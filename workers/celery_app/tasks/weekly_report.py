import logging

from celery_app.config import app
from celery_app.db import User, UserAISettings, get_session
from celery_app.sns import publish_event

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3)
def generate_for_all_users(self):
    """For each user with AI enabled, publish AI_ANALYSIS_REQUESTED to SNS."""
    published = 0
    try:
        with get_session() as session:
            ai_users = (
                session.query(User)
                .join(UserAISettings, UserAISettings.user_id == User.id)
                .filter(UserAISettings.ai_enabled.is_(True))
                .all()
            )
            for user in ai_users:
                publish_event(
                    event_type="ai.analysis.requested",
                    user_id=str(user.id),
                    payload={"trigger": "weekly_report"},
                )
                published += 1

    except Exception as exc:
        logger.error("weekly_report failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    logger.info("weekly_report: published %d AI_ANALYSIS_REQUESTED events", published)
    return {"published": published}
