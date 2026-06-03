"""Optional FastAPI server for table allocation recommendations."""

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tableopt.models import FloorState, Party, PartyType
from tableopt.optimizer import AssignmentScore, ScoringConfig, recommend_assignment
from tableopt.priors import PriorDistributions

app = FastAPI(
    title="Table Allocation API",
    description="REST API for table allocation recommendations",
    version="0.1.0",
)

# Global state (in production, use proper state management)
_priors: Optional[PriorDistributions] = None
_config: ScoringConfig = ScoringConfig()


class RecommendationRequest(BaseModel):
    """Request for table recommendation."""

    floor_state: FloorState
    party_id: str
    party_size: int
    party_type: str = "walk_in"
    top_k: int = 3


class RecommendationResponse(BaseModel):
    """Response with table recommendations."""

    party_id: str
    party_size: int
    recommended_table: str
    score: float
    alternatives: list[dict]
    rationale: str
    timestamp: datetime


@app.on_event("startup")
async def load_priors():
    """Load priors on startup."""
    global _priors
    # In production, load from environment variable or config
    # For now, require calling /config endpoint first
    pass


@app.post("/config/priors")
async def set_priors(priors: PriorDistributions):
    """
    Set the prior distributions.

    This should be called once at startup with the learned priors.
    """
    global _priors
    _priors = priors
    return {"status": "ok", "message": "Priors updated"}


@app.post("/recommend", response_model=RecommendationResponse)
async def get_recommendation(request: RecommendationRequest):
    """
    Get table assignment recommendation for a party.

    Returns the top recommended table with score breakdown.
    """
    if _priors is None:
        raise HTTPException(status_code=500, detail="Priors not loaded. Call /config/priors first")

    # Create party
    party = Party(
        id=request.party_id,
        size=request.party_size,
        type=PartyType(request.party_type),
    )

    # Get recommendations
    recommendations = recommend_assignment(
        party, request.floor_state, _priors, _config, request.top_k
    )

    if not recommendations or not recommendations[0].is_feasible:
        raise HTTPException(status_code=404, detail="No feasible table assignments available")

    top = recommendations[0]

    # Format alternatives
    alternatives = []
    for rec in recommendations[1:]:
        if rec.is_feasible:
            alternatives.append(
                {
                    "table_id": rec.table_id,
                    "score": rec.total_score,
                    "rationale": rec.rationale,
                }
            )

    return RecommendationResponse(
        party_id=request.party_id,
        party_size=request.party_size,
        recommended_table=top.table_id,
        score=top.total_score,
        alternatives=alternatives,
        rationale=top.rationale,
        timestamp=datetime.now(),
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "priors_loaded": _priors is not None,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
