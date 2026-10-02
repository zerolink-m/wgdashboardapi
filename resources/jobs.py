"""Scheduled jobs attached to peers."""

from __future__ import annotations

import uuid
from typing import Any

from ..models import PeerJob, PeerJobLog
from .base import Resource

#: Every key the endpoints read out of the job dict. They index it directly, so a
#: missing key is a 500 — even for the two the server then ignores and fills itself.
JOB_KEYS = (
    "JobID", "Configuration", "Peer", "Field",
    "Operator", "Value", "CreationDate", "ExpireDate", "Action",
)


def _job_payload(job: PeerJob | dict) -> dict[str, Any]:
    """Build a complete job dict, filling in the keys the server insists on."""
    if isinstance(job, PeerJob):
        source: dict[str, Any] = job.model_dump(by_alias=True)
    else:
        source = dict(job)

    payload = {key: source.get(key) for key in JOB_KEYS}
    payload.update({k: v for k, v in source.items() if k not in payload})
    if not payload["JobID"]:
        payload["JobID"] = str(uuid.uuid4())
    return payload


class JobsResource(Resource):
    """Automate peer actions based on traffic or time.

    Accessed as ``client.jobs``. A job reads as *if* ``field`` ``operator`` ``value``
    *then* ``action`` — for example, restrict a peer once it has used 22 GB.
    """

    async def save(self, job: PeerJob | dict) -> list[PeerJob]:
        """Create or update a job.

        The server updates the job when its ``job_id`` already exists and creates one
        otherwise. Leave ``job_id`` unset to create a job — a UUID is generated for you.

        ``creation_date`` is set by the server, and ``expire_date`` is always stored as
        null, so both are ignored here whatever you pass.

        Args:
            job: A :class:`~wgdashboard.models.PeerJob`, or a dict using the API's
                field names (``JobID``, ``Configuration``, ``Peer``, ``Field``,
                ``Operator``, ``Value``, ``Action``).

        Returns:
            The peer's jobs after the change.
        """
        data = await self._client._post(
            "/api/savePeerScheduleJob", json={"Job": _job_payload(job)}
        )
        return [PeerJob.model_validate(item) for item in data or []]

    async def delete(self, job: PeerJob | dict) -> list[PeerJob]:
        """Delete a job.

        Pass the full job object — the server matches on its fields, not on the ID alone.

        Returns:
            The peer's remaining jobs.
        """
        data = await self._client._post(
            "/api/deletePeerScheduleJob", json={"Job": _job_payload(job)}
        )
        return [PeerJob.model_validate(item) for item in data or []]

    async def get_logs(self, configuration: str) -> list[PeerJobLog]:
        """Return the job execution log for a configuration."""
        data = await self._client._get(
            f"/api/getPeerScheduleJobLogs/{self._client._quote(configuration)}"
        )
        return [PeerJobLog.model_validate(item) for item in data or []]
