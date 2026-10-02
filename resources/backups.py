"""Backup and restore of WireGuard configurations."""

from __future__ import annotations

from ..models import AllBackups, Backup
from .base import Resource


class BackupsResource(Resource):
    """Create, list, restore and delete configuration backups.

    Accessed as ``client.backups``. A backup captures the ``.conf`` file and,
    optionally, the peer database.

    .. warning::
        Up to and including WGDashboard v4.3.3 the server cannot see the backups of a
        configuration that still exists, because of a typo in the filename pattern it
        matches them against (``\\\\.conf`` instead of ``\\.conf`` in
        ``WireguardConfiguration.getBackups``). On an affected server:

        * :meth:`create` writes the backup but returns an empty list
        * :meth:`list` always returns an empty list
        * :meth:`restore`, :meth:`delete` and :meth:`download` always fail
        * :meth:`list_all` works, but only reports backups of *deleted* configurations

        Verify with :meth:`list` right after :meth:`create`: an empty list on a
        configuration you just backed up means the server is affected. Restoring such a
        backup requires deleting the configuration first, so that it shows up under
        ``list_all().non_existing_configurations``, or copying the file in by hand.
    """

    async def list(self, configuration: str) -> list[Backup]:
        """Return every backup of one configuration.

        Always empty on WGDashboard ≤ 4.3.3 — see the class docstring.
        """
        data = await self._client._get(
            "/api/getWireguardConfigurationBackup",
            params={"configurationName": configuration},
        )
        return [Backup.model_validate(item) for item in data or []]

    async def list_all(self) -> AllBackups:
        """Return every backup on the server.

        Backups are split into those whose configuration still exists and those left
        over from deleted configurations — the latter can still be restored.
        """
        data = await self._client._get("/api/getAllWireguardConfigurationBackup")
        return AllBackups.model_validate(data or {})

    async def create(self, configuration: str) -> list[Backup]:
        """Take a new backup and return the configuration's backups afterwards.

        The returned list is empty on WGDashboard ≤ 4.3.3 even though the backup was
        written — see the class docstring.
        """
        data = await self._client._get(
            "/api/createWireguardConfigurationBackup",
            params={"configurationName": configuration},
        )
        return [Backup.model_validate(item) for item in data or []]

    async def restore(self, configuration: str, backup_file_name: str) -> None:
        """Restore a configuration from a backup, replacing its current state.

        Fails with ``"Restore backup failed"`` on WGDashboard ≤ 4.3.3 — see the class
        docstring.
        """
        await self._client._post(
            "/api/restoreWireguardConfigurationBackup",
            json={
                "ConfigurationName": configuration,
                "BackupFileName": backup_file_name,
            },
        )

    async def delete(self, configuration: str, backup_file_name: str) -> None:
        """Delete a single backup file."""
        await self._client._post(
            "/api/deleteWireguardConfigurationBackup",
            json={
                "ConfigurationName": configuration,
                "BackupFileName": backup_file_name,
            },
        )

    async def download(self, configuration: str, backup_file_name: str) -> str:
        """Ask the server to package a backup as a ZIP archive.

        Returns:
            The generated archive's file name, which the dashboard serves for download.
        """
        return await self._client._get(
            "/api/downloadWireguardConfigurationBackup",
            params={
                "configurationName": configuration,
                "backupFileName": backup_file_name,
            },
        )
