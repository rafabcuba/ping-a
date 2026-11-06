from __future__ import annotations

from typing import Optional

MODES = ("reply", "timeout", "change", "failure")


class EventDecider:
    """Decide si un resultado de sondeo debe disparar la alarma.

    Modos:
      reply   -> cada respuesta correcta (equivalente a `ping -a`)
      timeout -> cada intento sin respuesta
      change  -> solo transiciones arriba/abajo (el primer resultado fija estado)
      failure -> inicio de caída y recuperación, sin repetir durante la caída
    """

    def __init__(
        self,
        mode: str = "reply",
        latency_threshold_ms: Optional[float] = None,
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"modo desconocido: {mode}")
        self.mode = mode
        self.latency_threshold_ms = latency_threshold_ms
        self.state: Optional[str] = None
        self.seen = False

    def on_result(self, ok: bool, rtt_ms: Optional[float]) -> Optional[str]:
        new_state = "up" if ok else "down"
        event: Optional[str] = None

        if self.mode == "reply":
            if ok and rtt_ms is not None:
                if (
                    self.latency_threshold_ms is None
                    or rtt_ms > self.latency_threshold_ms
                ):
                    event = "reply"
        elif self.mode == "timeout":
            if not ok:
                event = "timeout"
        elif self.mode == "change":
            if self.seen and new_state != self.state:
                event = new_state
        elif self.mode == "failure":
            if not self.seen:
                if new_state == "down":
                    event = "down"
            elif new_state != self.state:
                event = new_state

        self.state = new_state
        self.seen = True
        return event
