from typing import List, Dict, Any
from app.models.schema import ShapFactor

class ExplainabilityEngine:
    """
    Translates ML feature impacts and graph attention signals
    into investigator-ready plain-language reasons.
    """
    @staticmethod
    def format_explanations(
        sequence_factors: List[Dict[str, Any]],
        network_factors: List[Dict[str, Any]],
        context_factors: List[Dict[str, Any]]
    ) -> List[ShapFactor]:
        all_factors = sequence_factors + network_factors + context_factors
        # Sort by absolute impact descending
        sorted_factors = sorted(all_factors, key=lambda x: abs(x.get("impact", 0.0)), reverse=True)

        return [
            ShapFactor(
                feature=f.get("feature", f.get("signal", "unknown")),
                impact=round(float(f.get("impact", f.get("weight", 0.0))), 3),
                explanation=f.get("explanation", "Contributing risk factor.")
            )
            for f in sorted_factors[:4]
        ]

explainability_engine = ExplainabilityEngine()
