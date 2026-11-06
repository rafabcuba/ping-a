from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Optional, Sequence, Tuple

from . import __version__
from .audio import (
    AudioError,
    AudioPlayer,
    NullBackend,
    SoundSource,
    create_backend,
    default_sound,
    load_sound,
)
from .events import MODES, EventDecider
from .prober import ProbeError, ProbeResult, Prober
from .stats import Stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ping-a",
        description=(
            "Hace ping a un host y reproduce una alarma sonora "
            "personalizada (WAV/MP3)."
        ),
        epilog=(
            "Ejemplo: ping-a 1.1.1.1 --sound alarma.mp3 --volume 0.9"
        ),
    )
    parser.add_argument("host", help="host o IP a monitorear")
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=1.0,
        metavar="SEG",
        help="intervalo entre pings (def. 1.0, mínimo 0.2)",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=0,
        metavar="N",
        help="número de pings (def. 0 = infinito)",
    )
    parser.add_argument(
        "-W",
        "--timeout",
        type=float,
        default=2.0,
        metavar="SEG",
        help="espera por respuesta (def. 2)",
    )
    parser.add_argument(
        "-s",
        "--size",
        type=int,
        default=56,
        metavar="BYTES",
        help="tamaño del payload ICMP (def. 56)",
    )
    parser.add_argument(
        "-a",
        "--audible",
        action="store_true",
        help="alias de --on reply (ya es el comportamiento por defecto)",
    )
    parser.add_argument(
        "-f",
        "--sound",
        metavar="ARCHIVO",
        help="alarma WAV/MP3/OGG (def. pitido sintetizado)",
    )
    parser.add_argument(
        "--sound-down",
        metavar="ARCHIVO",
        help="sonido específico para caída (modos change/failure)",
    )
    parser.add_argument(
        "--sound-up",
        metavar="ARCHIVO",
        help="sonido específico para recuperación (modos change/failure)",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=0.8,
        metavar="0..1",
        help="volumen de reproducción (def. 0.8)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help="repeticiones por evento (def. 1)",
    )
    parser.add_argument(
        "--tone",
        type=float,
        default=880.0,
        metavar="HZ",
        help="frecuencia del pitido sintetizado (def. 880)",
    )
    parser.add_argument(
        "--on",
        choices=MODES,
        default=None,
        metavar="MODO",
        help="reply|timeout|change|failure (def. reply)",
    )
    parser.add_argument(
        "--latency-threshold",
        type=float,
        default=None,
        metavar="MS",
        help="solo suena si el RTT supera este valor",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "pygame", "ffplay", "bell", "null"),
        default="auto",
        help="motor de audio (def. auto: pygame -> ffplay -> bell)",
    )
    parser.add_argument(
        "--device",
        metavar="NOMBRE",
        help="dispositivo de salida (solo backend pygame)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="no reproducir sonido (tests/CI)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emitir una línea JSON por evento",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def validate_args(
    parser: argparse.ArgumentParser, args: argparse.Namespace
) -> None:
    if args.interval < 0.2:
        parser.error("--interval debe ser >= 0.2 segundos")
    if args.count < 0:
        parser.error("--count debe ser >= 0")
    if args.timeout <= 0:
        parser.error("--timeout debe ser > 0")
    if not 0 <= args.size <= 65507:
        parser.error("--size debe estar entre 0 y 65507")
    if not 0.0 <= args.volume <= 1.0:
        parser.error("--volume debe estar entre 0 y 1")
    if args.repeat < 1:
        parser.error("--repeat debe ser >= 1")
    if args.tone <= 0:
        parser.error("--tone debe ser > 0")
    if args.latency_threshold is not None and args.latency_threshold < 0:
        parser.error("--latency-threshold debe ser >= 0")
    if args.on is None:
        args.on = "reply"


def _resolve_sounds(
    args: argparse.Namespace,
) -> Tuple[SoundSource, SoundSource, SoundSource]:
    fallback: Optional[SoundSource] = None

    def get_fallback() -> SoundSource:
        nonlocal fallback
        if fallback is None:
            fallback = default_sound(args.tone)
        return fallback

    def resolve(path: Optional[str], label: str) -> SoundSource:
        if path:
            try:
                return load_sound(path)
            except AudioError as exc:
                print(
                    f"ping-a: aviso: {exc}; "
                    f"se usará el pitido sintetizado para {label}",
                    file=sys.stderr,
                )
        return get_fallback()

    normal = resolve(args.sound, "el pitido normal")
    down = (
        resolve(args.sound_down, "la caída")
        if args.sound_down
        else normal
    )
    up = (
        resolve(args.sound_up, "la recuperación")
        if args.sound_up
        else normal
    )
    return normal, down, up


def _make_player(args: argparse.Namespace) -> AudioPlayer:
    if args.no_audio:
        return AudioPlayer(NullBackend(), repeat=args.repeat)
    try:
        backend = create_backend(
            args.backend, volume=args.volume, device=args.device
        )
    except AudioError as exc:
        print(
            f"ping-a: audio: {exc}; se continuará sin sonido",
            file=sys.stderr,
        )
        backend = NullBackend()
    return AudioPlayer(backend, repeat=args.repeat)


def _print_header(prober: Prober, size: int, backend_name: str) -> None:
    target = ""
    if prober.target_ip:
        target = f" ({prober.target_ip})"
    print(
        f"PING {prober.host}{target} {size} bytes de datos.  "
        f"[audio: {backend_name}]"
    )


def _format_result(
    result: ProbeResult, event: Optional[str], sound_enabled: bool
) -> str:
    marker = "  🔊" if event is not None and sound_enabled else ""
    if result.ok:
        parts = [f"{result.size or '?'} bytes from {result.ip or '?'}:"]
        parts.append(f"icmp_seq={result.seq}")
        if result.ttl is not None:
            parts.append(f"ttl={result.ttl}")
        if result.rtt_ms is not None:
            parts.append(f"time={result.rtt_ms:.3f} ms")
        return " ".join(parts) + marker
    detail = f" ({result.error})" if result.error else ""
    return (
        f"Tiempo de espera agotado para icmp_seq={result.seq}{detail}"
        + marker
    )


def run(args: argparse.Namespace) -> int:
    prober = Prober(args.host, timeout=args.timeout, size=args.size)
    normal, down, up = _resolve_sounds(args)
    player = _make_player(args)
    decider = EventDecider(args.on, args.latency_threshold)
    stats = Stats()
    sounds = {
        "reply": normal,
        "timeout": down,
        "down": down,
        "up": up,
    }

    seq = 1
    try:
        if not args.json:
            _print_header(prober, args.size, player.name)

        while True:
            if args.count and seq > args.count:
                break

            started = time.monotonic()
            result = prober.probe(seq)
            stats.record(result.ok, result.rtt_ms)
            event = decider.on_result(result.ok, result.rtt_ms)
            if event is not None:
                player.play(sounds[event])

            if args.json:
                payload = {
                    "timestamp": round(time.time(), 3),
                    "seq": result.seq,
                    "ok": result.ok,
                    "rtt_ms": result.rtt_ms,
                    "ip": result.ip,
                    "ttl": result.ttl,
                    "size": result.size,
                    "event": event,
                    "loss_percent": round(stats.loss_percent, 2),
                }
                print(
                    json.dumps(payload, ensure_ascii=False), flush=True
                )
            else:
                print(
                    _format_result(
                        result, event, player.name != "null"
                    ),
                    flush=True,
                )

            seq += 1
            if args.count and seq > args.count:
                break

            remaining = args.interval - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    finally:
        player.close()

    summary = stats.summary(prober.host)
    if args.json:
        print(summary, file=sys.stderr)
    else:
        print()
        print(summary)

    if stats.transmitted == 0:
        return 0
    if stats.received < stats.transmitted:
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(parser, args)
    try:
        return run(args)
    except ProbeError as exc:
        print(f"ping-a: {exc}", file=sys.stderr)
        return 2
    except AudioError as exc:
        print(f"ping-a: audio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
