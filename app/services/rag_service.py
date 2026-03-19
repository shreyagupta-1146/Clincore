"""
app/services/rag_service.py
────────────────────────────
Research Retrieval (RAG = Retrieval Augmented Generation) pipeline.

Flow:
1. Extract medical concepts from the clinical query (using the LLM or keyword extraction)
2. Search PubMed E-utilities API for relevant papers
3. Embed the abstracts using BioLORD-2023 (medical sentence embeddings)
4. Store in Qdrant vector database
5. At query time: embed the clinical query, find semantically similar papers
6. Return top-K results with relevance scores
7. LLM generates TL;DR for each result

The knowledge base is updated nightly via Celery Beat task.
"""

import asyncio
import hashlib
from typing import Optional
from datetime import datetime
from loguru import logger

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
    SearchParams,
)

from app.config import settings
from app.schemas.ai import ResearchSuggestion

# ── Embedding Model ────────────────────────────────────────────────────────────
# BioLORD-2023: Fine-tuned on biomedical text for semantic similarity
# Alternative: "neuml/pubmedbert-base-embeddings" (also good for PubMed)
_embedding_model: Optional[object] = None


def get_embedding_model():
    """Lazy-load the embedding model (downloads ~1GB on first run)."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded.")
    return _embedding_model


def embed_text(text: str) -> list[float]:
    """Convert text to embedding vector."""
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


# ── Qdrant Client ─────────────────────────────────────────────────────────────
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)


def ensure_collections_exist():
    """Create Qdrant collections if they don't exist. Called on app startup."""
    client = get_qdrant_client()

    for collection_name in [
        settings.QDRANT_COLLECTION_PUBMED,
        settings.QDRANT_COLLECTION_CASES,
    ]:
        existing = [c.name for c in client.get_collections().collections]
        if collection_name not in existing:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {collection_name}")


# ── PubMed API ─────────────────────────────────────────────────────────────────

PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


async def search_pubmed(query: str, max_results: int = 10) -> list[str]:
    """Search PubMed and return a list of PMIDs."""
    params = {
        "db": "pubmed",
        "term": f"{query} AND (systematic review[pt] OR randomized controlled trial[pt] OR clinical trial[pt])",
        "retmax": max_results,
        "retmode": "json",
        "sort": "relevance",
        "datetype": "pdat",
        "mindate": "2015",  # Prioritize recent literature
        "api_key": settings.NCBI_API_KEY,
        "email": settings.NCBI_EMAIL,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(PUBMED_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

    return data.get("esearchresult", {}).get("idlist", [])


async def fetch_pubmed_abstracts(pmids: list[str]) -> list[dict]:
    """Fetch full abstract data for a list of PMIDs."""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "json",
        "rettype": "abstract",
        "api_key": settings.NCBI_API_KEY,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(PUBMED_SUMMARY_URL, params=params)
        response.raise_for_status()
        data = response.json()

    articles = []
    result = data.get("result", {})

    for pmid in pmids:
        if pmid not in result:
            continue

        article = result[pmid]

        # Extract authors (first 3)
        authors = article.get("authors", [])
        author_str = ", ".join(
            [a.get("name", "") for a in authors[:3]]
        )
        if len(authors) > 3:
            author_str += " et al."

        # Evidence level classification
        pub_types = [pt.lower() for pt in article.get("pubtype", [])]
        evidence_level = _classify_evidence_level(pub_types)

        articles.append({
            "pmid": pmid,
            "title": article.get("title", ""),
            "authors": author_str,
            "journal": article.get("fulljournalname", article.get("source", "")),
            "year": int(article.get("pubdate", "2000")[:4] or 2000),
            "abstract": "",  # Summary endpoint doesn't include full abstract
            "abstract_snippet": article.get("title", "")[:200],
            "evidence_level": evidence_level,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })

    return articles


def _classify_evidence_level(pub_types: list[str]) -> str:
    """Classify evidence level from PubMed publication types."""
    if any(t in pub_types for t in ["meta-analysis", "systematic review"]):
        return "meta_analysis"
    if "randomized controlled trial" in pub_types:
        return "rct"
    if any(t in pub_types for t in ["clinical trial", "controlled clinical trial"]):
        return "clinical_trial"
    if "practice guideline" in pub_types:
        return "guideline"
    if "cohort studies" in pub_types:
        return "cohort"
    return "case_report"


# ── Qdrant Indexing ───────────────────────────────────────────────────────────

def index_article(article: dict, collection: str = None) -> bool:
    """Embed and store a PubMed article in Qdrant."""
    if collection is None:
        collection = settings.QDRANT_COLLECTION_PUBMED

    client = get_qdrant_client()
    model = get_embedding_model()

    # Text to embed: title + abstract snippet
    text_to_embed = f"{article['title']} {article.get('abstract', '')}".strip()

    if not text_to_embed:
        return False

    vector = model.encode(text_to_embed, normalize_embeddings=True).tolist()

    # Use MD5 of PMID as deterministic integer ID for Qdrant
    point_id = int(hashlib.md5(article["pmid"].encode()).hexdigest()[:8], 16)

    client.upsert(
        collection_name=collection,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "pmid": article["pmid"],
                    "title": article["title"],
                    "authors": article["authors"],
                    "journal": article["journal"],
                    "year": article["year"],
                    "abstract_snippet": article.get("abstract_snippet", ""),
                    "evidence_level": article["evidence_level"],
                    "url": article["url"],
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            )
        ],
    )
    return True


# ── Semantic Search ────────────────────────────────────────────────────────────

def search_similar_research(
    query: str,
    top_k: int = 5,
    min_year: int = 2015,
    evidence_levels: Optional[list[str]] = None,
) -> list[dict]:
    """
    Find research papers semantically similar to the clinical query.

    Args:
        query: The clinical question/context
        top_k: Number of results
        min_year: Filter out older papers
        evidence_levels: Only return specific evidence levels (e.g., ["rct", "meta_analysis"])
    """
    client = get_qdrant_client()
    query_vector = embed_text(query)

    # Build filter conditions
    conditions = [
        FieldCondition(key="year", range=Range(gte=min_year))
    ]

    if evidence_levels:
        conditions.append(
            FieldCondition(
                key="evidence_level",
                match=MatchAny(any=evidence_levels)
            )
        )

    search_filter = Filter(must=conditions) if conditions else None

    results = client.search(
        collection_name=settings.QDRANT_COLLECTION_PUBMED,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=top_k,
        search_params=SearchParams(hnsw_ef=128),
        with_payload=True,
        score_threshold=0.4,  # Minimum relevance threshold
    )

    return [
        {**result.payload, "relevance_score": round(result.score, 3)}
        for result in results
    ]


# ── Main RAG Pipeline ─────────────────────────────────────────────────────────

async def get_research_suggestions(
    clinical_text: str,
    llm_service,
    top_k: int = 5,
) -> list[ResearchSuggestion]:
    """
    Full RAG pipeline: query → vector search → TL;DR generation.

    1. Search Qdrant for semantically similar papers
    2. If not enough results, fallback to live PubMed search
    3. Generate TL;DR for each result
    4. Return ranked list of ResearchSuggestion
    """
    suggestions = []

    # Step 1: Semantic search in Qdrant
    qdrant_results = search_similar_research(clinical_text, top_k=top_k)
    logger.info(f"Qdrant returned {len(qdrant_results)} results")

    # Step 2: Fallback to live PubMed if Qdrant is sparse
    if len(qdrant_results) < 3:
        logger.info("Qdrant sparse, falling back to live PubMed search")
        try:
            pmids = await search_pubmed(clinical_text[:200], max_results=5)
            live_articles = await fetch_pubmed_abstracts(pmids)
            # Add live results to Qdrant for future queries
            for article in live_articles:
                index_article(article)
            # Combine results
            qdrant_results.extend([
                {**a, "relevance_score": 0.5}  # Default score for live results
                for a in live_articles
                if not any(r.get("pmid") == a["pmid"] for r in qdrant_results)
            ])
        except Exception as e:
            logger.warning(f"PubMed live search failed: {e}")

    # Step 3: Generate TL;DRs (async, all at once)
    tldr_tasks = [
        llm_service.generate_research_tldr(
            title=result.get("title", ""),
            abstract=result.get("abstract_snippet", result.get("title", "")),
            clinical_context=clinical_text[:300],
        )
        for result in qdrant_results[:top_k]
    ]

    tldr_results = await asyncio.gather(*tldr_tasks, return_exceptions=True)

    # Step 4: Build ResearchSuggestion objects
    for i, result in enumerate(qdrant_results[:top_k]):
        tldr = tldr_results[i] if not isinstance(tldr_results[i], Exception) else "Summary unavailable."

        suggestions.append(ResearchSuggestion(
            pubmed_id=result.get("pmid", ""),
            title=result.get("title", "Untitled"),
            authors=result.get("authors", ""),
            journal=result.get("journal", ""),
            year=result.get("year", 2020),
            abstract_snippet=result.get("abstract_snippet", "")[:300],
            tldr=tldr,
            relevance_score=result.get("relevance_score", 0.5),
            evidence_level=result.get("evidence_level", "unknown"),
            url=result.get("url", f"https://pubmed.ncbi.nlm.nih.gov/{result.get('pmid', '')}/"),
        ))

    # Sort by relevance score descending
    suggestions.sort(key=lambda x: x.relevance_score, reverse=True)
    return suggestions


# Singleton
rag_service = type("RAGService", (), {
    "get_research_suggestions": staticmethod(get_research_suggestions),
    "search_similar_research": staticmethod(search_similar_research),
    "index_article": staticmethod(index_article),
    "ensure_collections_exist": staticmethod(ensure_collections_exist),
})()
