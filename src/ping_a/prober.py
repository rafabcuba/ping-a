from __future__ import annotations

import os
import re
import socket
import subprocess
from dataclasses import dataclass
from typing import List, Optional

_TIME_RE = re.compile(r"time[=<]\s*([0-9]+(?:\.[0-9]+)?)\s*ms")
_TTL_RE = re.compile(r"ttl=(\d+)")
_SIZE_RE = re.compile(r"(\d+)\s+bytes\s+from")


class ProbeError(RuntimeError):
    """Error fatal (DNS, red, ping ausente) que debe detener el programa."""


@dataclass
class ProbeResult:
    seq: int
    ok: bool
    rtt_ms: Optional[float] = None
    ip: Optional[str] = None
    ttl: Optional[int] = None
    size: Optional[int] = None
    error: Optional[str] = None


def parse_reply(stdout: str) -> Optional[dict]:
    """Extrae rtt/ttl/tamaño de la salida de ping. Devuelve None si no hay reply."""
    match = _TIME_RE.search(stdout)
    if not match:
        return None
    ttl = _TTL_RE.search(stdout)
    size = _SIZE_RE.search(stdout)
    return {
        "rtt_ms": float(match.group(1)),
        "ttl": int(ttl.group(1)) if ttl else None,
        "size": int(size.group(1)) if size else None,
    }


def build_command(
    host: str, timeout: float, size: int, ipv6: bool = False
) -> List[str]:
    command = [
        "ping",
        "-n",
        "-c",
        "1",
        "-W",
        f"{timeout:g}",
        "-s",
        str(size),
    ]
    if ipv6:
        command.append("-6")
    command.append(host)
    return command


class Prober:
    """Ejecuta el ping del sistema (con cap_net_raw) una vez por sondeo."""

    def __init__(self, host: str, timeout: float = 2.0, size: int = 56) -> None:
        self.host = host
        self.timeout = timeout
        self.size = size
        self.ipv6 = ":" in host
        self.target_ip: Optional[str] = None
        self._resolve()

    def _resolve(self) -> None:
        """Resuelve el host una sola vez para mostrarlo y elegir IPv4/IPv6."""
        try:
            infos = socket.getaddrinfo(self.host, None)
        except socket.gaierror:
            return
        if not infos:
            return
        chosen = infos[0]
        if ":" not in self.host:
            for info in infos:
                if info[0] == socket.AF_INET:
                    chosen = info
                    break
        self.ipv6 = chosen[0] == socket.AF_INET6
        self.target_ip = chosen[4][0]

    def command(self) -> List[str]:
        return build_command(self.host, self.timeout, self.size, self.ipv6)

    def probe(self, seq: int) -> ProbeResult:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        try:
            completed = subprocess.run(
                self.command(),
                capture_output=True,
                text=True,
                timeout=self.timeout + 5,
                env=env,
            )
        except FileNotFoundError as exc:
            raise ProbeError("no se encontró el comando 'ping' en PATH") from exc
        except subprocess.TimeoutExpired:
            return ProbeResult(
                seq=seq,
                ok=False,
                ip=self.target_ip,
                error="tiempo de espera agotado",
            )

        stdout = completed.stdout or ""
        stderr = (completed.stderr or "").strip()

        if completed.returncode == 0:
            parsed = parse_reply(stdout)
            if parsed is None:
                return ProbeResult(
                    seq=seq,
                    ok=False,
                    ip=self.target_ip,
                    error="respuesta no reconocida",
                )
            return ProbeResult(seq=seq, ok=True, ip=self.target_ip, **parsed)

        if completed.returncode == 1:
            return ProbeResult(
                seq=seq,
                ok=False,
                ip=self.target_ip,
                error="sin respuesta",
            )

        raise ProbeError(
            stderr or f"'ping' terminó con código {completed.returncode}"
        )
