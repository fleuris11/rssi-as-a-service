import pytest

from apps.monitoring import services as monitoring_services
from apps.monitoring.models import Asset


@pytest.fixture
def website_asset(tenant, tenant_owner):
    return monitoring_services.create_asset(
        tenant=tenant,
        user=tenant_owner,
        type=Asset.Type.WEBSITE,
        value="https://example.com",
        ownership_confirmed=True,
    )
