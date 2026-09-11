import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

try:
    from celery import Celery
    CELERY_AVAILABLE = True
except ImportError:
    Celery = None
    CELERY_AVAILABLE = False

from backend.config.settings import get_settings

settings = get_settings()

if CELERY_AVAILABLE:
    celery_app = Celery(
        "chainsleuth",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=[
            "backend.tasks.trace_task",
            "backend.tasks.alert_task"
        ]
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=300,
        beat_schedule={
            "monitor-suspect-wallets-every-5-min": {
                "task": "backend.tasks.alert_task.monitor_active_wallets",
                "schedule": 300.0,
            }
        }
    )
else:
    # Lightweight mock for local development and test environments
    class MockTask:
        def __init__(self, func: Callable):
            self.func = func

        def delay(self, *args: Any, **kwargs: Any) -> Any:
            return self.func(*args, **kwargs)

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            return self.func(*args, **kwargs)

    class MockCelery:
        def __init__(self):
            self.conf = {}

        def task(self, *dargs: Any, **dkwargs: Any) -> Callable:
            def decorator(f: Callable) -> MockTask:
                return MockTask(f)
            if len(dargs) == 1 and callable(dargs[0]):
                return MockTask(dargs[0])
            return decorator

    celery_app = MockCelery()
    logger.info("Celery package not installed. Using local task executor fallback.")

