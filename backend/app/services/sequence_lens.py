"""
Sequence Risk Engine — Person 3 (ML - Sequence & SHAP)

Computes account lifecycle velocity and behavioural features strictly before
as_of_timestamp, then evaluates sequence risk via a trained XGBoost classifier.
SHAP TreeExplainer provides per-feature attribution for every scored transaction.

Feature set (15 features):
  - setup_gap_minutes        : time between last credential/payee change and action
  - logins_1h / logins_24h  : session velocity
  - amount_zscore            : how far this amount deviates from account history
  - dormancy_flag            : reactivation after >30 days silence
  - flow_imbalance           : (|inflow - outflow|) / (inflow + outflow)
  - fan_in_out_ratio         : login-velocity proxy for counterparty fan
  - degree_vs_time_mean      : transaction count relative to account window
  - in_degree_ratio          : proportion incoming
  - out_degree_ratio         : proportion outgoing
  - log_total_degree         : log(1 + txn_count)
  - extreme_feature_count_2  : number of features at extreme percentile
  - extreme_feature_count_3  : number of features at ultra-extreme percentile
  - feature_mean             : normalised amount
  - feature_std              : amount z-score (mirrors amount_zscore for XGB)
  - new_device_flag          : login from new/unrecognised device in session
  - payee_added_flag         : payee was added in this session window
"""

import os
import json
from typing import Dict, Any, List, Tuple
from datetime import datetime
import numpy as np
import xgboost as xgb

from app.core.causal_filter import CausalFilter
from app.services.shap_engine import shap_engine


class SequenceRiskEngine:
    """
    Evaluates behavioural sequence risk using XGBoost + SHAP.
    All features are computed strictly before as_of_timestamp (causal).
    """

    FEATURE_ORDER = [
        "flow_imbalance", "fan_in_out_ratio", "degree_vs_time_mean",
        "in_degree_ratio", "out_degree_ratio", "log_total_degree",
        "extreme_feature_count_2", "extreme_feature_count_3",
        "feature_mean", "feature_std"
    ]

    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        model_paths = [
            os.path.abspath("backend/artifacts/xgboost_sequence_model.json"),
            os.path.abspath("MuleNet/backend/artifacts/xgboost_sequence_model.json"),
            os.path.abspath("artifacts/xgboost_sequence_model.json"),
        ]
        for p in model_paths:
            if os.path.exists(p):
                try:
                    self.model = xgb.XGBClassifier(n_jobs=1)
                    self.model.load_model(p)
                    # Init SHAP explainer immediately after model load
                    shap_engine.init_explainer(self.model)
                    print(f"[SequenceRiskEngine] XGBoost + SHAP loaded from {p}")
                    break
                except Exception as e:
                    print(f"[SequenceRiskEngine] Warning loading model from {p}: {e}")

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def extract_features(
        self,
        account_id: str,
        amount: float,
        as_of_timestamp: str,
        events: List[Dict[str, Any]],
        historical_txns: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        prior_events = CausalFilter.filter_prior_events(events, as_of_timestamp)
        prior_txns   = CausalFilter.filter_prior_transactions(historical_txns, as_of_timestamp)
        as_of_dt     = CausalFilter.parse_iso(as_of_timestamp)

        # ---- 1. Setup-to-action gap (minutes) ----
        SETUP_EVENT_TYPES = {
            "mobile_number_change", "email_change", "payee_added",
            "password_reset", "address_change", "beneficiary_added"
        }
        setup_gap_minutes = 9999.0
        for ev in reversed(prior_events):
            if ev.get("event_type") in SETUP_EVENT_TYPES:
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                diff = (as_of_dt - ev_dt).total_seconds() / 60.0
                if diff >= 0:
                    setup_gap_minutes = min(setup_gap_minutes, diff)
                    break

        # ---- 2. Login velocity ----
        logins_1h, logins_24h = 0, 0
        for ev in prior_events:
            if ev.get("event_type") in ("login", "new_device_login"):
                ev_dt = CausalFilter.parse_iso(ev["timestamp"])
                secs = (as_of_dt - ev_dt).total_seconds()
                if 0 <= secs <= 3600:
                    logins_1h += 1
                if 0 <= secs <= 86400:
                    logins_24h += 1

        # ---- 3. New device flag ----
        new_device_flag = float(any(
            ev.get("event_type") == "new_device_login"
            for ev in prior_events
            if (as_of_dt - CausalFilter.parse_iso(ev["timestamp"])).total_seconds() <= 3600
        ))

        # ---- 4. Payee added in session ----
        payee_added_flag = float(any(
            ev.get("event_type") == "payee_added"
            for ev in prior_events
            if (as_of_dt - CausalFilter.parse_iso(ev["timestamp"])).total_seconds() <= 1800
        ))

        # ---- 5. Amount z-score vs history ----
        prior_amounts = [t.get("amount", 0.0) for t in prior_txns]
        if len(prior_amounts) >= 3:
            mean_amt = float(np.mean(prior_amounts))
            std_amt  = float(np.std(prior_amounts)) + 1e-5
            amount_zscore = float((amount - mean_amt) / std_amt)
        else:
            # Cold start: use absolute thresholds
            if amount > 50000:
                amount_zscore = 4.0
            elif amount > 25000:
                amount_zscore = 2.8
            elif amount > 10000:
                amount_zscore = 1.5
            else:
                amount_zscore = 0.5
        amount_zscore = max(0.0, amount_zscore)

        # ---- 6. Dormancy flag (>30 days no txn) ----
        dormancy_flag = 0.0
        if prior_txns:
            latest_dt = max(CausalFilter.parse_iso(t["timestamp"]) for t in prior_txns)
            if (as_of_dt - latest_dt).total_seconds() > 30 * 86400:
                dormancy_flag = 1.0
        else:
            # No prior txns at all = effectively dormant
            dormancy_flag = 1.0

        # ---- 7. Flow imbalance ----
        inflows  = sum(t.get("amount", 0.0) for t in prior_txns if t.get("receiver_id") == account_id)
        outflows = sum(t.get("amount", 0.0) for t in prior_txns if t.get("sender_id") == account_id) + amount
        flow_imbalance = abs(inflows - outflows) / max(1.0, inflows + outflows)

        # ---- 8. Degree features ----
        n_txns    = len(prior_txns)
        in_count  = sum(1 for t in prior_txns if t.get("receiver_id") == account_id)
        out_count = sum(1 for t in prior_txns if t.get("sender_id") == account_id)
        total_deg = in_count + out_count + 1  # +1 for current pending txn

        in_degree_ratio  = in_count / max(1, total_deg)
        out_degree_ratio = out_count / max(1, total_deg)
        log_total_degree = float(np.log1p(total_deg))
        degree_vs_time_mean = min(10.0, float(n_txns + 1))

        # ---- 9. Extreme feature counts ----
        extreme_vals = [
            1 if flow_imbalance > 0.80 else 0,
            1 if amount_zscore > 2.5  else 0,
            1 if logins_1h >= 3       else 0,
            1 if dormancy_flag > 0    else 0,
            1 if setup_gap_minutes < 30 else 0,
            1 if new_device_flag > 0  else 0,
            1 if payee_added_flag > 0 else 0,
        ]
        extreme_feature_count_2 = float(sum(extreme_vals))
        extreme_feature_count_3 = float(sum(
            1 if flow_imbalance > 0.90 else 0,
            1 if amount_zscore > 3.5   else 0,
            1 if logins_1h >= 5        else 0,
        ) if False else sum([
            1 if flow_imbalance > 0.90 else 0,
            1 if amount_zscore > 3.5   else 0,
            1 if logins_1h >= 5        else 0,
        ]))

        # ---- 10. Fan-in/out ratio ----
        fan_in_out_ratio = min(5.0, (logins_1h + 1.0) / 2.0)

        return {
            "setup_gap_minutes":       setup_gap_minutes,
            "logins_1h":               float(logins_1h),
            "logins_24h":              float(logins_24h),
            "new_device_flag":         new_device_flag,
            "payee_added_flag":        payee_added_flag,
            "amount_zscore":           amount_zscore,
            "dormancy_flag":           dormancy_flag,
            "flow_imbalance":          flow_imbalance,
            "fan_in_out_ratio":        fan_in_out_ratio,
            "degree_vs_time_mean":     degree_vs_time_mean,
            "in_degree_ratio":         in_degree_ratio,
            "out_degree_ratio":        out_degree_ratio,
            "log_total_degree":        log_total_degree,
            "extreme_feature_count_2": extreme_feature_count_2,
            "extreme_feature_count_3": extreme_feature_count_3,
            "feature_mean":            float(amount / 10000.0),
            "feature_std":             float(amount_zscore),
        }

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_sequence(
        self,
        account_id: str,
        amount: float,
        as_of_timestamp: str,
        events: List[Dict[str, Any]],
        historical_txns: List[Dict[str, Any]]
    ) -> Tuple[float, List[Dict[str, Any]]]:

        feats = self.extract_features(account_id, amount, as_of_timestamp, events, historical_txns)

        # ---- XGBoost inference ----
        model_prob = None
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
            feats["feature_std"],
        ]])

        if self.model is not None:
            try:
                probs = self.model.predict_proba(feature_vector)[0]
                model_prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            except Exception as e:
                print(f"[SequenceRiskEngine] XGBoost predict error: {e}")

        score = model_prob if model_prob is not None else 0.05

        # ---- SHAP attribution ----
        shap_factors = shap_engine.explain(
            feature_vector=feature_vector,
            feature_values_dict=feats,
            top_n=4
        )
        # Convert to unified factor format
        factors: List[Dict[str, Any]] = [
            {
                "feature": sf["feature"],
                "impact":  sf["impact"],
                "explanation": sf["explanation"],
            }
            for sf in shap_factors
        ]

        # ---- Hard rule boosts (safety net on top of XGB) ----
        if feats["setup_gap_minutes"] < 5.0:
            score = max(score, min(0.98, score + 0.50))
            if not any(f["feature"] == "setup_gap_minutes" for f in factors):
                factors.insert(0, {
                    "feature": "setup_to_action_gap",
                    "impact": 0.50,
                    "explanation": (
                        f"CRITICAL: Credential/payee change occurred "
                        f"{int(feats['setup_gap_minutes'] * 60)}s before this transfer — "
                        f"strong ATO indicator."
                    ),
                })
        elif feats["setup_gap_minutes"] < 60.0:
            score = max(score, min(0.98, score + 0.25))

        if feats["amount_zscore"] > 3.0:
            score = max(score, min(0.98, score + 0.30))

        if feats["logins_1h"] >= 4:
            score = max(score, min(0.98, score + 0.20))

        if feats["dormancy_flag"] > 0 and amount > 5000:
            score = max(score, min(0.98, score + 0.20))
            if not any(f["feature"] == "dormancy_reactivation" for f in factors):
                factors.append({
                    "feature": "dormancy_reactivation",
                    "impact": 0.20,
                    "explanation": (
                        "Account reactivated after >30 days dormancy with "
                        f"a ${amount:,.0f} transfer — dormancy-then-burst pattern."
                    ),
                })

        if feats["new_device_flag"] > 0 and feats["setup_gap_minutes"] < 120:
            score = max(score, min(0.98, score + 0.15))
            factors.append({
                "feature": "new_device_login",
                "impact": 0.15,
                "explanation": (
                    "Transaction initiated from a new/unrecognised device "
                    "within 1 hour of account modification."
                ),
            })

        if feats["payee_added_flag"] > 0:
            score = max(score, min(0.98, score + 0.18))
            factors.append({
                "feature": "payee_added_in_session",
                "impact": 0.18,
                "explanation": (
                    "Payee added within 30 minutes of this transfer — "
                    "same-session payee-add pattern is a top ATO indicator."
                ),
            })

        # De-duplicate factors, keep highest absolute impact per feature
        seen = {}
        for f in factors:
            key = f["feature"]
            if key not in seen or abs(f["impact"]) > abs(seen[key]["impact"]):
                seen[key] = f
        deduped = sorted(seen.values(), key=lambda x: abs(x["impact"]), reverse=True)

        return min(1.0, max(0.01, round(score, 4))), deduped[:6]


sequence_risk_engine = SequenceRiskEngine()
