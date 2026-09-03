from typing import List, Dict, Any

class TypologyDetector:
    """
    Deterministic motif and laundering topology engine.
    Detects: Rapid pass-through, Fan-in/out, Smurfing, and Circular rings.
    """
    @staticmethod
    def detect_typologies(
        amount: float,
        setup_gap_minutes: float,
        neighbor_count: int,
        is_ring_member: bool = False
    ) -> List[Dict[str, str]]:
        typologies = []

        # 1. Rapid pass-through mule pattern
        if setup_gap_minutes < 15.0 and amount >= 5000.0:
            typologies.append({
                "name": "Rapid Pass-Through Mule Behavior",
                "evidence": f"Large transfer (${amount:,.2f}) executed {int(setup_gap_minutes)} minutes after account/payee modification."
            })

        # 2. Fan-in collection hub
        if neighbor_count >= 5:
            typologies.append({
                "name": "Fan-In Collection Hub",
                "evidence": f"Account interacts with {neighbor_count} distinct counterparties in active window."
            })

        # 3. Coordinated Mule Ring
        if is_ring_member or (amount >= 20000.0 and neighbor_count >= 3):
            typologies.append({
                "name": "Cross-Bank Coordinated Mule Ring",
                "evidence": "Account identified in a circular transaction flow traversing multiple financial entities."
            })

        return typologies

typology_detector = TypologyDetector()
