import pytest

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset


@pytest.fixture
def website_asset(tenant, tenant_owner):
    """Même fixture que dans apps/threat_intelligence/tests/conftest.py, dont
    la portée s'arrête à ce sous-arbre. Dupliquée plutôt que remontée au
    conftest racine : c'est une commodité de test locale, pas un contrat
    partagé, et la remonter la rendrait visible partout sans raison."""
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )
