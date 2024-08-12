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
    # executed at midnight everyday
    "update-contribution-days": {
        "task": "chama.tasks.update_contribution_days",
        "schedule": crontab(minute=40, hour=0),
    },
    # every day - midnight - calculate daily mmf interests - midnight
    "run_daily": {
        "task": "chama.tasks.calculate_daily_mmf_interests",
        "schedule": crontab(minute=15, hour=0),
    },
    # every week - resets weekly interests and adds the weekly interests to the principal
    # every sat at midnight
    "run_weekly": {
        "task": "chama.tasks.reset_and_move_weekly_mmf_interests",
        "schedule": crontab(minute=10, hour=0, day_of_week=6),
    },
    # every month - resets monthly interests
    # every 1st of the month
    "run_monthly": {
        "task": "chama.tasks.reset_monthly_mmf_interests",
        "schedule": crontab(minute=15, hour=0, day_of_month=1),
    },
    # few minutes after midnight - calculate missed contributions and update the fines
    "run_fines": {
        "task": "member.tasks.calculate_missed_contributions_fines",
        "schedule": crontab(minute=0, hour=1),
    },
    # run at 2am every day
    "run_pending_withdrawals": {
        "task": "manager.tasks.fulfill_pending_withdrawal_requests",
        "schedule": crontab(minute=0, hour=2),
    },
    # run at 11pm every day
    "update_and_fix_callbacks": {
        "task": "chama.tasks.run_update_and_fix_callbacks",
        "schedule": crontab(minute=0, hour=23),
    },
    # run everyday at 9 pm
    "make_auto_contributions": {
        "task": "member.tasks.auto_contribute",
        "schedule": crontab(minute=0, hour=10),
    },
}

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
