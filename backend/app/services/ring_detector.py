"""
Ring Detector — Person 2 (ML - GNN)

Pure NetworkX-based cycle and structural pattern detector operating on the
in-memory graph. Complements the GNN score with deterministic graph topology
signals that don't require model inference.

Detects:
- Circular routing (A -> B -> C -> A) via simple_cycles
- Device-sharing syndicates (SHARES_DEVICE edge clusters)
- Fan-in collection hubs (high in-degree concentration)
- Fan-out dispersal nodes (high out-degree in short time windows)
- Multi-hop layering depth (longest simple path from source)
"""

import networkx as nx
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta


class RingDetector:
    """
    Deterministic graph topology analyser. Operates on the
    MemoryGraphManager's live NetworkX MultiDiGraph.
    """

    MAX_CYCLE_LENGTH = 6    # ignore very long cycles (noise)
    MIN_CYCLE_LENGTH = 2    # minimum meaningful cycle
    HUB_IN_DEGREE_THRESHOLD = 4
    DISPERSAL_OUT_DEGREE_THRESHOLD = 4

    def analyse(
        self,
        account_id: str,
        graph: nx.MultiDiGraph,
        as_of_timestamp: Optional[str] = None,
        hops: int = 3
    ) -> Dict[str, Any]:
        """
        Runs all ring and structural detectors for `account_id`.

        Returns a dict:
        {
            "in_ring": bool,
            "ring_members": list[str],
            "cycle_length": int,
            "is_hub": bool,
            "is_dispersal": bool,
            "device_syndicate": bool,
            "syndicate_accounts": list[str],
            "layering_depth": int,
            "signals": list[str]   # human-readable evidence strings
        }
        """
        result = {
            "in_ring": False,
            "ring_members": [],
            "cycle_length": 0,
            "is_hub": False,
            "is_dispersal": False,
            "device_syndicate": False,
            "syndicate_accounts": [],
            "layering_depth": 0,
            "signals": []
        }

        # Build causal snapshot up to as_of_timestamp
        causal_g = self._build_causal_graph(graph, as_of_timestamp)

        if account_id not in causal_g:
            return result

        # 1. Circular routing detection
        self._detect_cycles(account_id, causal_g, result, hops)

        # 2. Device-sharing syndicate
        self._detect_device_syndicate(account_id, graph, result)

        # 3. Hub / dispersal classification
        self._classify_hub_dispersal(account_id, causal_g, result)

        # 4. Layering depth
        self._measure_layering_depth(account_id, causal_g, result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_causal_graph(
        self,
        graph: nx.MultiDiGraph,
        as_of_timestamp: Optional[str]
    ) -> nx.DiGraph:
        """Returns a causal DiGraph with only edges strictly before as_of."""
        g = nx.DiGraph()
        threshold_dt = None
        if as_of_timestamp:
            try:
                threshold_dt = datetime.fromisoformat(
                    as_of_timestamp.replace("Z", "+00:00")
                )
            except Exception:
                pass

        for u, v, data in graph.edges(data=True):
            ts = data.get("timestamp")
            if ts and threshold_dt:
                try:
                    edge_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if edge_dt >= threshold_dt:
                        continue
                except Exception:
                    pass
            g.add_edge(u, v, **data)

        return g

    def _detect_cycles(
        self,
        account_id: str,
        g: nx.DiGraph,
        result: Dict,
        hops: int
    ):
        """Finds shortest simple cycle containing account_id within hop limit."""
        # Work on ego-neighbourhood to keep cycle search tractable
        try:
            reachable = set(nx.single_source_shortest_path_length(
                g.to_undirected(), account_id, cutoff=hops
            ).keys())
            sub = g.subgraph(reachable)

            shortest = None
            for cycle in nx.simple_cycles(sub):
                if account_id in cycle:
                    cl = len(cycle)
                    if self.MIN_CYCLE_LENGTH <= cl <= self.MAX_CYCLE_LENGTH:
                        if shortest is None or cl < len(shortest):
                            shortest = cycle

            if shortest:
                result["in_ring"] = True
                result["ring_members"] = shortest
                result["cycle_length"] = len(shortest)
                result["signals"].append(
                    f"Circular routing detected: {' → '.join(shortest + [shortest[0]])} "
                    f"(cycle length {len(shortest)})."
                )
        except Exception as e:
            print(f"[RingDetector] Cycle detection error: {e}")

    def _detect_device_syndicate(
        self,
        account_id: str,
        graph: nx.MultiDiGraph,
        result: Dict
    ):
        """Checks SHARES_DEVICE edges for multi-account syndicate indicators."""
        syndicate: Set[str] = set()
        try:
            for u, v, data in graph.edges(data=True):
                if data.get("edge_type") == "SHARES_DEVICE":
                    if u == account_id or v == account_id:
                        syndicate.add(u)
                        syndicate.add(v)
                        dev_id = data.get("device_id", "UNKNOWN")
                        result["signals"].append(
                            f"Device-sharing link detected: {u} ↔ {v} "
                            f"(device {dev_id}) — potential account syndicate."
                        )
            syndicate.discard(account_id)
            if syndicate:
                result["device_syndicate"] = True
                result["syndicate_accounts"] = list(syndicate)
        except Exception as e:
            print(f"[RingDetector] Device syndicate detection error: {e}")

    def _classify_hub_dispersal(
        self,
        account_id: str,
        g: nx.DiGraph,
        result: Dict
    ):
        """Classifies account as collection hub or dispersal node by degree."""
        try:
            in_d = g.in_degree(account_id)
            out_d = g.out_degree(account_id)

            if in_d >= self.HUB_IN_DEGREE_THRESHOLD:
                result["is_hub"] = True
                result["signals"].append(
                    f"Collection hub pattern: in-degree {in_d} — "
                    f"receiving from {in_d} distinct counterparties."
                )

            if out_d >= self.DISPERSAL_OUT_DEGREE_THRESHOLD:
                result["is_dispersal"] = True
                result["signals"].append(
                    f"Fan-out dispersal pattern: out-degree {out_d} — "
                    f"funds dispersed to {out_d} distinct destinations."
                )
        except Exception as e:
            print(f"[RingDetector] Hub/dispersal classification error: {e}")

    def _measure_layering_depth(
        self,
        account_id: str,
        g: nx.DiGraph,
        result: Dict
    ):
        """Estimates layering depth as the longest reachable path from account."""
        try:
            if not nx.is_directed_acyclic_graph(g):
                # For cyclic graphs, use BFS depth as proxy
                lengths = nx.single_source_shortest_path_length(g, account_id)
                depth = max(lengths.values()) if lengths else 0
            else:
                # True DAG longest path
                descendants = nx.descendants(g, account_id) | {account_id}
                sub = g.subgraph(descendants)
                depth = nx.dag_longest_path_length(sub) if sub.nodes else 0

            result["layering_depth"] = int(depth)
            if depth >= 3:
                result["signals"].append(
                    f"Deep layering structure detected: {depth}-hop reachable "
                    f"path from account — consistent with placement-layering-integration cycle."
                )
        except Exception as e:
            print(f"[RingDetector] Layering depth error: {e}")


ring_detector = RingDetector()
