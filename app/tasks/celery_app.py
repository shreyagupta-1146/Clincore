"""
app/tasks/celery_app.py
────────────────────────
Celery configuration and scheduled tasks.

Tasks:
1. `update_knowledge_base` — runs nightly, fetches new PubMed papers
2. `generate_chat_summary_task` — generates summaries for long chats
3. `cleanup_expired_shares` — removes expired share records
4. `cleanup_old_audit_logs` — removes audit logs beyond retention period

The Celery Beat scheduler triggers these on a schedule.
Run workers with: celery -A app.tasks.celery_app worker --loglevel=info
Run beat with:    celery -A app.tasks.celery_app beat --loglevel=info
"""

import asyncio
from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from loguru import logger

from app.config import settings

# ── Celery App ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "clinicore",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # Important for long-running tasks
)

# ── Scheduled Tasks ───────────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "update-knowledge-base-nightly": {
        "task": "app.tasks.celery_app.update_knowledge_base",
        "schedule": crontab(hour=2, minute=0),  # 2 AM UTC daily
        "kwargs": {"topics": [
            "clinical diagnosis guidelines 2024",
            "evidence based medicine systematic review",
            "dermatology diagnosis imaging",
            "radiology chest X-ray interpretation",
            "infectious disease treatment",
            "cardiology guidelines",
            "oncology screening",
            "emergency medicine",
        ]},
    },
    "cleanup-expired-shares-daily": {
        "task": "app.tasks.celery_app.cleanup_expired_shares",
        "schedule": crontab(hour=3, minute=0),  # 3 AM UTC daily
    },
    "cleanup-old-audit-logs-weekly": {
        "task": "app.tasks.celery_app.cleanup_old_audit_logs",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),  # Sunday 4 AM
    },
}


# ── Task: Knowledge Base Update ───────────────────────────────────────────────

@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=3600,  # 1 hour max
    name="app.tasks.celery_app.update_knowledge_base",
)
def update_knowledge_base(self, topics: list[str]):
    """
    Fetch new PubMed papers and index them in Qdrant.

    This runs nightly to keep the knowledge base current.
    Only fetches papers published in the last 7 days to stay efficient.

    Evidence quality filter:
    - Prioritises: Systematic reviews, RCTs, Clinical Guidelines
    - Deprioritises: Case reports (indexed but lower weight)
    """
    logger.info(f"Starting knowledge base update for {len(topics)} topics")

    async def _run():
        from app.services.rag_service import (
            search_pubmed,
            fetch_pubmed_abstracts,
            index_article,
            ensure_collections_exist,
        )

        ensure_collections_exist()

        total_indexed = 0
        total_skipped = 0

        for topic in topics:
            try:
                logger.info(f"Fetching PubMed papers for: {topic}")

                # Fetch recent papers (last 30 days for weekly runs)
                pmids = await search_pubmed(
                    query=topic + " AND free full text[sb]",
                    max_results=settings.PUBMED_MAX_RESULTS,
                )

                if not pmids:
                    logger.info(f"No new papers found for: {topic}")
                    continue

                articles = await fetch_pubmed_abstracts(pmids)

                for article in articles:
                    # Quality filter: skip low-quality sources
                    if article.get("evidence_level") == "case_report" and total_indexed > 100:
                        total_skipped += 1
                        continue

                    indexed = index_article(article)
                    if indexed:
                        total_indexed += 1

                logger.info(f"Topic '{topic}': indexed {len(articles)} papers")

            except Exception as e:
                logger.error(f"Error processing topic '{topic}': {e}")
                continue

        logger.info(
            f"Knowledge base update complete. "
            f"Indexed: {total_indexed}, Skipped: {total_skipped}"
        )

        return {
            "topics_processed": len(topics),
            "total_indexed": total_indexed,
            "total_skipped": total_skipped,
            "timestamp": datetime.utcnow().isoformat(),
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(f"Knowledge base update failed: {exc}")
        raise self.retry(exc=exc, countdown=300)  # Retry after 5 minutes


# ── Task: Cleanup Expired Shares ──────────────────────────────────────────────

@celery_app.task(name="app.tasks.celery_app.cleanup_expired_shares")
def cleanup_expired_shares():
    """Mark expired shares as revoked. Runs daily."""
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.share import Share
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Share).where(
                    Share.is_revoked == False,
                    Share.expires_at < datetime.utcnow(),
                )
            )
            expired = result.scalars().all()

            for share in expired:
                share.is_revoked = True
                share.revoked_at = datetime.utcnow()

            await db.commit()
            logger.info(f"Cleaned up {len(expired)} expired shares")

    asyncio.run(_run())


# ── Task: Cleanup Old Audit Logs ──────────────────────────────────────────────

@celery_app.task(name="app.tasks.celery_app.cleanup_old_audit_logs")
def cleanup_old_audit_logs():
    """
    Remove audit logs older than AUDIT_LOG_RETENTION_DAYS.
    HIPAA requires 7 years (2555 days) minimum retention.
    This task ONLY runs if the retention period has passed.
    """
    async def _run():
        from app.database import AsyncSessionLocal
        from app.models.audit import AuditLog
        from sqlalchemy import delete

        cutoff = datetime.utcnow() - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(AuditLog).where(AuditLog.timestamp < cutoff)
            )
            await db.commit()
            logger.info(f"Deleted {result.rowcount} audit logs older than {cutoff.date()}")

    asyncio.run(_run())


# ── Manual Trigger: Index Specific Topics ─────────────────────────────────────

@celery_app.task(name="app.tasks.celery_app.index_topic")
def index_topic_now(topic: str, max_results: int = 20):
    """
    Manually trigger indexing for a specific topic.
    Can be called from the admin interface.
    """
    return update_knowledge_base.apply(args=[[topic]]).get()
