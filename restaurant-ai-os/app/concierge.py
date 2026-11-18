from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from slai.agents.guest_intake import GuestIntakeAgent
from slai.agents.qualifier import QualifierAgent

from .security import Principal, require

router = APIRouter()
qualifier = QualifierAgent()
assistant = GuestIntakeAgent(qualifier=qualifier)

class IntakeIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

@router.post("/concierge/intake")
def intake(
    body: IntakeIn,
    _: Principal = Depends(require("res:write")),
):
    state = qualifier.extract(body.message)
    reply = assistant.respond(state)

    return {
        "reply": reply,
        "state": state.to_dict(),
        "reservation_created": False,
    }
