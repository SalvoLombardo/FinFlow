import datetime as _dt
import logging

from celery_app.config import app
from celery_app.db import Goal, GoalStatus, get_session
from celery_app.sns import publish_event

logger = logging.getLogger(__name__)


def _today() -> _dt.date:
    return _dt.date.today()


@app.task(bind=True, max_retries=3)
def check_expiring_goals(self):
    """Find active goals expiring within 30 days and behind >20%; publish GOAL_PROGRESS to SNS."""
    today = _today()
    deadline = today + _dt.timedelta(days=30)
    published = 0

    try:
        with get_session() as session:
            goals = (
                session.query(Goal)
                .filter(
                    Goal.status == GoalStatus.active,
                    Goal.target_date <= deadline,
                )
                .all()
            )
            for goal in goals:
                if goal.target_amount <= 0:
                    continue
                gap_pct = float(goal.target_amount - goal.current_amount) / float(goal.target_amount)
                if gap_pct <= 0.2:
                    continue
                publish_event(
                    event_type="goal.progress",
                    user_id=str(goal.user_id),
                    payload={
                        "goal_id": str(goal.id),
                        "goal_name": goal.name,
                        "target_amount": str(goal.target_amount),
                        "current_amount": str(goal.current_amount),
                        "target_date": goal.target_date.isoformat(),
                        "gap_pct": round(gap_pct * 100, 1),
                    },
                )
                published += 1

    except Exception as exc:
        logger.error("goal_checker failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    logger.info("goal_checker: published %d GOAL_PROGRESS events", published)
    return {"published": published}
