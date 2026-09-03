"""
SHAP Explainability Engine — Person 3 (ML - Sequence & SHAP)

Provides TreeExplainer-based SHAP values for the XGBoost sequence model
and formats them into investigator-ready ranked factor lists.

Responsibilities:
- Fit / cache a shap.TreeExplainer on the loaded XGBoost model
- Compute per-feature SHAP values for a single feature vector
- Map raw SHAP values to human-readable explanations
- Merge with GAT attention signals from network lens
- Return top-N ranked ShapFactor objects for the dossier
"""

import numpy as np
from typing import List, Dict, Any, Optional

try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    print("[SHAPEngine] shap not installed — falling back to rule-based explanations.")


# Human-readable templates for each feature
FEATURE_EXPLANATIONS = {
    "flow_imbalance": (
        "Flow imbalance of {val:.2f}: outflows significantly exceed inflows, "
        "consistent with fund-forwarding mule behaviour."
    ),
    "fan_in_out_ratio": (
        "Fan-in/out ratio {val:.2f}: disproportionate counterparty volume ratio "
        "suggesting aggregation or dispersal activity."
    ),
    "degree_vs_time_mean": (
        "Degree-vs-time mean {val:.2f}: unusually high transaction frequency "
        "relative to account age."
    ),
    "in_degree_ratio": (
        "In-degree ratio {val:.2f}: high proportion of incoming counterparties "
        "— potential collection hub pattern."
    ),
    "out_degree_ratio": (
        "Out-degree ratio {val:.2f}: high proportion of outgoing counterparties "
        "— potential dispersal node pattern."
    ),
    "log_total_degree": (
        "Log total degree {val:.2f}: account connectivity significantly above "
        "the legitimate baseline."
    ),
    "extreme_feature_count_2": (
        "{val:.0f} features in extreme percentile range — multi-signal anomaly "
        "combination detected."
    ),
    "extreme_feature_count_3": (
        "{val:.0f} features in extreme-extreme percentile range — rare outlier "
        "pattern associated with confirmed mule accounts."
    ),
    "feature_mean": (
        "Mean feature value {val:.3f} elevated — overall behavioural profile "
        "skewed towards high-risk region."
    ),
    "feature_std": (
        "Feature std {val:.3f}: high variance across behavioural signals — "
        "erratic activity pattern."
    ),
    "setup_gap_minutes": (
        "Setup-to-action gap {val:.1f} min: credential/payee modification occurred "
        "shortly before transfer — ATO indicator."
    ),
    "logins_1h": (
        "{val:.0f} logins in past hour: login velocity spike preceding transaction."
    ),
    "logins_24h": (
        "{val:.0f} logins in past 24 hours: elevated session activity over the day."
    ),
    "amount_zscore": (
        "Amount z-score {val:.1f}: transfer is {val:.1f}σ above account's historical mean."
    ),
    "dormancy_flag": (
        "Account reactivated after >30 days dormancy with a high-value transfer."
    ),
}


class SHAPExplainabilityEngine:
    """
    Wraps shap.TreeExplainer for XGBoost sequence model.
    Falls back to magnitude-ranked rule explanations when SHAP unavailable.
    """

    FEATURE_ORDER = [
        "flow_imbalance", "fan_in_out_ratio", "degree_vs_time_mean",
        "in_degree_ratio", "out_degree_ratio", "log_total_degree",
        "extreme_feature_count_2", "extreme_feature_count_3",
        "feature_mean", "feature_std"
    ]

    def __init__(self):
        self._explainer = None  # lazy-init after model is loaded

    def init_explainer(self, xgb_model):
        """Call this once after the XGBoost model is loaded."""
        if not SHAP_AVAILABLE:
            return
        try:
            self._explainer = shap.TreeExplainer(
                xgb_model,
                feature_perturbation="tree_path_dependent"
            )
            print("[SHAPEngine] TreeExplainer initialised.")
        except Exception as e:
            print(f"[SHAPEngine] TreeExplainer init failed: {e}")

    def explain(
        self,
        feature_vector: np.ndarray,
        feature_values_dict: Dict[str, float],
        top_n: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Computes SHAP values for a single sample and returns top_n factors.

        Parameters
        ----------
        feature_vector   : shape (1, n_features) numpy array matching FEATURE_ORDER
        feature_values_dict : raw feature values keyed by name (for explanation text)
        top_n            : number of top factors to return

        Returns
        -------
        List of dicts: {feature, impact, direction, explanation}
        """
        if SHAP_AVAILABLE and self._explainer is not None:
            return self._shap_explain(feature_vector, feature_values_dict, top_n)
        return self._rule_explain(feature_values_dict, top_n)

    # ------------------------------------------------------------------
    # SHAP path
    # ------------------------------------------------------------------

    def _shap_explain(
        self,
        feature_vector: np.ndarray,
        feature_values_dict: Dict[str, float],
        top_n: int
    ) -> List[Dict[str, Any]]:
        try:
            shap_values = self._explainer.shap_values(feature_vector)
            # For binary classifier: shap_values is list [class0, class1]
            if isinstance(shap_values, list) and len(shap_values) == 2:
                sv = shap_values[1][0]   # positive class SHAP for sample 0
            elif isinstance(shap_values, np.ndarray) and shap_values.ndim == 2:
                sv = shap_values[0]
            else:
                sv = np.array(shap_values).flatten()

            n_feats = min(len(sv), len(self.FEATURE_ORDER))
            ranked = sorted(
                range(n_feats),
                key=lambda i: abs(sv[i]),
                reverse=True
            )[:top_n]

            factors = []
            for i in ranked:
                fname = self.FEATURE_ORDER[i]
                impact = float(sv[i])
                val = feature_values_dict.get(fname, float(feature_vector[0, i]))
                explanation = self._render_explanation(fname, val, impact)
                factors.append({
                    "feature": fname,
                    "impact": round(impact, 4),
                    "direction": "risk_increase" if impact > 0 else "risk_decrease",
                    "explanation": explanation
                })
            return factors

        except Exception as e:
            print(f"[SHAPEngine] SHAP explain error: {e}")
            return self._rule_explain(feature_values_dict, top_n)

    # ------------------------------------------------------------------
    # Fallback: magnitude-ranked rule explanations
    # ------------------------------------------------------------------

    def _rule_explain(
        self,
        feature_values_dict: Dict[str, float],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """
        When SHAP is unavailable, rank features by normalised deviation
        from safe baseline and generate templated explanations.
        """
        BASELINES = {
            "flow_imbalance": 0.15,
            "fan_in_out_ratio": 1.0,
            "degree_vs_time_mean": 1.5,
            "in_degree_ratio": 0.4,
            "out_degree_ratio": 0.4,
            "log_total_degree": 1.0,
            "extreme_feature_count_2": 0.0,
            "extreme_feature_count_3": 0.0,
            "feature_mean": 0.05,
            "feature_std": 0.5,
        }
        scored = []
        for fname, baseline in BASELINES.items():
            val = feature_values_dict.get(fname, 0.0)
            deviation = abs(val - baseline) / max(abs(baseline), 0.01)
            scored.append((fname, val, deviation))

        scored.sort(key=lambda x: x[2], reverse=True)
        factors = []
        for fname, val, dev in scored[:top_n]:
            impact = round(min(dev * 0.2, 0.6), 4)
            explanation = self._render_explanation(fname, val, impact)
            factors.append({
                "feature": fname,
                "impact": impact,
                "direction": "risk_increase" if impact > 0 else "risk_decrease",
                "explanation": explanation
            })
        return factors

    # ------------------------------------------------------------------

    def _render_explanation(self, fname: str, val: float, impact: float) -> str:
        template = FEATURE_EXPLANATIONS.get(fname)
        if template:
            try:
                return template.format(val=val, impact=impact)
            except Exception:
                return f"{fname} = {val:.3f} (SHAP impact {impact:+.3f})"
        return f"{fname} contributed {impact:+.3f} to risk score (value={val:.3f})."


shap_engine = SHAPExplainabilityEngine()
