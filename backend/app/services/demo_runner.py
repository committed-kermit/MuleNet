import asyncio
import json
from typing import AsyncGenerator, Optional
from datetime import datetime, timedelta
import random

from app.core.memory_graph import memory_graph
from app.services.sequence_lens import sequence_risk_engine
from app.services.network_lens import network_risk_engine
from app.services.context_lens import context_risk_engine
from app.services.anomaly_engine import anomaly_engine
from app.services.typology_detector import typology_detector
from app.services.fusion_engine import risk_fusion_engine
from app.services.explainability import explainability_engine

class DemoRunner:
    """
    Asynchronous event generator for the live pre-commitment stream and simulated attacks.
    """
    def __init__(self):
        self.injected_queue: asyncio.Queue = asyncio.Queue()

    async def inject_scenario(self, scenario_type: str, account_id: Optional[str] = None, amount: Optional[float] = None):
        sender = account_id or f"BANK01_ACC{random.randint(1000, 9999)}"
        amt = amount or 48500.0
        now_iso = datetime.utcnow().isoformat() + "Z"

        if scenario_type == "ATO":
            # Seed rapid profile change and logins
            memory_graph.record_event(sender, "password_reset", (datetime.utcnow() - timedelta(minutes=2)).isoformat() + "Z")
            memory_graph.record_event(sender, "mobile_number_change", (datetime.utcnow() - timedelta(minutes=1)).isoformat() + "Z")
            memory_graph.record_event(sender, "payee_added", (datetime.utcnow() - timedelta(seconds=45)).isoformat() + "Z")
            for _ in range(5):
                memory_graph.record_event(sender, "login", now_iso)
            receiver = f"BANK04_MULE{random.randint(500, 999)}"

        elif scenario_type == "SMURFING":
            # Smurfing cluster to hub
            receiver = "BANK01_HUB900"
            amt = 9950.0
            memory_graph.record_event(sender, "login", now_iso)

        elif scenario_type == "RING_WASH":
            receiver = "BANK02_RING_A"
            amt = 24800.0
            memory_graph.record_event(sender, "login", now_iso)

        else:
            receiver = f"BANK03_ACC{random.randint(2000, 9999)}"

        # Compute dynamic scores
        events = memory_graph.get_events(sender)
        txns = memory_graph.get_transactions(sender)

        seq_score, seq_factors = sequence_risk_engine.score_sequence(sender, amt, now_iso, events, txns)
        net_score, net_factors = network_risk_engine.score_network(sender, receiver, now_iso, memory_graph)
        ctx_score, ctx_factors = context_risk_engine.score_context(amt, "USD", receiver, "WIRE")
        anom_score = anomaly_engine.score_anomaly(amt, 4.0, 1.0)

        fused_score, tier, action = risk_fusion_engine.fuse_scores(seq_score, net_score, ctx_score, anom_score)
        
        ego_data = memory_graph.get_ego_subgraph(sender, now_iso)
        typologies_raw = typology_detector.detect_typologies(amt, 1.0, len(ego_data.get("nodes", [])), True)
        typologies = [{"name": t["name"], "evidence": t["evidence"]} for t in typologies_raw]
        if not typologies:
            typologies = [{"name": f"Simulated {scenario_type} Attack", "evidence": f"Injected synthetic {scenario_type} signature."}]

        shap_factors = explainability_engine.format_explanations(seq_factors, net_factors, ctx_factors)

        scenario_event = {
            "transaction_id": f"INJ-{random.randint(10000, 99999)}",
            "timestamp": now_iso,
            "sender_id": sender,
            "receiver_id": receiver,
            "amount": amt,
            "currency": "USD",
            "fused_score": fused_score,
            "risk_tier": tier.value if hasattr(tier, "value") else str(tier),
            "recommended_action": action.value if hasattr(action, "value") else str(action),
            "lenses": {
                "sequence_score": seq_score,
                "network_score": net_score,
                "context_score": ctx_score,
                "anomaly_score": anom_score
            },
            "typologies": typologies,
            "shap_factors": [
                {"feature": f.feature, "impact": f.impact, "explanation": f.explanation}
                for f in shap_factors
            ]
        }
        await self.injected_queue.put(scenario_event)

    async def stream_transactions(self) -> AsyncGenerator[str, None]:
        while True:
            if not self.injected_queue.empty():
                event_data = await self.injected_queue.get()
            else:
                is_risky = (random.random() < 0.18)
                now_iso = datetime.utcnow().isoformat() + "Z"

                if is_risky:
                    sender = random.choice(["BANK01_ACC1042", "BANK01_HUB900", f"BANK01_RISK{random.randint(10, 99)}"])
                    receiver = random.choice(["BANK04_ACC9011", "BANK04_SINK99", "BANK02_RING_A"])
                    amt = round(random.uniform(8500, 49900), 2)
                else:
                    sender = f"BANK01_LEGIT_{random.randint(0, 9):02d}"
                    receiver = f"BANK02_LEGIT_{random.randint(0, 9):02d}"
                    amt = round(random.uniform(25, 1200), 2)

                events = memory_graph.get_events(sender)
                txns = memory_graph.get_transactions(sender)

                seq_score, seq_factors = sequence_risk_engine.score_sequence(sender, amt, now_iso, events, txns)
                net_score, net_factors = network_risk_engine.score_network(sender, receiver, now_iso, memory_graph)
                ctx_score, ctx_factors = context_risk_engine.score_context(amt, "USD", receiver, "ACH")
                anom_score = anomaly_engine.score_anomaly(amt, 1.0, 50.0)

                fused_score, tier, action = risk_fusion_engine.fuse_scores(seq_score, net_score, ctx_score, anom_score)
                
                ego_data = memory_graph.get_ego_subgraph(sender, now_iso)
                typologies_raw = typology_detector.detect_typologies(
                    amt,
                    1.0 if is_risky else 500.0,
                    len(ego_data.get("nodes", [])),
                    (net_score > 0.6)
                )
                typologies = [{"name": t["name"], "evidence": t["evidence"]} for t in typologies_raw]
                shap_factors = explainability_engine.format_explanations(seq_factors, net_factors, ctx_factors)

                event_data = {
                    "transaction_id": f"TXN-{random.randint(10000, 99999)}",
                    "timestamp": now_iso,
                    "sender_id": sender,
                    "receiver_id": receiver,
                    "amount": amt,
                    "currency": "USD",
                    "fused_score": fused_score,
                    "risk_tier": tier.value if hasattr(tier, "value") else str(tier),
                    "recommended_action": action.value if hasattr(action, "value") else str(action),
                    "lenses": {
                        "sequence_score": seq_score,
                        "network_score": net_score,
                        "context_score": ctx_score,
                        "anomaly_score": anom_score
                    },
                    "typologies": typologies,
                    "shap_factors": [
                        {"feature": f.feature, "impact": f.impact, "explanation": f.explanation}
                        for f in shap_factors
                    ]
                }

            yield f"data: {json.dumps(event_data)}\n\n"
            await asyncio.sleep(2.5)

demo_runner = DemoRunner()
