"""
app/schemas/ai.py
──────────────────
All AI-related Pydantic schemas for CLINICORE.

These are the core structured response types returned by the LLM engine
and the RAG (PubMed retrieval) pipeline.
"""

from pydantic import BaseModel


class ResearchSuggestion(BaseModel):
    pubmed_id: str
    title: str
    authors: str
    journal: str
    year: int
    abstract_snippet: str
    tldr: str  # AI-generated 2-3 sentence summary
    relevance_score: float  # 0.0 - 1.0
    evidence_level: str  # "rct", "meta_analysis", "cohort", "case_report", "guideline"
    url: str


class DiagnosticGap(BaseModel):
    gap_type: str  # "missing_differential", "contradictory_finding", "incomplete_history", "anchoring_bias"
    description: str
    suggested_action: str
    severity: str  # "low", "medium", "high"


class UncertaintyFactor(BaseModel):
    factor: str  # e.g., "Limited imaging views"
    impact: str  # "low", "medium", "high"
    recommendation: str


class BiasAlert(BaseModel):
    bias_type: str  # "anchoring", "availability", "confirmation", "demographic", "premature_closure"
    description: str
    alternative_to_consider: str


class CounterfactualInsight(BaseModel):
    variable: str  # e.g., "HPV vaccination status"
    current_value: str
    alternative_value: str
    impact_on_diagnosis: str


class AIResponse(BaseModel):
    """
    The structured response returned by the LLM after clinical reasoning.
    This is the core explainability output of CLINICORE.
    """
    primary_suggestion: str
    confidence: str  # "low" | "moderate" | "high"
    reasoning_steps: list[str]  # step-by-step chain-of-thought
    differential_diagnoses: list[str]
    missing_information: list[str]  # what the AI wishes it knew
    red_flags: list[str]  # urgent findings requiring immediate action
    recommended_next_steps: list[str]
    uncertainty_factors: list[UncertaintyFactor]
    diagnostic_gaps: list[DiagnosticGap]
    bias_alerts: list[BiasAlert]
    counterfactual_insights: list[CounterfactualInsight]
    research_suggestions: list[ResearchSuggestion] = []
    model_used: str
    knowledge_base_version: str  # ISO date of last knowledge update
    disclaimer: str = (
        "This AI output is for clinical decision support only and does not "
        "constitute a diagnosis. Always apply clinical judgment."
    )


__all__ = [
    "ResearchSuggestion",
    "DiagnosticGap",
    "UncertaintyFactor",
    "BiasAlert",
    "CounterfactualInsight",
    "AIResponse",
]
