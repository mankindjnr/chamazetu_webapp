from __future__ import absolute_import, division, print_function, unicode_literals
import os

from celery import Celery
from django.conf import settings
from datetime import timedelta
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend_chamazetu.settings")

app = Celery("frontend_chamazetu")
app.conf.enable_utc = False  # we already set this in settings.py

app.conf.update(timezone="Africa/Nairobi")

# app.config_from_object('django.conf:settings', namespace='CELERY')
app.config_from_object(settings, namespace="CELERY")

# celery Beat settings
app.conf.beat_schedule = {
    "update-contribution-days": {
        "task": "chama.tasks.update_contribution_days",
        "schedule": crontab(minute=0, hour=0),  # executed at midnight everyday
    },
    # every day - midnight - calculate daily mmf interests
    "run_daily": {
        "task": "chama.tasks.calaculate_daily_mmf_interests",
        "schedule": crontab(minute="*/10"),
    },
    # every week - resets weekly interests and adds the weekly interests to the principal
    "run_weekly": {
        "task": "chama.tasks.reset_and_move_weekly_mmf_interests",
        "schedule": crontab(minute="*/30"),  # every sat at midnight
    },
    # every month - resets monthly interests
    "run_monthly": {
        "task": "chama.tasks.reset_monthly_mmf_interests",
        "schedule": timedelta(hours=1),  # every 1st of the month
    },
}

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
