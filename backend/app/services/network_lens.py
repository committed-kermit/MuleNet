"""
Network Risk Engine — Person 2 (ML - GNN)

2-Layer Graph Attention Network (GAT) with:
- Full PyG integration via SubgraphExtractor
- Exposed attention coefficients per edge (alpha)
- Top-K edge attribution logging for forensic dossiers
- Ring-topology structural heuristics
- Graceful fallback when model weights unavailable
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv
from typing import Tuple, Dict, Any, List, Optional
import numpy as np

from app.services.subgraph_extractor import subgraph_extractor
from app.services.ring_detector import ring_detector


class MuleGATModel(nn.Module):
    """
    2-Layer Graph Attention Network with multi-head attention and
    extractable per-edge attention coefficients for forensic attribution.

    Architecture:
        Layer 1: GATConv(16 -> 32, heads=4, concat=True) -> ELU -> Dropout(0.15)
        Layer 2: GATConv(128 -> 2,  heads=1, concat=False)
    """

    def __init__(
        self,
        in_channels: int = 16,
        hidden_channels: int = 32,
        out_channels: int = 2,
        heads: int = 4,
        dropout: float = 0.15
    ):
        super().__init__()
        self.dropout = dropout

        self.conv1 = GATConv(
            in_channels,
            hidden_channels,
            heads=heads,
            concat=True,
            dropout=dropout,
            add_self_loops=False  # we handle self-loops in extractor
        )
        self.bn1 = nn.BatchNorm1d(hidden_channels * heads)

        self.conv2 = GATConv(
            hidden_channels * heads,
            out_channels,
            heads=1,
            concat=False,
            dropout=dropout,
            add_self_loops=False
        )

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
        return_attention_weights: bool = False
    ):
        if return_attention_weights:
            x_out, (ei1, alpha1) = self.conv1(x, edge_index, return_attention_weights=True)
            x_out = self.bn1(x_out) if x_out.size(0) > 1 else x_out
            x_out = F.elu(x_out)
            x_out = F.dropout(x_out, p=self.dropout, training=self.training)
            logits, (ei2, alpha2) = self.conv2(x_out, edge_index, return_attention_weights=True)
            return logits, (ei2, alpha2)
        else:
            x_out = self.conv1(x, edge_index)
            x_out = self.bn1(x_out) if x_out.size(0) > 1 else x_out
            x_out = F.elu(x_out)
            x_out = F.dropout(x_out, p=self.dropout, training=self.training)
            return self.conv2(x_out, edge_index)


class NetworkRiskEngine:
    """
    Drives the MuleGATModel for real-time per-transaction network risk scoring.

    Scoring flow:
        1. MemoryGraphManager.get_ego_subgraph() -> ego_data dict
        2. SubgraphExtractor.extract()          -> PyG Data + focus_idx
        3. MuleGATModel forward (attention)     -> softmax probs + alpha
        4. Top-K attention edges extracted      -> forensic evidence list
        5. Structural heuristics applied        -> score boosted where warranted
    """

    TOP_K_ATTENTION_EDGES = 3  # number of top attention edges to surface in dossier

    def __init__(self):
        self.device = torch.device("cpu")
        self.model = MuleGATModel(
            in_channels=16,
            hidden_channels=32,
            out_channels=2,
            heads=4,
            dropout=0.15
        ).to(self.device)
        self._load_model()
        self.model.eval()

    def _load_model(self):
        model_paths = [
            os.path.abspath("backend/artifacts/mule_gat_model.pt"),
            os.path.abspath("MuleNet/backend/artifacts/mule_gat_model.pt"),
            os.path.abspath("artifacts/mule_gat_model.pt"),
        ]
        loaded = False
        for p in model_paths:
            if os.path.exists(p):
                try:
                    state = torch.load(p, map_location=self.device, weights_only=True)
                    # Handle both plain state_dict and wrapped checkpoint
                    if "model_state_dict" in state:
                        state = state["model_state_dict"]
                    self.model.load_state_dict(state, strict=False)
                    print(f"[NetworkRiskEngine] GAT weights loaded from {p}")
                    loaded = True
                    break
                except Exception as e:
                    print(f"[NetworkRiskEngine] Could not load weights from {p}: {e}")
        if not loaded:
            print("[NetworkRiskEngine] No pretrained weights found — using random init (dev mode).")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_network(
        self,
        account_id: str,
        counterparty_id: str,
        as_of_timestamp: str,
        graph_manager: Any
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Returns (network_risk_score ∈ [0,1], list of forensic evidence dicts).
        """
        ego_data = graph_manager.get_ego_subgraph(account_id, as_of_timestamp, hops=2)
        nodes = ego_data.get("nodes", [])
        links = ego_data.get("links", [])

        reasons: List[Dict[str, Any]] = []

        # Degenerate: completely isolated account
        if len(nodes) <= 1 and not links:
            return 0.08, [{
                "signal": "isolated_node",
                "weight": 0.05,
                "explanation": "No prior counterparties or transactions found in subgraph window."
            }]

        # Convert to PyG
        try:
            pyg_data, focus_idx, node_ids = subgraph_extractor.extract(
                ego_data, account_id, counterparty_id
            )
        except Exception as e:
            print(f"[NetworkRiskEngine] SubgraphExtractor failed: {e}")
            return 0.15, [{"signal": "extractor_error", "weight": 0.10, "explanation": str(e)}]

        x = pyg_data.x.to(self.device)
        edge_index = pyg_data.edge_index.to(self.device)

        # GAT inference
        gat_prob = 0.10
        try:
            with torch.no_grad():
                logits, (att_edge_index, alpha) = self.model(
                    x, edge_index, return_attention_weights=True
                )
                probs = F.softmax(logits, dim=-1)
                if focus_idx < probs.size(0):
                    gat_prob = float(probs[focus_idx, 1].item())

                # Extract top-K attention edges for evidence
                reasons.extend(
                    self._extract_attention_evidence(
                        alpha, att_edge_index, node_ids, focus_idx
                    )
                )
        except Exception as e:
            print(f"[NetworkRiskEngine] GAT forward error: {e}")

        # --- Structural heuristics (complement to GNN) ---
        score = gat_prob

        # Neighborhood density
        num_neighbors = len(nodes)
        num_links = len(links)
        density = num_links / max(1.0, num_neighbors * (num_neighbors - 1))

        if num_neighbors >= 3:
            density_boost = min(0.35, density * 0.7 + num_neighbors * 0.03)
            score = max(score, density_boost + gat_prob * 0.5)
            reasons.append({
                "signal": "high_neighborhood_density",
                "weight": round(density_boost, 3),
                "explanation": (
                    f"Ego-subgraph contains {num_neighbors} counterparties with "
                    f"density {density:.2f} — consistent with hub-and-spoke mule topology."
                )
            })

        # Known risky adjacency
        risky_links = [lnk for lnk in links if lnk.get("is_risky", False)]
        if risky_links:
            risky_boost = min(0.45, 0.20 + len(risky_links) * 0.08)
            score = max(score, 0.72 + len(risky_links) * 0.03)
            reasons.append({
                "signal": "known_mule_cluster_adjacency",
                "weight": round(risky_boost, 3),
                "explanation": (
                    f"{len(risky_links)} high-risk transaction edge(s) detected adjacent to "
                    f"account in active laundering topology."
                )
            })

        # Ring detector signals
        try:
            ring_analysis = ring_detector.analyse(
                account_id=account_id,
                graph=graph_manager.graph,
                as_of_timestamp=as_of_timestamp,
                hops=3
            )
            if ring_analysis["in_ring"]:
                score = max(score, 0.82)
                reasons.append({
                    "signal": "circular_routing_detected",
                    "weight": 0.50,
                    "explanation": ring_analysis["signals"][0] if ring_analysis["signals"] else
                        f"Account participates in a {ring_analysis['cycle_length']}-node circular routing ring."
                })
            if ring_analysis["device_syndicate"]:
                score = max(score, 0.70)
                reasons.append({
                    "signal": "device_sharing_syndicate",
                    "weight": 0.40,
                    "explanation": (
                        f"Account shares device fingerprint with "
                        f"{len(ring_analysis['syndicate_accounts'])} other account(s): "
                        f"{', '.join(ring_analysis['syndicate_accounts'][:3])}."
                    )
                })
            if ring_analysis["is_hub"]:
                score = max(score, 0.60)
                reasons.append({
                    "signal": "collection_hub_pattern",
                    "weight": 0.35,
                    "explanation": "Account exhibits fan-in collection hub structure consistent with smurfing aggregation."
                })
            if ring_analysis["layering_depth"] >= 3:
                reasons.append({
                    "signal": "deep_layering_path",
                    "weight": 0.20,
                    "explanation": f"Funds traceable through {ring_analysis['layering_depth']}-hop layering structure from this account."
                })
        except Exception as e:
            print(f"[NetworkRiskEngine] RingDetector error: {e}")

        # High mean GAT attention on this account's edges (ring signal)
        incident_attn = [
            float(lnk.get("gat_attention", 0.5))
            for lnk in links
            if lnk.get("source") == account_id or lnk.get("target") == account_id
        ]
        if incident_attn:
            mean_attn = float(np.mean(incident_attn))
            if mean_attn >= 0.80:
                score = max(score, 0.65)
                reasons.append({
                    "signal": "high_mean_edge_attention",
                    "weight": round(mean_attn, 3),
                    "explanation": (
                        f"Mean pre-recorded GAT attention on account edges is {mean_attn:.2f} "
                        f"— indicating account sits on a previously flagged high-attention path."
                    )
                })

        return min(1.0, round(float(score), 4)), reasons

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_attention_evidence(
        self,
        alpha: torch.Tensor,
        att_edge_index: torch.Tensor,
        node_ids: List[str],
        focus_idx: int
    ) -> List[Dict[str, Any]]:
        """
        Surfaces the top-K highest attention edges from the GAT Layer-2
        output for forensic dossier inclusion.
        """
        evidence = []
        try:
            alpha_np = alpha.squeeze(-1).cpu().numpy()
            if alpha_np.ndim == 0:
                alpha_np = np.array([float(alpha_np)])

            # Focus on edges incident to focus node
            num_edges = att_edge_index.shape[1]
            incident_mask = (
                (att_edge_index[0].cpu().numpy() == focus_idx) |
                (att_edge_index[1].cpu().numpy() == focus_idx)
            )

            if incident_mask.any():
                candidate_scores = alpha_np[incident_mask]
                candidate_edges = att_edge_index[:, incident_mask].cpu().numpy()
            else:
                candidate_scores = alpha_np
                candidate_edges = att_edge_index.cpu().numpy()

            top_k = min(self.TOP_K_ATTENTION_EDGES, len(candidate_scores))
            top_indices = np.argsort(candidate_scores)[-top_k:][::-1]

            for rank, idx in enumerate(top_indices):
                src_i = int(candidate_edges[0, idx])
                dst_i = int(candidate_edges[1, idx])
                attn_val = float(candidate_scores[idx])

                src_name = node_ids[src_i] if src_i < len(node_ids) else f"node_{src_i}"
                dst_name = node_ids[dst_i] if dst_i < len(node_ids) else f"node_{dst_i}"

                if src_name == dst_name:
                    continue  # skip self-loops

                evidence.append({
                    "signal": f"gat_attention_edge_rank{rank + 1}",
                    "weight": round(attn_val, 4),
                    "explanation": (
                        f"GAT Layer-2 assigned attention {attn_val:.3f} to edge "
                        f"{src_name} → {dst_name} (rank {rank + 1} of subgraph)."
                    )
                })
        except Exception as e:
            print(f"[NetworkRiskEngine] Attention extraction error: {e}")

        return evidence


network_risk_engine = NetworkRiskEngine()
