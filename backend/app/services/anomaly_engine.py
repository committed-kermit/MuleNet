import os
from typing import Dict, Any, List
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

class AnomalyEngine:
    """
    Unsupervised Isolation Forest novelty detector for identifying statistical outliers.
    """
    def __init__(self):
        self.iso_forest = None
        self.scaler = None
        self._load_model()

    def _load_model(self):
        artifact_dirs = [
            os.path.abspath("backend/artifacts"),
            os.path.abspath("MuleNet/backend/artifacts"),
            os.path.abspath("artifacts")
        ]
        for ad in artifact_dirs:
            iso_p = os.path.join(ad, "isolation_forest.joblib")
            scaler_p = os.path.join(ad, "anomaly_scaler.joblib")
            if os.path.exists(iso_p) and os.path.exists(scaler_p):
                try:
                    self.iso_forest = joblib.load(iso_p)
                    self.scaler = joblib.load(scaler_p)
                    print(f"[AnomalyEngine] Loaded IsolationForest from {iso_p}")
                    break
                except Exception as e:
                    print(f"[AnomalyEngine] Warning loading anomaly model: {e}")

        if self.iso_forest is None:
            self.iso_forest = IsolationForest(contamination=0.03, random_state=42)
            dummy_data = np.array([
                [1.0, 0.1, 1.0],
                [2.0, 0.2, 1.5],
                [1.5, 0.05, 2.0],
                [0.8, 0.3, 0.5],
                [1.2, 0.1, 1.2]
            ])
            self.iso_forest.fit(dummy_data)

    def score_anomaly(self, amount: float, velocity: float, setup_gap: float) -> float:
        try:
            # Map input parameters to features
            deg_vs_time = min(10.0, velocity * 2.0)
            flow_imb = 0.9 if setup_gap < 5.0 else 0.2
            log_tot_deg = float(np.log1p(velocity * 3.0))

            feat = np.array([[deg_vs_time, flow_imb, log_tot_deg]])
            if self.scaler is not None:
                feat_scaled = self.scaler.transform(feat)
            else:
                feat_scaled = feat

            raw_score = self.iso_forest.score_samples(feat_scaled)[0]
            # Convert raw anomaly score to [0, 1] range
            norm_score = max(0.0, min(1.0, float((-raw_score - 0.2) * 2.5)))
            return round(norm_score, 4)
        except Exception as e:
            print(f"[AnomalyEngine] score_anomaly error: {e}")
            return 0.12

anomaly_engine = AnomalyEngine()
