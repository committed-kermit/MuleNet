from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from app.services.demo_runner import demo_runner

router = APIRouter(tags=["Live Stream & Replay"])

@router.get("/demo/stream")
async def stream_demo_transactions():
    """
    SSE stream of live incoming transactions with graduated decisions.
    """
    return EventSourceResponse(demo_runner.stream_transactions())
