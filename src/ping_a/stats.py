from __future__ import annotations

import math
import time
from typing import List, Optional, Tuple


class Stats:
    """Acumula los resultados de sondeo y calcula un resumen tipo ping."""

    def __init__(self) -> None:
        self.transmitted = 0
        self.received = 0
        self.rtts: List[float] = []
        self.started = time.monotonic()

    def record(self, ok: bool, rtt_ms: Optional[float] = None) -> None:
        self.transmitted += 1
        if ok and rtt_ms is not None:
            self.received += 1
            self.rtts.append(float(rtt_ms))

    @property
    def lost(self) -> int:
        return self.transmitted - self.received

    @property
    def loss_percent(self) -> float:
        if self.transmitted == 0:
            return 0.0
        return self.lost * 100.0 / self.transmitted

    @property
    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self.started) * 1000)

    def rtt_stats(self) -> Optional[Tuple[float, float, float, float]]:
        if not self.rtts:
            return None
        minimum = min(self.rtts)
        maximum = max(self.rtts)
        average = sum(self.rtts) / len(self.rtts)
        mdev = math.sqrt(
            sum((rtt - average) ** 2 for rtt in self.rtts) / len(self.rtts)
        )
        return minimum, average, maximum, mdev

    def summary(self, host: str) -> str:
        sent = (
            f"{self.transmitted} paquete{'s' if self.transmitted != 1 else ''} "
            f"transmitido{'s' if self.transmitted != 1 else ''}"
        )
        received = (
            f"{self.received} recibido{'s' if self.received != 1 else ''}"
        )
        lines = [
            f"--- estadísticas de ping-a para {host} ---",
            (
                f"{sent}, {received}, "
                f"{self.loss_percent:.0f}% pérdida, "
                f"tiempo {self.elapsed_ms}ms"
            ),
        ]
        rtt = self.rtt_stats()
        if rtt is not None:
            lines.append(
                "rtt mín/med/máx/desv = "
                f"{rtt[0]:.3f}/{rtt[1]:.3f}/{rtt[2]:.3f}/{rtt[3]:.3f} ms"
            )
        return "\n".join(lines)
