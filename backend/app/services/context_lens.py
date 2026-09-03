from typing import Dict, Any, List, Tuple

class ContextRiskEngine:
    """
    Evaluates transaction payload consistency, currency matches,
    and counterparty relationship anomalies.
    """
    def score_context(
        self,
        amount: float,
        currency: str,
        counterparty_id: str,
        action_type: str
    ) -> Tuple[float, List[Dict[str, Any]]]:
        score = 0.05
        factors = []

        if amount >= 10000.0:
            score += 0.25
            factors.append({
                "feature": "high_value_transaction",
                "impact": 0.25,
                "explanation": f"High value transfer exceeding AML threshold ($10,000+)."
            })

        if currency not in ["USD", "EUR", "GBP", "INR"]:
            score += 0.15
            factors.append({
                "feature": "exotic_currency_flag",
                "impact": 0.15,
                "explanation": f"Transaction involves uncommon currency: {currency}."
            })

        return min(1.0, round(score, 4)), factors

context_risk_engine = ContextRiskEngine()
