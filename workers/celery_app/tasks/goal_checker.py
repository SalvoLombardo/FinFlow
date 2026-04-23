from celery_app.config import app

# Phase 3: full implementation


@app.task(bind=True, max_retries=3)
def check_expiring_goals(self):
    """Find goals expiring within 30 days and behind >20%; publish GOAL_PROGRESS to SNS."""
    raise NotImplementedError("Implement in Phase 3")
