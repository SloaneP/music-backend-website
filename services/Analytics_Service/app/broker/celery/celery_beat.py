from .celery_worker import celery_app

celery_app.conf.beat_schedule = {
    "update-user-analytics-every-1-minutes": {
        "task": "tasks.update_user_analytics_for_all",
        "schedule": 60 * 1,
    },
}

