import asyncio
import json
from typing import AsyncGenerator
from datetime import datetime
import random

class DemoRunner:
    """
    Asynchronous event generator for the live replay stream.
    """
    def __init__(self):
        self.injected_queue: asyncio.Queue = asyncio.Queue()

    async def inject_scenario(self, scenario_type: str, account_id: str, amount: float):
        scenario_event = {
            "transaction_id": f"INJ-{random.randint(10000, 99999)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sender_id": account_id or f"BANK01_ACC{random.randint(1000, 9999)}",
            "receiver_id": f"BANK04_ACC{random.randint(5000, 9999)}",
            "amount": amount or 49500.0,
            "currency": "USD",
            "fused_score": 0.93 if scenario_type == "ATO" else 0.86,
            "risk_tier": "CRITICAL",
            "recommended_action": "HOLD_FOR_REVIEW",
            "lenses": {
                "sequence_score": 0.95,
                "network_score": 0.88,
                "context_score": 0.75,
                "anomaly_score": 0.82
            },
            "typologies": [
                {
                    "name": f"Simulated {scenario_type} Attack",
                    "evidence": f"Synthetic injected {scenario_type} pattern triggered instant Level 2 alert."
                }
            ],
            "shap_factors": [
                {
                    "feature": "injected_attack_signature",
                    "impact": 0.55,
                    "explanation": f"Pattern matches known {scenario_type} risk profile."
                }
            ]
        }
        await self.injected_queue.put(scenario_event)

    async def stream_transactions(self) -> AsyncGenerator[str, None]:
        while True:
            # Check if there is an injected scenario
            if not self.injected_queue.empty():
                event_data = await self.injected_queue.get()
            else:
                # Generate baseline transaction
                is_risky = (random.random() < 0.15)
                amt = random.uniform(5000, 50000) if is_risky else random.uniform(20, 1500)
                score = random.uniform(0.75, 0.95) if is_risky else random.uniform(0.02, 0.25)
                tier = "CRITICAL" if score > 0.85 else ("HIGH" if score > 0.60 else ("MEDIUM" if score > 0.30 else "LOW"))
                action = "HOLD_FOR_REVIEW" if tier == "CRITICAL" else ("STEP_UP_AUTH" if tier == "HIGH" else ("SOFT_CHALLENGE" if tier == "MEDIUM" else "ALLOW"))

                event_data = {
                    "transaction_id": f"TXN-{random.randint(10000, 99999)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "sender_id": f"BANK01_ACC{random.randint(1000, 9999)}",
                    "receiver_id": f"BANK02_ACC{random.randint(1000, 9999)}",
                    "amount": round(amt, 2),
                    "currency": "USD",
                    "fused_score": round(score, 2),
                    "risk_tier": tier,
                    "recommended_action": action,
                    "lenses": {
                        "sequence_score": round(score * random.uniform(0.9, 1.1), 2),
                        "network_score": round(score * random.uniform(0.8, 1.0), 2),
                        "context_score": round(score * random.uniform(0.7, 0.9), 2),
                        "anomaly_score": round(score * random.uniform(0.85, 1.05), 2),
                    },
                    "typologies": [
                        {"name": "Rapid Pass-Through", "evidence": "Funds forwarded quickly."}
                    ] if is_risky else [],
                    "shap_factors": [
                        {"feature": "setup_gap", "impact": 0.35, "explanation": "Rapid modification before transfer."}
                    ] if is_risky else []
                }

            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(2.5)

demo_runner = DemoRunner()
