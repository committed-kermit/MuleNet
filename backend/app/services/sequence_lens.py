from typing import Dict, Any, List, Tuple
from datetime import datetime
from app.core.causal_filter import CausalFilter
import numpy as np

class SequenceRiskEngine:
    """
    Computes account lifecycle velocity and anomaly features strictly before as_of_timestamp
    and evaluates sequence risk.
    """
    def __init__(self):
        self.model = None # XGBoost / LightGBM model placeholder

    def extract_features(
        self,
        account_id: str,
        amount: float,
        as_of_timestamp: str,
        events: List[Dict[str, Any]],
        historical_txns: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        prior_events = CausalFilter.filter_prior_events(events, as_of_timestamp)
        prior_txns = CausalFilter.filter_prior_transactions(historical_txns, as_of_timestamp)
        as_of_dt = CausalFilter.parse_iso(as_of_timestamp)

        # 1. Setup to action gap
        setup_gap_minutes = 9999.0
        for ev in reversed(prior_events):
            if ev.get("event_type") in ["mobile_number_change", "email_change", "payee_added", "password_reset"]:
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                diff = (as_of_dt - ev_dt).total_seconds() / 60.0
                if diff >= 0:
                    setup_gap_minutes = min(setup_gap_minutes, diff)
                    break

        # 2. Login velocity last 1h
        logins_1h = 0
        for ev in prior_events:
            if ev.get("event_type") in ["login", "new_device_login"]:
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                if 0 <= (as_of_dt - ev_dt).total_seconds() <= 3600:
                    logins_1h += 1

        # 3. Amount z-score
        prior_amounts = [t.get("amount", 0.0) for t in prior_txns]
        if len(prior_amounts) >= 3:
            mean_amt = float(np.mean(prior_amounts))
            std_amt = float(np.std(prior_amounts)) + 1e-5
            amount_zscore = float((amount - mean_amt) / std_amt)
        else:
            amount_zscore = 1.0 if amount > 5000 else 0.0

        # 4. Dormancy flag
        dormancy_flag = 0.0
        if prior_txns:
            latest_txn_dt = max(CausalFilter.parse_iso(t["timestamp"]) for t in prior_txns)
            if (as_of_dt - latest_txn_dt).total_seconds() > 30 * 86400:
                dormancy_flag = 1.0

        return {
            "setup_gap_minutes": setup_gap_minutes,
            "logins_1h": float(logins_1h),
            "amount_zscore": max(0.0, amount_zscore),
            "dormancy_flag": dormancy_flag,
        }

    def score_sequence(
        self,
        account_id: str,
        amount: float,
        as_of_timestamp: str,
        events: List[Dict[str, Any]],
        historical_txns: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict[str, Any]]]:
        feats = self.extract_features(account_id, amount, as_of_timestamp, events, historical_txns)
        
        # Scoring logic based on sequence rules & XGBoost feature thresholds
        score = 0.05
        factors = []

        if feats["setup_gap_minutes"] < 5.0:
            score += 0.45
            factors.append({
                "feature": "setup_to_action_gap",
                "impact": 0.45,
                "explanation": f"Profile or payee setup occurred {int(feats['setup_gap_minutes'] * 60)}s before transfer attempt."
            })
        elif feats["setup_gap_minutes"] < 60.0:
            score += 0.25
            factors.append({
                "feature": "setup_to_action_gap",
                "impact": 0.25,
                "explanation": f"Profile or payee modified {int(feats['setup_gap_minutes'])} minutes prior to transfer."
            })

        if feats["amount_zscore"] > 3.0:
            score += 0.30
            factors.append({
                "feature": "amount_zscore",
                "impact": 0.30,
                "explanation": f"Transfer amount is {feats['amount_zscore']:.1f} standard deviations above historical account baseline."
            })

        if feats["logins_1h"] >= 5:
            score += 0.15
            factors.append({
                "feature": "login_velocity_1h",
                "impact": 0.15,
                "explanation": f"High login velocity: {int(feats['logins_1h'])} logins recorded in the past hour."
            })

        return min(1.0, round(score, 4)), factors

sequence_risk_engine = SequenceRiskEngine()
