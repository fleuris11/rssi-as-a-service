from django.apps import apps


def test_platform_admin_app_is_installed():
    """Scaffold check: the app loads cleanly ahead of the back-office work
    planned for a later phase."""
    assert apps.is_installed("apps.platform_admin")
