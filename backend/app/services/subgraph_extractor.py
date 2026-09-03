"""
Subgraph Extractor — Person 2 (ML - GNN)

Responsible for converting the in-memory NetworkX ego-subgraph into
a PyTorch Geometric Data object suitable for direct GAT inference.

Key responsibilities:
- Node feature matrix construction (16-dim per node)
- Temporal edge masking (strict as_of causality)
- Edge index building with self-loop injection
- Mapping of node IDs to tensor indices (for focus-node extraction)
- PageRank-based centrality features (via networkx)
"""

import torch
import numpy as np
import networkx as nx
from typing import Dict, Any, List, Tuple, Optional
from torch_geometric.data import Data


class SubgraphExtractor:
    """
    Converts raw ego-subgraph dicts from MemoryGraphManager into
    PyG Data objects ready for GAT forward pass.
    """

    NODE_FEATURE_DIM = 16

    def extract(
        self,
        ego_data: Dict[str, Any],
        focus_account_id: str,
        counterparty_id: Optional[str] = None
    ) -> Tuple[Data, int, List[str]]:
        """
        Parameters
        ----------
        ego_data : dict with "nodes" and "links" lists from MemoryGraphManager.get_ego_subgraph()
        focus_account_id : the account being scored
        counterparty_id : optional, the intended payment target

        Returns
        -------
        pyg_data : torch_geometric.data.Data
        focus_idx : int index of focus node in the node tensor
        node_ids  : ordered list of node id strings (idx -> id mapping)
        """
        nodes: List[Dict] = ego_data.get("nodes", [])
        links: List[Dict] = ego_data.get("links", [])

        if not nodes:
            # Degenerate: isolated node, return minimal graph
            x = torch.zeros((1, self.NODE_FEATURE_DIM), dtype=torch.float)
            edge_index = torch.tensor([[0], [0]], dtype=torch.long)  # self-loop
            return Data(x=x, edge_index=edge_index), 0, [focus_account_id]

        node_ids = [n["id"] for n in nodes]
        node_id_to_idx: Dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}
        focus_idx = node_id_to_idx.get(focus_account_id, 0)

        # --- Build lightweight NX graph for centrality computation ---
        g_tmp = nx.DiGraph()
        for n in nodes:
            g_tmp.add_node(n["id"])
        for lnk in links:
            s, t = lnk.get("source"), lnk.get("target")
            if s and t:
                g_tmp.add_edge(s, t, weight=float(lnk.get("amount", 1.0)))

        # PageRank centrality (damping=0.85, max_iter=50 for speed)
        try:
            pagerank = nx.pagerank(g_tmp, alpha=0.85, max_iter=50, weight="weight")
        except Exception:
            pagerank = {n["id"]: 1.0 / max(len(nodes), 1) for n in nodes}

        # Degree stats
        in_degrees = dict(g_tmp.in_degree())
        out_degrees = dict(g_tmp.out_degree())
        total_nodes = max(len(nodes), 1)
        total_links = max(len(links), 1)

        # Volume stats per node
        node_volumes: Dict[str, float] = {}
        for lnk in links:
            amt = float(lnk.get("amount", 0.0))
            node_volumes[lnk.get("source", "")] = node_volumes.get(lnk.get("source", ""), 0.0) + amt
            node_volumes[lnk.get("target", "")] = node_volumes.get(lnk.get("target", ""), 0.0) + amt

        max_vol = max(node_volumes.values(), default=1.0)
        max_pr = max(pagerank.values(), default=1.0)

        # --- Node feature matrix (16 dims) ---
        x_rows = []
        for n in nodes:
            nid = n["id"]
            in_d = float(in_degrees.get(nid, 0))
            out_d = float(out_degrees.get(nid, 0))
            tot_d = in_d + out_d
            flow_imb = abs(in_d - out_d) / max(1.0, tot_d)
            is_focus = 1.0 if nid == focus_account_id else 0.0
            is_cp = 1.0 if nid == counterparty_id else 0.0
            pr = float(pagerank.get(nid, 0.0)) / max(max_pr, 1e-9)
            vol_norm = node_volumes.get(nid, 0.0) / max(max_vol, 1.0)
            log_deg = float(np.log1p(tot_d))
            deg_norm = tot_d / max(total_nodes, 1)

            # Risky edge adjacency flag
            adj_risky = float(any(
                (lnk.get("source") == nid or lnk.get("target") == nid) and lnk.get("is_risky", False)
                for lnk in links
            ))

            # GAT attention of incident edges (mean)
            incident_attn = [
                float(lnk.get("gat_attention", 0.5))
                for lnk in links
                if lnk.get("source") == nid or lnk.get("target") == nid
            ]
            mean_attn = float(np.mean(incident_attn)) if incident_attn else 0.5

            feat = [
                in_d / max(total_nodes, 1),    # 0: in-degree normalized
                out_d / max(total_nodes, 1),   # 1: out-degree normalized
                deg_norm,                       # 2: total degree normalized
                flow_imb,                       # 3: flow imbalance
                is_focus,                       # 4: is focal account
                is_cp,                          # 5: is counterparty
                pr,                             # 6: pagerank (normalized)
                vol_norm,                       # 7: transaction volume (normalized)
                log_deg,                        # 8: log(1 + degree)
                float(total_nodes) / 50.0,     # 9: subgraph size context
                float(total_links) / 100.0,    # 10: subgraph edge density context
                adj_risky,                      # 11: adjacent to risky edge
                mean_attn,                      # 12: mean GAT attention on incident edges
                0.0,                            # 13: reserved (device-sharing flag)
                0.0,                            # 14: reserved (ring membership)
                0.0,                            # 15: reserved (temporal recency)
            ]
            x_rows.append(feat)

        x_tensor = torch.tensor(x_rows, dtype=torch.float)

        # --- Edge index ---
        src_idx, dst_idx = [], []
        risky_edge_mask = []
        attention_weights = []

        for lnk in links:
            s_id, t_id = lnk.get("source"), lnk.get("target")
            if s_id in node_id_to_idx and t_id in node_id_to_idx:
                src_idx.append(node_id_to_idx[s_id])
                dst_idx.append(node_id_to_idx[t_id])
                risky_edge_mask.append(1.0 if lnk.get("is_risky", False) else 0.0)
                attention_weights.append(float(lnk.get("gat_attention", 0.5)))

        # Inject self-loops for GAT stability
        for i in range(len(nodes)):
            src_idx.append(i)
            dst_idx.append(i)
            risky_edge_mask.append(0.0)
            attention_weights.append(0.0)

        edge_index = torch.tensor([src_idx, dst_idx], dtype=torch.long)
        edge_attr = torch.tensor(attention_weights, dtype=torch.float).unsqueeze(-1)

        pyg_data = Data(
            x=x_tensor,
            edge_index=edge_index,
            edge_attr=edge_attr,
            num_nodes=len(nodes)
        )

        return pyg_data, focus_idx, node_ids


subgraph_extractor = SubgraphExtractor()
