from ..models import ConnectorProvider
from .adzuna import AdzunaConnector
from .greenhouse import GreenhouseConnector
from .lever import LeverConnector
from .jsearch import JSearchConnector

CONNECTOR_REGISTRY = {
    ConnectorProvider.adzuna: AdzunaConnector,
    ConnectorProvider.greenhouse: GreenhouseConnector,
    ConnectorProvider.lever: LeverConnector,
    ConnectorProvider.jsearch: JSearchConnector,
}


def get_connector(provider: ConnectorProvider, credentials: dict):
    cls = CONNECTOR_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"No connector registered for provider: {provider}")
    return cls(credentials)
