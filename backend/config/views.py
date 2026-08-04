from django.http import JsonResponse


def healthz(request):
    """Liveness probe used by Docker/CI — no DB or Redis access on purpose."""
    return JsonResponse({"status": "ok"})
