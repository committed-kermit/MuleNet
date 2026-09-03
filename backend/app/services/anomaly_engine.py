from typing import Dict, Any, List
from sklearn.ensemble import IsolationForest
import numpy as np

class AnomalyEngine:
    """
    Unsupervised Isolation Forest novelty detector.
    """
    def __init__(self):
        self.iso_forest = IsolationForest(contamination=0.03, random_state=42)
        # Pre-fit on baseline reference points
        dummy_data = np.array([
            [100.0, 1.0, 0.0],
            [250.0, 2.0, 0.0],
            [500.0, 1.0, 0.0],
            [1200.0, 3.0, 0.0],
            [50.0, 1.0, 0.0]
        ])
        self.iso_forest.fit(dummy_data)

    def score_anomaly(self, amount: float, velocity: float, setup_gap: float) -> float:
        feat = np.array([[amount, velocity, setup_gap]])
        raw_score = self.iso_forest.score_samples(feat)[0]
        # Normalize to [0, 1] where 1 is highest anomaly
        norm_score = max(0.0, min(1.0, float(-raw_score * 1.5)))
        return round(norm_score, 4)

anomaly_engine = AnomalyEngine()
