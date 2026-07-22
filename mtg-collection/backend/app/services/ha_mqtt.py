"""Shared MQTT connection layer for the Home Assistant integration.

Every HA-facing publish goes through here.  :func:`run_manager` owns a single
long-lived connection that

* publishes a retained ``online`` birth message on ``{prefix}/status`` and
  registers ``offline`` as its Last Will, so HA marks all entities unavailable
  when the add-on dies unexpectedly, and
* receives the messages for all registered subscriptions (service calls today,
  command topics of the game-logger entities later).

Callers that publish while the manager is not connected — a request handler
during startup, a standalone script — transparently fall back to a short-lived
connection, so :func:`session` works in every context.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)

# handler(topic, payload) — topic is the concrete topic, not the filter
MessageHandler = Callable[[str, bytes], Awaitable[None]]

PAYLOAD_ONLINE = "online"
PAYLOAD_OFFLINE = "offline"

RECONNECT_DELAY_S = 30

_aiomqtt_module: Any = None
_aiomqtt_checked = False

# Client owned by run_manager() while connected; None otherwise.
_client: Any = None
_manager_task: asyncio.Task | None = None
_handlers: list[tuple[str, MessageHandler]] = []


def _aiomqtt() -> Any:
    """Import aiomqtt once, returning None (with one warning) if unavailable."""
    global _aiomqtt_module, _aiomqtt_checked
    if not _aiomqtt_checked:
        _aiomqtt_checked = True
        try:
            import aiomqtt

            _aiomqtt_module = aiomqtt
        except ImportError:
            logger.warning("aiomqtt not installed, MQTT integration disabled")
            _aiomqtt_module = None
    return _aiomqtt_module


def is_available() -> bool:
    """True when MQTT is enabled in the add-on options and aiomqtt is importable."""
    return bool(get_settings().mqtt_enabled) and _aiomqtt() is not None


def topic_prefix() -> str:
    return get_settings().mqtt_topic_prefix


def status_topic() -> str:
    """Availability topic referenced by every discovery payload."""
    return f"{topic_prefix()}/status"


def _client_kwargs() -> dict[str, Any]:
    settings = get_settings()
    return {
        "hostname": settings.mqtt_host,
        "port": settings.mqtt_port,
        "username": settings.mqtt_username or None,
        "password": settings.mqtt_password or None,
    }


def register_handler(topic_filter: str, handler: MessageHandler) -> None:
    """Register a subscription.  Must be called before :func:`start`."""
    _handlers.append((topic_filter, handler))


@asynccontextmanager
async def session() -> AsyncIterator[Any]:
    """Yield a connected client — the manager's if available, else a one-shot.

    Callers are expected to check :func:`is_available` first; publishing many
    messages inside a single ``session()`` block keeps the fallback path down to
    one connection instead of one per message.
    """
    client = _client
    if client is not None:
        yield client
        return

    async with _aiomqtt().Client(**_client_kwargs()) as one_shot:
        yield one_shot


async def publish(topic: str, payload: Any, retain: bool = False, qos: int = 0) -> None:
    """Publish a single message, logging (not raising) on failure."""
    if not is_available():
        return
    try:
        async with session() as client:
            await client.publish(topic, payload=payload, retain=retain, qos=qos)
    except Exception:
        logger.exception("MQTT publish to %s failed", topic)


async def _dispatch(message: Any) -> None:
    for topic_filter, handler in _handlers:
        if message.topic.matches(topic_filter):
            try:
                await handler(message.topic.value, message.payload or b"")
            except Exception:
                logger.exception("MQTT handler for %s failed", topic_filter)


async def run_manager() -> None:
    """Hold the MQTT connection open, reconnecting until cancelled."""
    global _client
    if not is_available():
        return

    aiomqtt = _aiomqtt()
    availability = status_topic()
    will = aiomqtt.Will(topic=availability, payload=PAYLOAD_OFFLINE, qos=1, retain=True)

    while True:
        try:
            async with aiomqtt.Client(**_client_kwargs(), will=will) as client:
                _client = client
                await client.publish(availability, payload=PAYLOAD_ONLINE, qos=1, retain=True)
                for topic_filter, _ in _handlers:
                    await client.subscribe(topic_filter)
                logger.info(
                    "MQTT manager connected (%d subscription(s)), availability on %s",
                    len(_handlers),
                    availability,
                )
                async for message in client.messages:
                    await _dispatch(message)
        # CancelledError is a BaseException and intentionally propagates here,
        # so shutdown() stops the loop instead of triggering a reconnect.
        except Exception:
            logger.exception(
                "MQTT manager disconnected, reconnecting in %ds", RECONNECT_DELAY_S
            )
        finally:
            _client = None
        await asyncio.sleep(RECONNECT_DELAY_S)


def start() -> None:
    """Start the manager task (no-op when MQTT is disabled or already running)."""
    global _manager_task
    if not is_available() or (_manager_task is not None and not _manager_task.done()):
        return
    _manager_task = asyncio.create_task(run_manager())


async def shutdown() -> None:
    """Mark the add-on offline and stop the manager.

    A clean disconnect does not trigger the Last Will, so the ``offline`` state
    has to be published explicitly — otherwise HA would keep showing stale
    values after a graceful add-on stop.
    """
    global _manager_task
    if is_available():
        await publish(status_topic(), PAYLOAD_OFFLINE, retain=True, qos=1)

    task = _manager_task
    _manager_task = None
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
