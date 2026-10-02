"""Resource namespaces exposed on :class:`~wgdashboard.client.WGDashboardClient`."""

from .backups import BackupsResource
from .base import Resource
from .configurations import ConfigurationsResource
from .dashboard import DashboardResource
from .email import EmailResource
from .jobs import JobsResource
from .peers import PeersResource
from .system import SystemResource

__all__ = [
    "Resource",
    "BackupsResource",
    "ConfigurationsResource",
    "DashboardResource",
    "EmailResource",
    "JobsResource",
    "PeersResource",
    "SystemResource",
]
