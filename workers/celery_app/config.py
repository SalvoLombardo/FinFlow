from celery import Celery
from celery.schedules import crontab

app = Celery("finflow_workers")
app.config_from_object("celery_app.celeryconfig")

# Phase 3: full schedule implementation
app.conf.beat_schedule = {
    "weekly-report-sunday": {
        "task": "celery_app.tasks.weekly_report.generate_for_all_users",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
    "month-setup-first-day": {
        "task": "celery_app.tasks.month_setup.create_next_month_weeks",
        "schedule": crontab(hour=1, minute=0, day=1),
    },
    "goal-checker-daily": {
        "task": "celery_app.tasks.goal_checker.check_expiring_goals",
        "schedule": crontab(hour=9, minute=0),
    },
}
