import asyncio
import json
import time

from channels.generic.websocket import AsyncWebsocketConsumer

from users.models import User


class EventsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if (
            user is None
            or not user.is_authenticated
            or user.password_change_required
            or user.role not in {User.Role.BOSS, User.Role.SUPERADMIN, User.Role.COLLABORATOR}
        ):
            await self.close(code=4401)
            return

        self.group_name = (
            "realtime.managers"
            if user.role in {User.Role.BOSS, User.Role.SUPERADMIN}
            else "realtime.collaborators"
        )
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        expires_at = self.scope.get("jwt_expires_at")
        if expires_at is not None:
            delay = max(0, expires_at - time.time())
            self.expiry_task = asyncio.create_task(self._close_when_token_expires(delay))

    async def disconnect(self, close_code):
        expiry_task = getattr(self, "expiry_task", None)
        if expiry_task:
            expiry_task.cancel()
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def _close_when_token_expires(self, delay):
        await asyncio.sleep(delay)
        await self.close(code=4401)

    async def receive(self, text_data=None, bytes_data=None):
        await self.close(code=4400)

    async def realtime_event(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
