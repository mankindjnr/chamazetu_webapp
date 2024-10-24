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
    "setfines_updatedays_autodisburse_rotations": {
        "task": "chama.tasks.setfines_updatedays_autodisburse_rotations_chain",
        "schedule": crontab(minute=30, hour=0),
    },
    # run everyday at 12 noon
    "make_auto_contributions": {
        "task": "member.tasks.make_auto_contributions",
        "schedule": crontab(minute=0, hour=12),
    },
    # runs 5 minutes after midnight everyday
    "update_accepting_members": {
        "task": "chama.tasks.check_and_update_accepting_members_status",
        "schedule": crontab(minute=5, hour=0),
    },
    # runs at 5 in the morning everyday
    "disburse_late_fines": {
        "task": "manager.tasks.late_auto_disbursements",
        "schedule": crontab(minute=0, hour=5),
    },
}

app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
