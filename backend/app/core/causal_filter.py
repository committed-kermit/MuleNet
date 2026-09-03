from datetime import datetime
from typing import List, Dict, Any

class CausalFilter:
    """
    Enforces strict temporal safety: ensures no function ever accesses data
    at or after the pending transaction's as_of_timestamp.
    """
    @staticmethod
    def parse_iso(ts_str: str) -> datetime:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        return datetime.fromisoformat(ts_str)

    @staticmethod
    def filter_prior_events(events: List[Dict[str, Any]], as_of_timestamp: str) -> List[Dict[str, Any]]:
        threshold_dt = CausalFilter.parse_iso(as_of_timestamp)
        return [
            e for e in events
            if CausalFilter.parse_iso(e["timestamp"]) < threshold_dt
        ]

    @staticmethod
    def filter_prior_transactions(txns: List[Dict[str, Any]], as_of_timestamp: str) -> List[Dict[str, Any]]:
        threshold_dt = CausalFilter.parse_iso(as_of_timestamp)
        return [
            t for t in txns
            if CausalFilter.parse_iso(t["timestamp"]) < threshold_dt
        ]
