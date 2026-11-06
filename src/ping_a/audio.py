from __future__ import annotations

import array
import hashlib
import io
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import wave
from typing import Dict, Optional

SAMPLE_RATE = 44100
REPEAT_GAP = 0.08


class AudioError(RuntimeError):
    """Error de audio que se puede recuperar o reportar al usuario."""


# ---------------------------------------------------------------------------
# Generación y carga de sonidos
# ---------------------------------------------------------------------------


def _render_tone(
    freq: float,
    duration: float,
    amplitude: float = 0.55,
    sample_rate: int = SAMPLE_RATE,
) -> array.array:
    samples = array.array("h")
    total = max(1, int(duration * sample_rate))
    fade = min(total // 2, max(1, int(0.005 * sample_rate)))
    for index in range(total):
        if index < fade:
            envelope = index / fade
        elif index >= total - fade:
            envelope = (total - index) / fade
        else:
            envelope = 1.0
        value = (
            amplitude
            * envelope
            * math.sin(2.0 * math.pi * freq * index / sample_rate)
        )
        samples.append(int(max(-1.0, min(1.0, value)) * 32767))
    return samples


def pcm_to_wav(pcm: array.array, sample_rate: int = SAMPLE_RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()


def generate_beep_wav(
    freq: float = 880.0,
    duration: float = 0.09,
    gap: float = 0.04,
    second_freq: Optional[float] = None,
    sample_rate: int = SAMPLE_RATE,
    amplitude: float = 0.55,
) -> bytes:
    """Genera un doble pitido propio (sin depender del sonido del sistema)."""
    if second_freq is None:
        second_freq = freq * 1.335
    pcm = array.array("h")
    pcm.extend(_render_tone(freq, duration, amplitude, sample_rate))
    silence = int(gap * sample_rate)
    if silence > 0:
        pcm.extend(array.array("h", [0]) * silence)
    pcm.extend(_render_tone(second_freq, duration, amplitude, sample_rate))
    return pcm_to_wav(pcm, sample_rate)


def wav_duration(data: bytes) -> float:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if rate <= 0:
                raise AudioError("WAV con frecuencia inválida")
            return frames / float(rate)
    except AudioError:
        raise
    except Exception as exc:
        raise AudioError(f"WAV inválido: {exc}") from exc


class SoundSource:
    """Sonido ya decodificado a WAV PCM 16-bit mono, listo para reproducir."""

    def __init__(self, wav_bytes: bytes, name: str = "sonido") -> None:
        self.wav_bytes = wav_bytes
        self.name = name
        self.duration = wav_duration(wav_bytes)


def load_sound(path: str) -> SoundSource:
    """Carga un WAV/MP3/OGG y lo normaliza a WAV PCM con ffmpeg.

    Si ffmpeg no está disponible solo se aceptan archivos WAV.
    """
    resolved = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(resolved):
        raise AudioError(f"no existe el archivo de sonido: {path}")
    if not os.path.isfile(resolved):
        raise AudioError(f"no es un archivo: {path}")

    name = os.path.basename(resolved)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        command = [
            ffmpeg,
            "-v",
            "error",
            "-i",
            resolved,
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, timeout=30
            )
        except subprocess.TimeoutExpired as exc:
            raise AudioError(
                f"ffmpeg tardó demasiado al decodificar {name}"
            ) from exc
        if completed.returncode == 0 and completed.stdout:
            return SoundSource(completed.stdout, name)
        detail = (completed.stderr or b"").decode(
            "utf-8", "replace"
        ).strip()
        raise AudioError(
            f"no se pudo decodificar {name}: "
            f"{detail or 'formato no soportado'}"
        )

    if not resolved.lower().endswith(".wav"):
        raise AudioError(
            "se necesita ffmpeg para leer formatos distintos de WAV"
        )
    with open(resolved, "rb") as file_handle:
        data = file_handle.read()
    return SoundSource(data, name)


def default_sound(tone: float = 880.0) -> SoundSource:
    return SoundSource(
        generate_beep_wav(freq=tone, second_freq=tone * 1.335),
        f"pitido sintetizado ({tone:.0f} Hz)",
    )


# ---------------------------------------------------------------------------
# Caché de WAV para el backend ffplay
# ---------------------------------------------------------------------------


def cache_dir() -> str:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache"
    )
    path = os.path.join(base, "ping-a")
    os.makedirs(path, exist_ok=True)
    return path


def source_path(source: SoundSource) -> str:
    digest = hashlib.sha1(source.wav_bytes).hexdigest()[:16]
    path = os.path.join(cache_dir(), f"{digest}.wav")
    if not os.path.exists(path):
        temporary = f"{path}.{os.getpid()}.tmp"
        with open(temporary, "wb") as file_handle:
            file_handle.write(source.wav_bytes)
        os.replace(temporary, path)
    return path


# ---------------------------------------------------------------------------
# Backends de reproducción
# ---------------------------------------------------------------------------


class AudioBackend:
    name = "null"

    def play(self, source: SoundSource) -> None:
        return None

    def close(self) -> None:
        return None


class NullBackend(AudioBackend):
    name = "null"


class BellBackend(AudioBackend):
    name = "bell"

    def play(self, source: SoundSource) -> None:
        try:
            sys.stderr.write("\a")
            sys.stderr.flush()
        except Exception:
            pass


class PygameBackend(AudioBackend):
    name = "pygame"

    def __init__(self, volume: float = 0.8, device: Optional[str] = None) -> None:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame  # type: ignore
        except Exception as exc:
            raise AudioError("pygame no está instalado") from exc

        self._pygame = pygame
        self._volume = max(0.0, min(1.0, volume))
        self._sounds: Dict[int, object] = {}
        options = {
            "frequency": SAMPLE_RATE,
            "size": -16,
            "channels": 1,
            "buffer": 512,
        }
        if device:
            options["devicename"] = device
        try:
            pygame.mixer.init(**options)
        except Exception as exc:
            raise AudioError(
                f"no se pudo inicializar pygame.mixer: {exc}"
            ) from exc

    def _sound(self, source: SoundSource):
        key = id(source)
        sound = self._sounds.get(key)
        if sound is not None:
            return sound
        try:
            sound = self._pygame.mixer.Sound(file=io.BytesIO(source.wav_bytes))
        except Exception:
            try:
                sound = self._pygame.mixer.Sound(source_path(source))
            except Exception as exc:
                raise AudioError(
                    f"no se pudo cargar el sonido: {exc}"
                ) from exc
        sound.set_volume(self._volume)
        self._sounds[key] = sound
        return sound

    def play(self, source: SoundSource) -> None:
        self._sound(source).play()

    def close(self) -> None:
        try:
            self._pygame.mixer.quit()
        except Exception:
            pass


class FFplayBackend(AudioBackend):
    name = "ffplay"

    def __init__(self, volume: float = 0.8) -> None:
        executable = shutil.which("ffplay")
        if not executable:
            raise AudioError("ffplay no está disponible en PATH")
        self._executable = executable
        self._volume = int(round(max(0.0, min(1.0, volume)) * 100))
        self._process: Optional[subprocess.Popen] = None

    def play(self, source: SoundSource) -> None:
        if self._process is not None and self._process.poll() is None:
            return  # todavía suena: no solapar
        command = [
            self._executable,
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-volume",
            str(self._volume),
            source_path(source),
        ]
        self._process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

    def close(self) -> None:
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()


def create_backend(
    name: str = "auto",
    volume: float = 0.8,
    device: Optional[str] = None,
) -> AudioBackend:
    name = (name or "auto").lower()
    if name == "null":
        return NullBackend()
    if name == "bell":
        return BellBackend()
    if name == "pygame":
        return PygameBackend(volume, device)
    if name == "ffplay":
        return FFplayBackend(volume)
    if name != "auto":
        raise AudioError(f"backend desconocido: {name}")

    for factory in (
        lambda: PygameBackend(volume, device),
        lambda: FFplayBackend(volume),
    ):
        try:
            return factory()
        except AudioError:
            continue
    return BellBackend()


# ---------------------------------------------------------------------------
# Reproductor con hilo y cola (no bloquea el sondeo)
# ---------------------------------------------------------------------------


class AudioPlayer:
    def __init__(self, backend: AudioBackend, repeat: int = 1) -> None:
        self.backend = backend
        self.repeat = max(1, int(repeat))
        self._queue: "queue.Queue[Optional[SoundSource]]" = queue.Queue(
            maxsize=32
        )
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="ping-a-audio", daemon=True
        )
        self._thread.start()

    @property
    def name(self) -> str:
        return self.backend.name

    def play(self, source: SoundSource) -> None:
        if self._stopped.is_set():
            return
        try:
            self._queue.put_nowait(source)
        except queue.Full:
            pass

    def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while not self._stopped.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.05))

    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                source = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if source is None:
                    break
                for index in range(self.repeat):
                    if self._stopped.is_set():
                        break
                    try:
                        self.backend.play(source)
                    except Exception:
                        pass
                    if index + 1 < self.repeat:
                        self._sleep(source.duration + REPEAT_GAP)
            finally:
                self._queue.task_done()

    def close(self) -> None:
        self._stopped.set()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=1.5)
        try:
            self.backend.close()
        except Exception:
            pass
