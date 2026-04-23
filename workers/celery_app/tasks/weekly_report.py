from celery_app.config import app

# Phase 3: full implementation


@app.task(bind=True, max_retries=3)
def generate_for_all_users(self):
    """For each user with AI enabled, publish AI_ANALYSIS_REQUESTED to SNS."""
    raise NotImplementedError("Implement in Phase 3")
