import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv
from typing import Tuple, Dict, Any, List
import numpy as np

class MuleGATModel(nn.Module):
    """
    2-Layer Graph Attention Network (GAT) with attention coefficient hooks
    for explainable AML network forensics.
    """
    def __init__(self, in_channels: int = 16, hidden_channels: int = 32, out_channels: int = 2, heads: int = 2):
        super().__init__()
        self.conv1 = GATConv(in_channels, hidden_channels, heads=heads, concat=True)
        self.conv2 = GATConv(hidden_channels * heads, out_channels, heads=1, concat=False)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, return_attention_weights: bool = False):
        if return_attention_weights:
            x, (edge_index_1, alpha_1) = self.conv1(x, edge_index, return_attention_weights=True)
            x = F.relu(x)
            x = F.dropout(x, p=0.1, training=self.training)
            out, (edge_index_2, alpha_2) = self.conv2(x, edge_index, return_attention_weights=True)
            return out, (edge_index_2, alpha_2)
        else:
            x = self.conv1(x, edge_index)
            x = F.relu(x)
            x = F.dropout(x, p=0.1, training=self.training)
            out = self.conv2(x, edge_index)
            return out

class NetworkRiskEngine:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = MuleGATModel(in_channels=16, hidden_channels=32, out_channels=2, heads=2).to(self.device)
        self._load_model()
        self.model.eval()

    def _load_model(self):
        model_paths = [
            os.path.abspath("backend/artifacts/mule_gat_model.pt"),
            os.path.abspath("MuleNet/backend/artifacts/mule_gat_model.pt"),
            os.path.abspath("artifacts/mule_gat_model.pt")
        ]
        for p in model_paths:
            if os.path.exists(p):
                try:
                    state_dict = torch.load(p, map_location=self.device)
                    self.model.load_state_dict(state_dict)
                    print(f"[NetworkRiskEngine] Loaded GAT weights from {p}")
                    break
                except Exception as e:
                    print(f"[NetworkRiskEngine] Warning loading GAT weights from {p}: {e}")

    def score_network(
        self,
        account_id: str,
        counterparty_id: str,
        as_of_timestamp: str,
        graph_manager: Any
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Computes network risk score and extracts top GAT edge attention weights.
        """
        ego_data = graph_manager.get_ego_subgraph(account_id, as_of_timestamp, hops=2)
        nodes = ego_data.get("nodes", [])
        links = ego_data.get("links", [])
        num_neighbors = len(nodes)
        num_links = len(links)

        reasons = []
        base_score = 0.05

        if num_neighbors <= 1 and num_links == 0:
            # Low prior connectivity
            return 0.08, [{
                "signal": "isolated_node",
                "weight": 0.05,
                "explanation": "No prior transaction history or counterparties in graph."
            }]

        # Map node ids to tensor indices
        node_id_to_idx = {n["id"]: idx for idx, n in enumerate(nodes)}
        focus_idx = node_id_to_idx.get(account_id, 0)

        # Build node feature tensor (16 features per node)
        x_features = []
        for n in nodes:
            n_id = n["id"]
            in_deg = sum(1 for l in links if l.get("target") == n_id)
            out_deg = sum(1 for l in links if l.get("source") == n_id)
            tot_deg = in_deg + out_deg
            flow_imb = abs(in_deg - out_deg) / max(1, tot_deg)
            is_foc = 1.0 if n_id == account_id else 0.0
            is_cp = 1.0 if n_id == counterparty_id else 0.0
            
            feat = [
                float(in_deg), float(out_deg), float(tot_deg), float(flow_imb),
                is_foc, is_cp, float(num_neighbors), float(num_links),
                float(np.log1p(tot_deg)), 0.5, 0.5, 0.1, 0.0, 0.0, 0.0, 0.0
            ]
            x_features.append(feat)

        x_tensor = torch.tensor(x_features, dtype=torch.float, device=self.device)

        # Build edge index
        src_indices, dst_indices = [], []
        for l in links:
            s_id, t_id = l.get("source"), l.get("target")
            if s_id in node_id_to_idx and t_id in node_id_to_idx:
                src_indices.append(node_id_to_idx[s_id])
                dst_indices.append(node_id_to_idx[t_id])

        if not src_indices:
            # Fallback self-loops
            src_indices = list(range(len(nodes)))
            dst_indices = list(range(len(nodes)))

        edge_index = torch.tensor([src_indices, dst_indices], dtype=torch.long, device=self.device)

        # GAT Inference with Attention Extraction
        gat_prob = 0.1
        try:
            with torch.no_grad():
                logits, (edge_att_index, alpha) = self.model(x_tensor, edge_index, return_attention_weights=True)
                probs = F.softmax(logits, dim=-1)
                gat_prob = float(probs[focus_idx, 1].item())
                
                # Annotate top attention edges
                if alpha is not None and len(alpha) > 0:
                    alpha_flat = alpha.squeeze().cpu().numpy()
                    if alpha_flat.ndim == 0:
                        alpha_flat = np.array([float(alpha_flat)])
                    top_att_idx = int(np.argmax(alpha_flat))
                    if top_att_idx < edge_att_index.shape[1]:
                        src_node = nodes[edge_att_index[0, top_att_idx].item()]["id"]
                        dst_node = nodes[edge_att_index[1, top_att_idx].item()]["id"]
                        reasons.append({
                            "signal": "gat_attention_hotspot",
                            "weight": round(float(alpha_flat[top_att_idx]), 3),
                            "explanation": f"GNN identified critical structural edge {src_node} -> {dst_node} with attention {float(alpha_flat[top_att_idx]):.2f}"
                        })
        except Exception as e:
            print(f"[NetworkRiskEngine] GAT forward error: {e}")

        # Graph Density / Ring heuristics
        density = num_links / max(1, (num_neighbors * (num_neighbors - 1)))
        score = max(gat_prob, (num_neighbors * 0.04) + (density * 0.45))

        if num_neighbors >= 3:
            reasons.append({
                "signal": "high_neighborhood_density",
                "weight": 0.35,
                "explanation": f"Connected to {num_neighbors} active transaction counterparties in ego-subgraph."
            })

        has_risky_edges = any(l.get("is_risky", False) for l in links)
        if has_risky_edges:
            score = max(score, 0.78)
            reasons.append({
                "signal": "known_mule_cluster_adjacency",
                "weight": 0.45,
                "explanation": "Account is adjacent to high-risk counterparty in active laundering topology."
            })

        return min(1.0, round(float(score), 4)), reasons

network_risk_engine = NetworkRiskEngine()
