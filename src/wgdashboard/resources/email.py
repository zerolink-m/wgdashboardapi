"""Sending peer configurations over the dashboard's email service."""

from __future__ import annotations

from .base import Resource


class EmailResource(Resource):
    """Email peer configuration files to users.

    Accessed as ``client.email``. Requires SMTP to be configured under
    *Settings → Email* on the dashboard.

    Message bodies are Jinja2 templates rendered against the peer, with
    ``{{ peer.name }}``, ``{{ peer.allowed_ip }}``, ``{{ configurationFile.fileName }}``
    and ``{{ configurationFile.file }}`` available.
    """

    async def is_ready(self) -> bool:
        """Whether the SMTP server, port, encryption, username and password are all set.

        Returns ``False`` when email is not configured — this is not an error.
        """
        return await self._client._probe("/api/email/ready")

    async def send(
        self,
        *,
        receiver: str,
        subject: str,
        body: str,
        configuration: str,
        peer_id: str,
        include_attachment: bool = True,
    ) -> None:
        """Email a peer's configuration.

        Args:
            receiver: Recipient address.
            subject: Message subject.
            body: Message body, as a Jinja2 template.
            configuration: Name of the peer's configuration.
            peer_id: Peer public key.
            include_attachment: Attach the ``.conf`` file to the message.
        """
        await self._client._post(
            "/api/email/send",
            json={
                "Receiver": receiver,
                "Subject": subject,
                "Body": body,
                "IncludeAttachment": include_attachment,
                "ConfigurationName": configuration,
                "Peer": peer_id,
            },
        )

    async def preview_body(self, *, configuration: str, peer_id: str, body: str) -> str:
        """Render a body template against a peer without sending anything.

        Returns:
            The rendered text.
        """
        return await self._client._post(
            "/api/email/previewBody",
            json={
                "ConfigurationName": configuration,
                "Peer": peer_id,
                "Body": body,
            },
        )
