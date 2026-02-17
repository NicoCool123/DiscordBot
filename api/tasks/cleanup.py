"""Background cleanup tasks for data retention."""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update

from api.core.config import settings
from api.core.database import AsyncSessionLocal
from api.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def cleanup_old_audit_logs() -> None:
    """Clean up audit logs older than retention period.

    This task:
    1. Anonymizes logs between anonymize_after_days and retention_days
    2. Deletes logs older than retention_days
    """
    # Skip if audit logging is disabled
    if not settings.audit_log_enabled:
        return

    try:
        async with AsyncSessionLocal() as db:
            # Calculate cutoff dates
            retention_days = getattr(settings, "audit_log_retention_days", 1)
            anonymize_days = getattr(settings, "audit_log_anonymize_after_days", 0)

            delete_cutoff = datetime.utcnow() - timedelta(days=retention_days)
            anonymize_cutoff = datetime.utcnow() - timedelta(days=anonymize_days)

            # Anonymize logs between anonymize and delete cutoffs
            anonymize_result = await db.execute(
                update(AuditLog)
                .where(
                    AuditLog.created_at < anonymize_cutoff,
                    AuditLog.created_at >= delete_cutoff,
                    AuditLog.anonymized == False,  # noqa: E712
                )
                .values(
                    ip_address="0.0.0.0",
                    user_agent="[ANONYMIZED]",
                    anonymized=True,
                )
            )

            # Delete logs older than retention period
            delete_result = await db.execute(
                delete(AuditLog).where(AuditLog.created_at < delete_cutoff)
            )

            await db.commit()

            anonymized_count = anonymize_result.rowcount
            deleted_count = delete_result.rowcount

            if anonymized_count > 0 or deleted_count > 0:
                logger.info(
                    f"Audit log cleanup: anonymized {anonymized_count} logs, "
                    f"deleted {deleted_count} logs older than {retention_days} days"
                )

    except Exception as e:
        logger.error(f"Error during audit log cleanup: {e}")


async def run_cleanup_scheduler() -> None:
    """Run cleanup tasks on a daily schedule."""
    logger.info("Started audit log cleanup scheduler")

    while True:
        try:
            # Run cleanup
            await cleanup_old_audit_logs()

            # Wait 24 hours before next run
            await asyncio.sleep(86400)

        except asyncio.CancelledError:
            logger.info("Cleanup scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in cleanup scheduler: {e}")
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)
