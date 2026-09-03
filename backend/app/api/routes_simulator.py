from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.demo_runner import demo_runner

router = APIRouter(tags=["Attack Simulator"])

class SimulationRequest(BaseModel):
    scenario_type: str = "ATO" # "ATO" | "SMURFING" | "RING_WASH"
    account_id: Optional[str] = None
    amount: Optional[float] = 49500.0

@router.post("/simulator/inject")
async def inject_simulation(payload: SimulationRequest):
    """
    Injects an adversarial attack pattern into the live scoring stream.
    """
    await demo_runner.inject_scenario(
        scenario_type=payload.scenario_type,
        account_id=payload.account_id,
        amount=payload.amount
    )
    return {
        "status": "INJECTED",
        "scenario_type": payload.scenario_type,
        "message": f"Successfully injected {payload.scenario_type} attack pattern."
    }
