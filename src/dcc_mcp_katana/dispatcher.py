"""Katana main-thread dispatcher backed by the native event queue."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import BoundedSemaphore, Event, Lock, current_thread, main_thread
from typing import Any, Callable, Optional

MAX_PENDING_CALLS = 32
DEFAULT_TIMEOUT_SECONDS = 30.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 1800.0


@dataclass
class _PendingCall:
    callback: Callable[..., Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    completed: Event
    result: dict[str, Any]
    state_lock: Lock = field(default_factory=Lock)
    started: bool = False
    cancelled: bool = False
    capacity_released: bool = False


class KatanaDispatcher:
    """Execute work from Katana's ``Utils.EventModule`` processing loop."""

    event_type = "dcc_mcp_katana_call"

    def __init__(self, max_pending: int = MAX_PENDING_CALLS) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        self._installed = False
        self._max_pending = max_pending
        self._capacity = BoundedSemaphore(max_pending)

    def install(self) -> None:
        if self._installed:
            return
        from Katana import Utils

        Utils.EventModule.RegisterEventHandler(self._run, eventType=self.event_type)
        self._installed = True

    def uninstall(self) -> None:
        if not self._installed:
            return
        from Katana import Utils

        Utils.EventModule.UnregisterEventHandler(self._run, eventType=self.event_type)
        self._installed = False

    def dispatch_callable(self, callback: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        timeout = _coerce_timeout(kwargs.get("timeout_hint_secs"))
        for key in (
            "context",
            "action_name",
            "skill_name",
            "execution",
            "timeout_hint_secs",
            "affinity",
            "thread_affinity",
        ):
            kwargs.pop(key, None)
        if current_thread() is main_thread():
            return callback(*args, **kwargs)
        if not self._installed:
            raise RuntimeError("Katana event dispatcher is not installed")
        if not self._capacity.acquire(blocking=False):
            raise RuntimeError(
                f"Katana main-thread queue is full ({self._max_pending} pending calls)"
            )

        pending = _PendingCall(callback, args, kwargs, Event(), {})
        from Katana import Utils

        try:
            Utils.EventModule.QueueEvent(self.event_type, id(pending), pending=pending)
        except Exception:
            self._capacity.release()
            raise
        if not pending.completed.wait(timeout):
            with pending.state_lock:
                if not pending.started:
                    pending.cancelled = True
                    pending.capacity_released = True
                    self._capacity.release()
                    raise RuntimeError(
                        "Timed out before Katana started the main-thread operation; "
                        "the operation was cancelled"
                    )
            raise RuntimeError(
                "Timed out after Katana started the main-thread operation; "
                "the final host outcome is unknown"
            )
        if "error" in pending.result:
            raise pending.result["error"]
        return pending.result["value"]

    def _run(
        self,
        _event_type: str,
        _event_id: int,
        pending: Optional[_PendingCall] = None,
        **_: Any,
    ) -> None:
        if pending is None:
            return
        with pending.state_lock:
            if pending.cancelled:
                if not pending.capacity_released:
                    self._capacity.release()
                    pending.capacity_released = True
                pending.completed.set()
                return
            pending.started = True
        try:
            pending.result["value"] = pending.callback(*pending.args, **pending.kwargs)
        except Exception as error:
            pending.result["error"] = error
        finally:
            with pending.state_lock:
                if not pending.capacity_released:
                    self._capacity.release()
                    pending.capacity_released = True
            pending.completed.set()


def _coerce_timeout(value: Any) -> float:
    if value is None:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError("timeout_hint_secs must be numeric") from error
    return max(MIN_TIMEOUT_SECONDS, min(timeout, MAX_TIMEOUT_SECONDS))
