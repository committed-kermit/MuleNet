import networkx as nx
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.causal_filter import CausalFilter

class MemoryGraphManager:
    """
    High-performance in-memory MultiDiGraph manager supporting dynamic
    temporal edge filtering, 1-2 hop ego-subgraph extraction, and instant commits.
    """
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.account_metadata: Dict[str, Dict[str, Any]] = {}

    def add_account(self, account_id: str, metadata: Optional[Dict[str, Any]] = None):
        if not self.graph.has_node(account_id):
            self.graph.add_node(account_id, **(metadata or {}))
            self.account_metadata[account_id] = metadata or {}

    def add_transaction_edge(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        timestamp: str,
        currency: str = "USD",
        payment_format: str = "ACH",
        edge_type: str = "TRANSACTED_WITH"
    ):
        self.add_account(sender_id)
        self.add_account(receiver_id)
        self.graph.add_edge(
            sender_id,
            receiver_id,
            amount=amount,
            timestamp=timestamp,
            currency=currency,
            payment_format=payment_format,
            edge_type=edge_type
        )

    def add_device_edge(self, account_a: str, account_b: str, device_id: str, timestamp: str):
        self.add_account(account_a)
        self.add_account(account_b)
        self.graph.add_edge(
            account_a,
            account_b,
            device_id=device_id,
            timestamp=timestamp,
            edge_type="SHARES_DEVICE"
        )

    def get_ego_subgraph(
        self,
        account_id: str,
        as_of_timestamp: str,
        hops: int = 2,
        max_nodes: int = 50
    ) -> Dict[str, Any]:
        """
        Extracts a causal 1-2 hop ego-subgraph strictly before as_of_timestamp.
        """
        threshold_dt = CausalFilter.parse_iso(as_of_timestamp) if as_of_timestamp else None

        if not self.graph.has_node(account_id):
            return {"nodes": [{"id": account_id, "label": "Sender", "risk_tier": "LOW", "is_focus": True}], "links": []}

        # Build causal subgraph
        valid_edges = []
        for u, v, k, data in self.graph.edges(data=True, keys=True):
            edge_ts = data.get("timestamp")
            if edge_ts:
                if threshold_dt is None or CausalFilter.parse_iso(edge_ts) < threshold_dt:
                    valid_edges.append((u, v, data))
            else:
                valid_edges.append((u, v, data))

        temp_g = nx.DiGraph()
        for u, v, d in valid_edges:
            temp_g.add_edge(u, v, **d)

        if not temp_g.has_node(account_id):
            return {"nodes": [{"id": account_id, "label": "Account", "risk_tier": "LOW", "is_focus": True}], "links": []}

        # Ego subgraph extraction
        undirected_view = temp_g.to_undirected()
        sub_nodes = set(nx.single_source_shortest_path_length(undirected_view, account_id, cutoff=hops).keys())
        
        # Limit to max_nodes
        if len(sub_nodes) > max_nodes:
            sub_nodes = set(list(sub_nodes)[:max_nodes])
            sub_nodes.add(account_id)

        sub_g = temp_g.subgraph(sub_nodes)

        nodes_list = []
        for n in sub_g.nodes():
            is_focus = (n == account_id)
            nodes_list.append({
                "id": n,
                "label": "Focus Account" if is_focus else f"Counterparty {n[-4:] if len(n) >= 4 else n}",
                "risk_tier": "HIGH" if is_focus else "LOW",
                "is_focus": is_focus
            })

        links_list = []
        for u, v, d in sub_g.edges(data=True):
            links_list.append({
                "source": u,
                "target": v,
                "amount": float(d.get("amount", 1000.0)),
                "gat_attention": float(d.get("gat_attention", 0.5)),
                "is_risky": d.get("is_risky", False)
            })

        return {"nodes": nodes_list, "links": links_list}

memory_graph = MemoryGraphManager()
