import time
import uuid
from typing import TYPE_CHECKING, Any

from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.astr_message_event import AstrMessageEvent
from astrbot.core.platform.astrbot_message import AstrBotMessage, MessageMember
from astrbot.core.platform.message_session import MessageSession
from astrbot.core.platform.message_type import MessageType
from astrbot.core.platform.platform_metadata import PlatformMetadata

if TYPE_CHECKING:
    from astrbot.core.db import BaseDatabase


class CronMessageEvent(AstrMessageEvent):
    """Synthetic event used when a cron job triggers the main agent loop."""

    def __init__(
        self,
        *,
        context,
        session: MessageSession,
        message: str,
        sender_id: str = "astrbot",
        sender_name: str = "Scheduler",
        extras: dict[str, Any] | None = None,
        message_type: MessageType = MessageType.FRIEND_MESSAGE,
        db: "BaseDatabase | None" = None,
        job_id: str | None = None,
    ) -> None:
        # Use the session's platform name instead of hardcoded "cron"
        platform_meta = PlatformMetadata(
            name=session.platform_name,
            description="CronJob",
            id=session.platform_id,
        )

        msg_obj = AstrBotMessage()
        msg_obj.type = message_type
        msg_obj.self_id = sender_id
        msg_obj.session_id = session.session_id
        msg_obj.message_id = uuid.uuid4().hex
        msg_obj.sender = MessageMember(user_id=session.session_id, nickname=sender_name)
        msg_obj.message = [Plain(message)]
        msg_obj.message_str = message
        msg_obj.raw_message = message
        msg_obj.timestamp = int(time.time())

        super().__init__(message, msg_obj, platform_meta, session.session_id)

        # Ensure we use the original session for sending messages
        self.session = session
        self.context_obj = context
        self.is_at_or_wake_command = True
        self.is_wake = True

        if extras:
            self._extras.update(extras)

        # Track cron job completion via first send
        self._db = db
        self._job_id = job_id
        self._cron_status_reported = False

    async def send(self, message: MessageChain) -> None:
        if message is None:
            return
        await self.context_obj.send_message(self.session, message)
        await super().send(message)
        await self._mark_cron_completed()

    async def send_streaming(self, generator, use_fallback: bool = False) -> None:
        async for chain in generator:
            await self.send(chain)

    async def _mark_cron_completed(self) -> None:
        """Mark the cron job as completed in DB on first successful send."""
        if self._cron_status_reported or not self._db or not self._job_id:
            return
        self._cron_status_reported = True
        try:
            await self._db.update_cron_job(self._job_id, status="completed")
        except Exception:
            pass  # best-effort; do not break message delivery


__all__ = ["CronMessageEvent"]
