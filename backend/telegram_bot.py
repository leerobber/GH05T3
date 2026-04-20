"""Telegram bot — real long-polling worker.
- No webhook needed (container friendly).
- Token stored in Mongo (single-user personal). Start/stop via API.
- First message from any chat auto-locks that chat_id unless allow_open=True.
- Each message routes through GH05T3 chat pipeline.
"""
from __future__ import annotations
import asyncio
import logging
import httpx
from typing import Callable, Awaitable

LOG = logging.getLogger("ghost.telegram")

API = "https://api.telegram.org"


class TelegramPoller:
    def __init__(self, db, on_message: Callable[[int, str, str], Awaitable[str]]):
        """on_message(chat_id, username, text) -> ghost_reply_text."""
        self.db = db
        self.on_message = on_message
        self.task: asyncio.Task | None = None
        self._stop = False

    async def _get_cfg(self) -> dict | None:
        return await self.db.telegram_config.find_one({"_id": "singleton"}, {"_id": 0})

    async def save_cfg(self, cfg: dict):
        await self.db.telegram_config.update_one(
            {"_id": "singleton"}, {"$set": cfg}, upsert=True
        )

    async def status(self) -> dict:
        cfg = await self._get_cfg() or {}
        return {
            "running": bool(self.task and not self.task.done()),
            "locked_chat_id": cfg.get("locked_chat_id"),
            "allow_open": cfg.get("allow_open", False),
            "bot_username": cfg.get("bot_username"),
            "configured": bool(cfg.get("bot_token")),
            "last_error": cfg.get("last_error"),
        }

    async def start(self) -> dict:
        cfg = await self._get_cfg()
        if not cfg or not cfg.get("bot_token"):
            return {"ok": False, "error": "bot token not configured"}
        if self.task and not self.task.done():
            return {"ok": True, "already": True}
        self._stop = False
        self.task = asyncio.create_task(self._run(cfg["bot_token"]))
        return {"ok": True}

    async def stop(self) -> dict:
        self._stop = True
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except Exception:
                pass
            self.task = None
        return {"ok": True}

    async def _run(self, token: str):
        offset = 0
        base = f"{API}/bot{token}"
        # verify token
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{base}/getMe")
                data = r.json()
                if not data.get("ok"):
                    await self.save_cfg({"last_error": data.get("description", "getMe failed")})
                    return
                uname = data["result"].get("username")
                await self.save_cfg({"bot_username": uname, "last_error": None})
        except Exception as e:  # noqa: BLE001
            await self.save_cfg({"last_error": str(e)})
            return

        LOG.info("telegram poller started @%s", uname)
        while not self._stop:
            try:
                async with httpx.AsyncClient(timeout=35) as c:
                    r = await c.get(
                        f"{base}/getUpdates",
                        params={"offset": offset, "timeout": 25},
                    )
                    j = r.json()
                    if not j.get("ok"):
                        await self.save_cfg({"last_error": j.get("description")})
                        await asyncio.sleep(5)
                        continue
                    for upd in j.get("result", []):
                        offset = upd["update_id"] + 1
                        msg = upd.get("message") or upd.get("edited_message")
                        if not msg:
                            continue
                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "")
                        uname_from = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name") or "unknown"

                        cfg = await self._get_cfg() or {}
                        locked = cfg.get("locked_chat_id")
                        if not locked and not cfg.get("allow_open"):
                            await self.save_cfg({"locked_chat_id": chat_id})
                            locked = chat_id
                        if locked and chat_id != locked:
                            await self._send(base, chat_id, "\u26d4 this ghost is locked to another chat.")
                            continue
                        if not text.strip():
                            continue
                        try:
                            reply = await self.on_message(chat_id, uname_from, text)
                        except Exception as e:  # noqa: BLE001
                            reply = f"[ghost error] {e}"
                        await self._send(base, chat_id, reply)
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                LOG.exception("poll loop error")
                await self.save_cfg({"last_error": str(e)})
                await asyncio.sleep(4)
        LOG.info("telegram poller stopped")

    async def _send(self, base: str, chat_id: int, text: str):
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                # chunk if over 3500 chars
                for i in range(0, len(text), 3500):
                    await c.post(
                        f"{base}/sendMessage",
                        json={"chat_id": chat_id, "text": text[i:i + 3500]},
                    )
        except Exception as e:  # noqa: BLE001
            LOG.warning("send failed: %s", e)
