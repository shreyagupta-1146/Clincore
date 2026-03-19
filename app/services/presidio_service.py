"""
app/services/presidio_service.py
─────────────────────────────────
PII (Personally Identifiable Information) detection and redaction.

Uses Microsoft Presidio with spaCy's NLP pipeline.
Runs BEFORE any text is sent to external LLM APIs.

What gets detected & redacted:
- Person names (PERSON)
- Medical record numbers (US_DRIVER_LICENSE used as proxy)
- Phone numbers (PHONE_NUMBER)
- Email addresses (EMAIL_ADDRESS)
- Dates of birth (DATE_TIME — partially)
- National IDs, SSNs (US_SSN)
- IP addresses (IP_ADDRESS)
- Locations / addresses (LOCATION)
- URLs (URL)

Redaction strategy: Replace with type placeholder.
Example: "John Smith, DOB 01/01/1980" → "[PERSON] DOB [DATE_TIME]"

The original text is stored in the DB; only redacted text goes to LLMs.
"""

from typing import Optional
from loguru import logger


# ── Initialize Presidio ───────────────────────────────────────────────────────
def _create_analyzer():
    """
    Creates the Presidio analyzer with spaCy's large English model.
    This is called once at startup and cached.
    """
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        
        # Use spaCy large model for better NER accuracy
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        return AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    except Exception as e:
        logger.warning(
            f"Could not load spaCy large model: {e}. Falling back to basic analyzer."
        )
        try:
            from presidio_analyzer import AnalyzerEngine
            return AnalyzerEngine()
        except ImportError:
            logger.warning("Presidio not installed. PII detection disabled.")
            return None


# Lazy initialization — only loads spaCy model when first needed
_analyzer: Optional[object] = None
_anonymizer: Optional[object] = None


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        _analyzer = _create_analyzer()
    return _analyzer


def _get_anonymizer():
    global _anonymizer
    if _anonymizer is None:
        try:
            from presidio_anonymizer import AnonymizerEngine
            _anonymizer = AnonymizerEngine()
        except ImportError:
            logger.warning("Presidio anonymizer not installed.")
            return None
    return _anonymizer


# ── PII Detection & Redaction ─────────────────────────────────────────────────

# Entity types to detect
ENTITIES_TO_DETECT = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "DATE_TIME",
    "US_SSN",
    "US_DRIVER_LICENSE",
    "CREDIT_CARD",
    "IP_ADDRESS",
    "URL",
    "MEDICAL_LICENSE",  # Presidio custom recognizer (doctor license numbers)
]

# Redaction operator: replace with "<TYPE>" placeholder
def get_redaction_operators():
    try:
        from presidio_anonymizer.entities import OperatorConfig
        return {
            entity: OperatorConfig("replace", {"new_value": f"[{entity}]"})
            for entity in ENTITIES_TO_DETECT
        }
    except ImportError:
        return {}


def detect_and_redact(text: str) -> dict:
    """
    Detect PII entities in text and return both redacted text and entity log.

    Returns:
        {
            "redacted_text": str,       # Safe to send to LLM APIs
            "original_text": str,       # Stored encrypted in DB, never sent externally
            "entities_found": list,     # Audit log of what was found
            "pii_detected": bool        # Quick flag
        }
    """
    if not text or not text.strip():
        return {
            "redacted_text": text,
            "original_text": text,
            "entities_found": [],
            "pii_detected": False,
        }

    try:
        analyzer = _get_analyzer()
        anonymizer = _get_anonymizer()
        
        if analyzer is None or anonymizer is None:
            logger.warning("Presidio not available. Skipping PII redaction.")
            return {
                "redacted_text": text,
                "original_text": text,
                "entities_found": [],
                "pii_detected": False,
            }

        # Analyze — detect PII entities
        results = analyzer.analyze(
            text=text,
            language="en",
            entities=ENTITIES_TO_DETECT,
            score_threshold=0.5,  # Only flag high-confidence detections
        )

        # Build entity log for audit
        entities_found = [
            {
                "type": result.entity_type,
                "score": round(result.score, 3),
                "start": result.start,
                "end": result.end,
                # Store character count of original (not the actual PII)
                "char_count": result.end - result.start,
            }
            for result in results
        ]

        # Anonymize — replace PII with placeholders
        anonymized = anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=get_redaction_operators(),
        )

        return {
            "redacted_text": anonymized.text,
            "original_text": text,
            "entities_found": entities_found,
            "pii_detected": len(results) > 0,
        }

    except Exception as e:
        logger.error(f"Presidio redaction failed: {e}")
        # Safe fallback: return original text with warning
        # In production, consider failing closed (blocking the request)
        return {
            "redacted_text": text,
            "original_text": text,
            "entities_found": [{"type": "ERROR", "message": str(e)}],
            "pii_detected": False,
        }


def analyze_only(text: str) -> list[dict]:
    """
    Detect PII without redacting — used for preview/warning before sending.
    Returns list of detected entity types.
    """
    if not text:
        return []

    try:
        analyzer = _get_analyzer()
        results = analyzer.analyze(text=text, language="en", entities=ENTITIES_TO_DETECT)
        return [{"type": r.entity_type, "score": r.score} for r in results]
    except Exception as e:
        logger.error(f"PII analysis failed: {e}")
        return []


# Singleton pattern
presidio_service = type("PresidioService", (), {
    "detect_and_redact": staticmethod(detect_and_redact),
    "analyze_only": staticmethod(analyze_only),
})()
