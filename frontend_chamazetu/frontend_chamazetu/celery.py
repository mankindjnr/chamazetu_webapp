from __future__ import absolute_import, division, print_function, unicode_literals
import os
from zoneinfo import ZoneInfo
from celery import Celery, chain
from django.conf import settings
from datetime import timedelta
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend_chamazetu.settings")

app = Celery("frontend_chamazetu")
app.conf.enable_utc = False
app.conf.timezone = ZoneInfo("Africa/Nairobi")


# app.config_from_object('django.conf:settings', namespace='CELERY')
app.config_from_object(settings, namespace="CELERY")

app.conf.accept_content = ["json", "pickle"]

# if the missed contributions and update contributions don't work as expected, then run them every 2 hours or so

# celery Beat settings
app.conf.beat_schedule = {
    # executed a little past midnight everyday
    "update-contribution-days": {
        "task": "chama.tasks.set_fines_and_update_activity_contribution_days",
        "schedule": crontab(minute=30, hour=0),
    },
    # run everyday at 12 noon
    "make_auto_contributions": {
        "task": "member.tasks.auto_contribute",
        "schedule": crontab(minute=0, hour=12),
    },
}

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
