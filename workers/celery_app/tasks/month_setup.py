from celery_app.config import app

# Phase 3: full implementation


@app.task(bind=True, max_retries=3)
def create_next_month_weeks(self):
    """Create financial_weeks for next month for all active users; copy recurring transactions; log to Kafka."""
    raise NotImplementedError("Implement in Phase 3")
