"""Dashboard settings, API keys, theme, version and localisation."""

from __future__ import annotations

from typing import Any

from ..models import APIKey, DashboardConfiguration, Locale
from .base import Resource


class DashboardResource(Resource):
    """Read and change the dashboard's own settings.

    Accessed as ``client.dashboard``.
    """

    async def get_configuration(self) -> DashboardConfiguration:
        """Return the full contents of ``wg-dashboard.ini``."""
        data = await self._client._get("/api/getDashboardConfiguration")
        return DashboardConfiguration.model_validate(data or {})

    async def update_configuration_item(self, section: str, key: str, value: Any) -> Any:
        """Change a single setting, writing it to ``wg-dashboard.ini``.

        Args:
            section: Section name, e.g. ``"Peers"`` or ``"Server"``.
            key: Setting name within the section, e.g. ``"peer_display_mode"``.
            value: New value.

        Returns:
            The stored value.
        """
        return await self._client._post(
            "/api/updateDashboardConfigurationItem",
            json={"section": section, "key": key, "value": value},
        )

    async def get_version(self) -> str:
        """Return the dashboard version, e.g. ``"v4.2.0"``."""
        return await self._client._get("/api/getDashboardVersion")

    async def get_theme(self) -> str:
        """Return the active theme, ``"dark"`` or ``"light"``."""
        return await self._client._get("/api/getDashboardTheme")

    async def check_update(self) -> str | None:
        """Check for a newer release.

        Returns:
            The update URL when one is available, otherwise ``None``.
        """
        return await self._client._get("/api/getDashboardUpdate")

    async def is_totp_enabled(self) -> bool:
        """Whether two-factor authentication is enabled on the dashboard."""
        return bool(await self._client._get("/api/isTotpEnabled"))

    # ------------------------------------------------------------------ #
    # API keys
    # ------------------------------------------------------------------ #

    async def list_api_keys(self) -> list[APIKey]:
        """Return every API key configured on the dashboard."""
        data = await self._client._get("/api/getDashboardAPIKeys")
        return [APIKey.model_validate(item) for item in data or []]

    async def create_api_key(
        self,
        *,
        never_expire: bool = False,
        expired_at: str | None = None,
    ) -> list[APIKey]:
        """Create a new API key.

        Args:
            never_expire: Create a key that never expires. Takes precedence over
                ``expired_at``.
            expired_at: Expiry as ``"YYYY-MM-DD HH:MM:SS"``.

        Returns:
            All API keys, with the new one included.
        """
        data = await self._client._post(
            "/api/newDashboardAPIKey",
            json={"NeverExpire": never_expire, "ExpiredAt": expired_at},
        )
        return [APIKey.model_validate(item) for item in data or []]

    async def delete_api_key(self, key: str) -> list[APIKey]:
        """Revoke an API key.

        Revoking the key this client authenticates with will break subsequent calls.

        Returns:
            The remaining API keys.
        """
        data = await self._client._post("/api/deleteDashboardAPIKey", json={"Key": key})
        return [APIKey.model_validate(item) for item in data or []]

    # ------------------------------------------------------------------ #
    # Localisation
    # ------------------------------------------------------------------ #

    async def get_locale(self) -> str | None:
        """Return the active language id. ``None`` means English."""
        return await self._client._get("/api/locale")

    async def get_available_locales(self) -> list[Locale]:
        """Return the languages the dashboard ships translations for."""
        data = await self._client._get("/api/locale/available")
        return [Locale.model_validate(item) for item in data or []]

    async def update_locale(self, lang_id: str) -> dict[str, str]:
        """Switch the dashboard language.

        Args:
            lang_id: A language id from :meth:`get_available_locales`, e.g. ``"ru"``.

        Returns:
            The translation table for the newly selected language.
        """
        data = await self._client._post("/api/locale/update", json={"lang_id": lang_id})
        return data or {}
