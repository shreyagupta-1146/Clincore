"""
app/services/llm_service.py
────────────────────────────
The AI Brain of CLINICORE.

Orchestrates:
1. Building the clinical reasoning prompt (system + user + image)
2. Calling Claude (primary) with Gemini fallback
3. Streaming response support
4. Parsing the structured JSON response into AIResponse schema
5. Post-processing: source attribution, bias checks, uncertainty factors

The system prompt is the most critical part — it instructs the LLM to
behave as a clinical decision support tool, not a diagnostic oracle.
"""

import json
import base64
import re
from typing import AsyncIterator, Optional
from loguru import logger

import anthropic
import google.generativeai as genai

from app.config import settings
from app.schemas.ai import (
    AIResponse,
    ResearchSuggestion,
    DiagnosticGap,
    UncertaintyFactor,
    BiasAlert,
    CounterfactualInsight,
)

# ── System Prompt ─────────────────────────────────────────────────────────────
CLINICAL_SYSTEM_PROMPT = """You are CLINICORE, a clinical decision support AI assistant designed to augment — never replace — the diagnostic reasoning of medical professionals.

## Your Role
You help clinicians think more deeply, identify potential gaps in reasoning, and access relevant evidence. You do NOT diagnose patients. You support the clinician's own diagnostic process.

## Response Format
You MUST respond ONLY with a valid JSON object matching this exact schema:
{
  "primary_suggestion": "string — the most likely clinical consideration based on presented information",
  "confidence": "low|moderate|high",
  "reasoning_steps": ["array of strings — your step-by-step clinical reasoning, each step on its own"],
  "differential_diagnoses": ["array of strings — other conditions to consider, ordered by likelihood"],
  "missing_information": ["array of strings — what additional history/tests/imaging would help"],
  "red_flags": ["array of strings — urgent findings requiring immediate action, if any"],
  "recommended_next_steps": ["array of strings — practical clinical actions"],
  "uncertainty_factors": [
    {
      "factor": "string — what is uncertain",
      "impact": "low|medium|high",
      "recommendation": "string — how to address this uncertainty"
    }
  ],
  "diagnostic_gaps": [
    {
      "gap_type": "missing_differential|contradictory_finding|incomplete_history|anchoring_bias",
      "description": "string — specific gap identified",
      "suggested_action": "string — what to do about it",
      "severity": "low|medium|high"
    }
  ],
  "bias_alerts": [
    {
      "bias_type": "anchoring|availability|confirmation|demographic|premature_closure",
      "description": "string — specific bias risk identified",
      "alternative_to_consider": "string — what else to consider"
    }
  ],
  "counterfactual_insights": [
    {
      "variable": "string — the clinical variable",
      "current_value": "string — what it is now",
      "alternative_value": "string — what if it were different",
      "impact_on_diagnosis": "string — how that changes the picture"
    }
  ],
  "knowledge_base_version": "2025-01"
}

## Critical Rules
1. NEVER claim to diagnose. Use language like "Consider...", "This presentation is consistent with...", "Clinically notable..."
2. Always flag what you DON'T know and what information is missing.
3. If red flags are present (sepsis, MI signs, stroke symptoms, etc.), list them prominently.
4. Consider demographic factors (age, sex, ethnicity) in differentials — flag if typical presentations may differ.
5. If the clinician appears anchored on one diagnosis, gently surface alternatives.
6. Every reasoning step should be traceable to presented clinical evidence.
7. Return ONLY the JSON object — no preamble, no markdown fences.

## On Images
If an image is provided (dermatology photo, X-ray, pathology slide, etc.):
- Describe relevant findings in reasoning_steps
- Note image quality limitations in uncertainty_factors
- Incorporate visual findings into differentials
- Do NOT claim definitive radiological diagnosis"""


# ── LLM Service ───────────────────────────────────────────────────────────────
class LLMService:
    def __init__(self):
        self.claude_client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        genai.configure(api_key=settings.GOOGLE_AI_API_KEY)
        self.gemini_model = genai.GenerativeModel(settings.GEMINI_MODEL)

    def _build_conversation_history(
        self, previous_messages: list[dict]
    ) -> list[dict]:
        """
        Convert stored messages to the format expected by the Claude API.
        previous_messages: list of {"role": "user"|"assistant", "content": "..."}
        """
        history = []
        for msg in previous_messages[-10:]:  # Last 10 messages for context
            history.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return history

    def _build_user_message(
        self,
        text: str,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> dict:
        """Build the user message content block, optionally with an image."""
        if image_base64 and image_mime_type:
            return {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": text},
                ],
            }
        return {"role": "user", "content": text}

    async def generate_clinical_response(
        self,
        user_text: str,
        previous_messages: list[dict],
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
        research_context: Optional[list[dict]] = None,
    ) -> AIResponse:
        """
        Main method: generates a structured clinical reasoning response.

        Args:
            user_text: The (PII-redacted) clinical query text
            previous_messages: Prior chat history for context
            image_base64: Optional image data
            image_mime_type: Image MIME type
            research_context: Optional RAG results to include in context

        Returns:
            Parsed AIResponse with full reasoning structure
        """
        # Augment the user text with research context if available
        augmented_text = user_text
        if research_context:
            context_str = "\n\n## Relevant Research Context (from PubMed):\n"
            for paper in research_context[:3]:  # Top 3 papers
                context_str += f"- {paper['title']} ({paper['year']}): {paper['abstract_snippet']}\n"
            augmented_text = user_text + context_str

        messages = self._build_conversation_history(previous_messages)
        messages.append(
            self._build_user_message(augmented_text, image_base64, image_mime_type)
        )

        # Try Claude first, fall back to Gemini
        try:
            return await self._call_claude(messages)
        except (anthropic.APIStatusError, anthropic.APIConnectionError, anthropic.RateLimitError) as e:
            logger.warning(f"Claude API error: {e}. Falling back to Gemini.")
            try:
                return await self._call_gemini(augmented_text, image_base64, image_mime_type)
            except Exception as e2:
                logger.error(f"Gemini fallback also failed: {e2}")
                return self._get_demo_fallback_response(user_text)

    async def _call_claude(self, messages: list[dict]) -> AIResponse:
        """Call Claude API and parse the structured response."""
        response = await self.claude_client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=CLINICAL_SYSTEM_PROMPT,
            messages=messages,
            temperature=0.3,  # Lower temp = more consistent clinical reasoning
        )

        content = response.content[0].text
        return self._parse_ai_response(content, model_used=settings.CLAUDE_MODEL)

    async def _call_gemini(
        self,
        text: str,
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> AIResponse:
        """Gemini fallback — handles multimodal input."""
        parts = [CLINICAL_SYSTEM_PROMPT + "\n\n" + text]

        if image_base64 and image_mime_type:
            image_bytes = base64.b64decode(image_base64)
            parts.append({"mime_type": image_mime_type, "data": image_bytes})

        response = await self.gemini_model.generate_content_async(
            parts,
            generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        )
        return self._parse_ai_response(response.text, model_used=settings.GEMINI_MODEL)

    async def generate_streaming_response(
        self,
        user_text: str,
        previous_messages: list[dict],
        image_base64: Optional[str] = None,
        image_mime_type: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streaming version for real-time token-by-token display.
        Used by the streaming endpoint for better UX.
        Yields raw text chunks; frontend renders progressively.
        """
        messages = self._build_conversation_history(previous_messages)
        messages.append(
            self._build_user_message(user_text, image_base64, image_mime_type)
        )

        async with self.claude_client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=4096,
            system=CLINICAL_SYSTEM_PROMPT,
            messages=messages,
            temperature=0.3,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def generate_chat_title(self, first_message: str) -> str:
        """Generate a concise title for a new chat from the first message."""
        response = await self.claude_client.messages.create(
            model="claude-haiku-4-5",  # Use faster/cheaper model for titles
            max_tokens=30,
            messages=[{
                "role": "user",
                "content": f"Create a very short (max 6 words) title for a clinical chat that starts with: '{first_message[:200]}'. Return only the title, nothing else."
            }],
        )
        return response.content[0].text.strip().strip('"')

    async def generate_chat_summary(self, messages: list[dict]) -> str:
        """Generate a concise summary of a chat for display in folder view."""
        messages_text = "\n".join([
            f"{m['role'].upper()}: {m['content'][:200]}"
            for m in messages[-6:]
        ])
        response = await self.claude_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": f"Summarize this clinical conversation in 2-3 sentences for a folder view. Focus on the key clinical question and what was found:\n\n{messages_text}"
            }],
        )
        return response.content[0].text.strip()

    async def generate_research_tldr(
        self, title: str, abstract: str, clinical_context: str
    ) -> str:
        """Generate a 2-3 sentence TL;DR for a PubMed abstract."""
        response = await self.claude_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    f"Clinical context: {clinical_context[:300]}\n\n"
                    f"Paper: {title}\n\nAbstract: {abstract[:1000]}\n\n"
                    f"Write a 2-3 sentence TL;DR explaining why this paper is relevant to the clinical context above. "
                    f"Be specific about the key finding and its clinical implication."
                )
            }],
        )
        return response.content[0].text.strip()

    def _parse_ai_response(self, raw_content: str, model_used: str) -> AIResponse:
        """
        Parse the LLM's JSON response into an AIResponse schema.
        Handles malformed JSON gracefully with a structured error response.
        """
        # Strip potential markdown fences
        clean_content = re.sub(r"```json\s*|\s*```", "", raw_content).strip()

        try:
            data = json.loads(clean_content)
            # Inject model metadata
            data["model_used"] = model_used

            # Parse nested objects
            data["uncertainty_factors"] = [
                UncertaintyFactor(**u) for u in data.get("uncertainty_factors", [])
            ]
            data["diagnostic_gaps"] = [
                DiagnosticGap(**g) for g in data.get("diagnostic_gaps", [])
            ]
            data["bias_alerts"] = [
                BiasAlert(**b) for b in data.get("bias_alerts", [])
            ]
            data["counterfactual_insights"] = [
                CounterfactualInsight(**c) for c in data.get("counterfactual_insights", [])
            ]
            data["research_suggestions"] = []  # Populated by RAG service after

            return AIResponse(**data)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.error(f"Failed to parse AI response: {e}\nRaw: {raw_content[:500]}")
            # Return a safe fallback
            return self._get_error_response(model_used)

    def _get_demo_fallback_response(self, user_text: str) -> AIResponse:
        """Pre-computed fallback for demo continuity when APIs are down."""
        return AIResponse(
            primary_suggestion="[Demo Mode] API temporarily unavailable — this is a pre-computed example response",
            confidence="low",
            reasoning_steps=[
                "Note: Live API is currently unavailable. This is a demo fallback response.",
                f"Query received: {user_text[:100]}",
            ],
            differential_diagnoses=["Please retry when API is available"],
            missing_information=["Live API connection"],
            red_flags=[],
            recommended_next_steps=["Retry in a few moments"],
            uncertainty_factors=[],
            diagnostic_gaps=[],
            bias_alerts=[],
            counterfactual_insights=[],
            research_suggestions=[],
            model_used="demo_fallback",
            knowledge_base_version="2025-01",
        )

    def _get_error_response(self, model_used: str) -> AIResponse:
        """Fallback when response parsing fails."""
        return AIResponse(
            primary_suggestion="Response parsing error — please rephrase your query",
            confidence="low",
            reasoning_steps=["The AI response could not be parsed into the expected format."],
            differential_diagnoses=[],
            missing_information=["Clear clinical question"],
            red_flags=[],
            recommended_next_steps=["Rephrase the clinical question and try again"],
            uncertainty_factors=[],
            diagnostic_gaps=[],
            bias_alerts=[],
            counterfactual_insights=[],
            research_suggestions=[],
            model_used=model_used,
            knowledge_base_version="2025-01",
        )


# Singleton instance
llm_service = LLMService()
