import networkx as nx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.core.causal_filter import CausalFilter

class MemoryGraphManager:
    """
    High-performance in-memory MultiDiGraph manager supporting dynamic
    temporal edge filtering, 1-2 hop ego-subgraph extraction, account event storage,
    and instant commits.
    """
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.account_metadata: Dict[str, Dict[str, Any]] = {}
        self.account_events: Dict[str, List[Dict[str, Any]]] = {}
        self.account_transactions: Dict[str, List[Dict[str, Any]]] = {}

    def add_account(self, account_id: str, metadata: Optional[Dict[str, Any]] = None):
        if not self.graph.has_node(account_id):
            self.graph.add_node(account_id, **(metadata or {}))
            self.account_metadata[account_id] = metadata or {}
        if account_id not in self.account_events:
            self.account_events[account_id] = []
        if account_id not in self.account_transactions:
            self.account_transactions[account_id] = []

    def record_event(self, account_id: str, event_type: str, timestamp: str, metadata: Optional[Dict[str, Any]] = None):
        self.add_account(account_id)
        ev = {
            "event_type": event_type,
            "timestamp": timestamp,
            **(metadata or {})
        }
        self.account_events[account_id].append(ev)
        # Keep events sorted chronologically
        self.account_events[account_id].sort(key=lambda x: CausalFilter.parse_iso(x["timestamp"]))

    def get_events(self, account_id: str) -> List[Dict[str, Any]]:
        return self.account_events.get(account_id, [])

    def get_transactions(self, account_id: str) -> List[Dict[str, Any]]:
        return self.account_transactions.get(account_id, [])

    def add_transaction_edge(
        self,
        sender_id: str,
        receiver_id: str,
        amount: float,
        timestamp: str,
        currency: str = "USD",
        payment_format: str = "ACH",
        edge_type: str = "TRANSACTED_WITH",
        gat_attention: float = 0.5,
        is_risky: bool = False
    ):
        self.add_account(sender_id)
        self.add_account(receiver_id)
        edge_data = {
            "amount": float(amount),
            "timestamp": timestamp,
            "currency": currency,
            "payment_format": payment_format,
            "edge_type": edge_type,
            "gat_attention": float(gat_attention),
            "is_risky": is_risky
        }
        self.graph.add_edge(sender_id, receiver_id, **edge_data)

        txn_record = {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "amount": float(amount),
            "timestamp": timestamp,
            "currency": currency,
            "edge_type": edge_type
        }
        self.account_transactions[sender_id].append(txn_record)
        self.account_transactions[receiver_id].append(txn_record)

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
        as_of_timestamp: Optional[str] = None,
        hops: int = 2,
        max_nodes: int = 50
    ) -> Dict[str, Any]:
        """
        Extracts a causal 1-2 hop ego-subgraph strictly before as_of_timestamp.
        """
        threshold_dt = CausalFilter.parse_iso(as_of_timestamp) if as_of_timestamp else None

        if not self.graph.has_node(account_id):
            return {
                "nodes": [{"id": account_id, "label": "Focus Account", "risk_tier": "LOW", "is_focus": True}],
                "links": []
            }

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
            return {
                "nodes": [{"id": account_id, "label": "Focus Account", "risk_tier": "LOW", "is_focus": True}],
                "links": []
            }

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
            meta = self.account_metadata.get(n, {})
            nodes_list.append({
                "id": n,
                "label": "Focus Account" if is_focus else f"Counterparty {n[-4:] if len(n) >= 4 else n}",
                "risk_tier": meta.get("risk_tier", "HIGH" if is_focus else "LOW"),
                "is_focus": is_focus
            })

        links_list = []
        for u, v, d in sub_g.edges(data=True):
            links_list.append({
                "source": u,
                "target": v,
                "amount": float(d.get("amount", 1000.0)),
                "gat_attention": float(d.get("gat_attention", 0.5)),
                "is_risky": bool(d.get("is_risky", False))
            })

        return {"nodes": nodes_list, "links": links_list}

    def seed_initial_topology(self):
        """
        Seeds realistic AML topological structures (Mule ring, rapid pass-through, fan-out, fan-in).
        """
        base_time = datetime.utcnow() - timedelta(hours=2)

        # 1. Smurfing / Collection Hub Ring
        hub = "BANK01_HUB900"
        smurfs = [f"BANK01_SMURF{i:02d}" for i in range(1, 6)]
        for i, s in enumerate(smurfs):
            ts = (base_time + timedelta(minutes=i * 5)).isoformat() + "Z"
            self.add_transaction_edge(s, hub, amount=9800.0, timestamp=ts, is_risky=True, gat_attention=0.88)
            self.record_event(s, "login", (base_time + timedelta(minutes=i * 5 - 1)).isoformat() + "Z")

        # Hub passes through to Layer 2 sink
        sink = "BANK04_SINK99"
        hub_ts = (base_time + timedelta(minutes=35)).isoformat() + "Z"
        self.add_transaction_edge(hub, sink, amount=48900.0, timestamp=hub_ts, is_risky=True, gat_attention=0.94)

        # 2. Circular Routing Ring (A -> B -> C -> A)
        ring_a, ring_b, ring_c = "BANK02_RING_A", "BANK03_RING_B", "BANK01_RING_C"
        t1 = (base_time + timedelta(minutes=10)).isoformat() + "Z"
        t2 = (base_time + timedelta(minutes=20)).isoformat() + "Z"
        t3 = (base_time + timedelta(minutes=30)).isoformat() + "Z"
        self.add_transaction_edge(ring_a, ring_b, amount=25000.0, timestamp=t1, is_risky=True, gat_attention=0.82)
        self.add_transaction_edge(ring_b, ring_c, amount=24500.0, timestamp=t2, is_risky=True, gat_attention=0.85)
        self.add_transaction_edge(ring_c, ring_a, amount=24000.0, timestamp=t3, is_risky=True, gat_attention=0.91)

        # 3. ATO Seed Profile (BANK01_ACC1042)
        ato_acc = "BANK01_ACC1042"
        ato_ts = (datetime.utcnow() - timedelta(minutes=2)).isoformat() + "Z"
        self.record_event(ato_acc, "password_reset", (datetime.utcnow() - timedelta(minutes=4)).isoformat() + "Z")
        self.record_event(ato_acc, "mobile_number_change", (datetime.utcnow() - timedelta(minutes=3)).isoformat() + "Z")
        self.record_event(ato_acc, "payee_added", (datetime.utcnow() - timedelta(minutes=2)).isoformat() + "Z", {"payee": "BANK04_ACC9011"})
        for k in range(5):
            self.record_event(ato_acc, "login", (datetime.utcnow() - timedelta(minutes=5 - k)).isoformat() + "Z")

        # 4. Legitimate Baseline accounts
        for i in range(10):
            legit_a = f"BANK01_LEGIT_{i:02d}"
            legit_b = f"BANK02_LEGIT_{i:02d}"
            ts_legit = (base_time - timedelta(days=i + 1)).isoformat() + "Z"
            self.add_transaction_edge(legit_a, legit_b, amount=120.0 + (i * 35.0), timestamp=ts_legit)
            self.record_event(legit_a, "login", (base_time - timedelta(days=i + 1, minutes=10)).isoformat() + "Z")

memory_graph = MemoryGraphManager()
memory_graph.seed_initial_topology()
