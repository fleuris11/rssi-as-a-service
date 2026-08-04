from django.http import JsonResponse


def healthz(request):
    """Liveness probe used by Docker/CI — no DB or Redis access on purpose."""
    return JsonResponse({"status": "ok"})


def healthz_worker(request):
    """Proves Celery Beat *and* a worker on the monitoring queue are both
    alive end to end (not just "a process exists") — see
    apps.monitoring.tasks.heartbeat and apps.monitoring.services."""
    from apps.monitoring.services import is_worker_healthy

    healthy, last_seen = is_worker_healthy()
    return JsonResponse(
        {"status": "ok" if healthy else "down", "last_heartbeat": last_seen},
        status=200 if healthy else 503,
    )
