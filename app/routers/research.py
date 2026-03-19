"""
app/routers/research.py
────────────────────────
Research retrieval endpoints — standalone access to the RAG pipeline.

Doctors can query for research papers independently of a chat.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ResearchSuggestion
from app.services.rag_service import get_research_suggestions, search_similar_research
from app.services.llm_service import llm_service

router = APIRouter(prefix="/research", tags=["Research"])


@router.get("/search", response_model=list[ResearchSuggestion])
async def search_research(
    query: str = Query(..., description="Clinical question or condition to search for"),
    top_k: int = Query(5, ge=1, le=10),
    min_year: int = Query(2015, ge=2000),
    evidence_levels: list[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search for research papers relevant to a clinical query.
    Uses the RAG pipeline: vector search + LLM TL;DR generation.
    """
    suggestions = await get_research_suggestions(
        clinical_text=query,
        llm_service=llm_service,
        top_k=top_k,
    )
    return suggestions


@router.get("/similar-cases")
async def find_similar_cases(
    query: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """
    Find clinically similar de-identified cases from the case database.
    (Requires the QDRANT_COLLECTION_CASES to be populated.)
    """
    from app.config import settings
    results = search_similar_research(query, top_k=5)
    return {"cases": results, "note": "De-identified case data from institutional database"}
