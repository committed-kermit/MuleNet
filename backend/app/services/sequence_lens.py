import os
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime
import numpy as np
import xgboost as xgb

from app.core.causal_filter import CausalFilter

class SequenceRiskEngine:
    """
    Computes account lifecycle velocity, anomaly features strictly before as_of_timestamp,
    and evaluates sequence risk using trained XGBoost Sequence Model.
    """
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        model_paths = [
            os.path.abspath("backend/artifacts/xgboost_sequence_model.json"),
            os.path.abspath("MuleNet/backend/artifacts/xgboost_sequence_model.json"),
            os.path.abspath("artifacts/xgboost_sequence_model.json")
        ]
        for p in model_paths:
            if os.path.exists(p):
                try:
                    self.model = xgb.XGBClassifier(n_jobs=1)
                    self.model.load_model(p)
                    print(f"[SequenceRiskEngine] Loaded XGBoost model from {p}")
                    break
                except Exception as e:
                    print(f"[SequenceRiskEngine] Warning loading model from {p}: {e}")

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

        # 1. Setup to action gap (minutes)
        setup_gap_minutes = 9999.0
        for ev in reversed(prior_events):
            if ev.get("event_type") in ["mobile_number_change", "email_change", "payee_added", "password_reset"]:
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                diff = (as_of_dt - ev_dt).total_seconds() / 60.0
                if diff >= 0:
                    setup_gap_minutes = min(setup_gap_minutes, diff)
                    break

        # 2. Login velocity last 1h and 24h
        logins_1h = 0
        logins_24h = 0
        for ev in prior_events:
            if ev.get("event_type") in ["login", "new_device_login"]:
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                secs = (as_of_dt - ev_dt).total_seconds()
                if 0 <= secs <= 3600:
                    logins_1h += 1
                if 0 <= secs <= 86400:
                    logins_24h += 1

        # 3. Amount z-score
        prior_amounts = [t.get("amount", 0.0) for t in prior_txns]
        if len(prior_amounts) >= 3:
            mean_amt = float(np.mean(prior_amounts))
            std_amt = float(np.std(prior_amounts)) + 1e-5
            amount_zscore = float((amount - mean_amt) / std_amt)
        else:
            amount_zscore = 2.5 if amount > 25000 else (1.0 if amount > 5000 else 0.0)

        # 4. Dormancy flag
        dormancy_flag = 0.0
        if prior_txns:
            latest_txn_dt = max(CausalFilter.parse_iso(t["timestamp"]) for t in prior_txns)
            if (as_of_dt - latest_txn_dt).total_seconds() > 30 * 86400:
                dormancy_flag = 1.0

        # 5. Outflow / Inflow ratio
        inflows = sum(t.get("amount", 0.0) for t in prior_txns if t.get("receiver_id") == account_id)
        outflows = sum(t.get("amount", 0.0) for t in prior_txns if t.get("sender_id") == account_id) + amount
        flow_imbalance = abs(inflows - outflows) / max(1.0, (inflows + outflows))

        return {
            "setup_gap_minutes": setup_gap_minutes,
            "logins_1h": float(logins_1h),
            "logins_24h": float(logins_24h),
            "amount_zscore": max(0.0, amount_zscore),
            "dormancy_flag": dormancy_flag,
            "flow_imbalance": flow_imbalance,
            "fan_in_out_ratio": min(5.0, (logins_1h + 1.0) / 2.0),
            "degree_vs_time_mean": min(10.0, float(len(prior_txns) + 1)),
            "in_degree_ratio": 0.5,
            "out_degree_ratio": 0.5,
            "log_total_degree": float(np.log1p(len(prior_txns) + 1)),
            "extreme_feature_count_2": 2 if amount_zscore > 3.0 else 0,
            "extreme_feature_count_3": 1 if amount_zscore > 3.0 else 0,
            "feature_mean": float(amount / 10000.0),
            "feature_std": float(amount_zscore)
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
        
        # XGBoost Model Inference
        model_prob = None
        if self.model is not None:
            try:
                feature_vector = np.array([[
                    feats["flow_imbalance"],
                    feats["fan_in_out_ratio"],
                    feats["degree_vs_time_mean"],
                    feats["in_degree_ratio"],
                    feats["out_degree_ratio"],
                    feats["log_total_degree"],
                    feats["extreme_feature_count_2"],
                    feats["extreme_feature_count_3"],
                    feats["feature_mean"],
                    feats["feature_std"]
                ]])
                probs = self.model.predict_proba(feature_vector)[0]
                model_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            except Exception as e:
                print(f"[SequenceRiskEngine] XGBoost predict error: {e}")

        # Rule & Factor Evaluation
        score = model_prob if model_prob is not None else 0.05
        factors = []

        if feats["setup_gap_minutes"] < 5.0:
            boost = 0.50
            score = max(score, min(0.98, score + boost))
            factors.append({
                "feature": "setup_to_action_gap",
                "impact": 0.50,
                "explanation": f"High risk: Profile or payee setup occurred {int(feats['setup_gap_minutes'] * 60)}s before transfer attempt."
            })
        elif feats["setup_gap_minutes"] < 60.0:
            boost = 0.25
            score = max(score, min(0.98, score + boost))
            factors.append({
                "feature": "setup_to_action_gap",
                "impact": 0.25,
                "explanation": f"Profile or payee modified {int(feats['setup_gap_minutes'])} minutes prior to transfer."
            })

        if feats["amount_zscore"] > 3.0:
            boost = 0.35
            score = max(score, min(0.98, score + boost))
            factors.append({
                "feature": "amount_zscore",
                "impact": 0.35,
                "explanation": f"Transfer amount is {feats['amount_zscore']:.1f} standard deviations above historical account baseline."
            })

        if feats["logins_1h"] >= 4:
            boost = 0.20
            score = max(score, min(0.98, score + boost))
            factors.append({
                "feature": "login_velocity_1h",
                "impact": 0.20,
                "explanation": f"High login velocity: {int(feats['logins_1h'])} logins recorded in the past hour."
            })

        if feats["dormancy_flag"] > 0:
            boost = 0.20
            score = max(score, min(0.98, score + boost))
            factors.append({
                "feature": "dormancy_reactivation",
                "impact": 0.20,
                "explanation": "Account reactivated with high-value transaction after >30 days of inactivity."
            })

        return min(1.0, max(0.01, round(score, 4))), factors

sequence_risk_engine = SequenceRiskEngine()
