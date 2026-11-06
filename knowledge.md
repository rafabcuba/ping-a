# ping-a: Project Knowledge

## What this project is

`ping-a` is a Python CLI tool that pings a host and plays a custom sound (WAV/MP3) when it responds, times out, or changes status. It's a replacement for `ping -a` with enhanced audio capabilities and statistics.

**Key code lives in:** `src/ping_a/` — main package with CLI, prober, events, stats, and audio modules.

## Commands

| Command | Description |
|---|---|
| `make test` | Runs `unittest` tests discovered from `tests/` |
| `make standalone` | Builds a standalone script via `scripts/build_standalone.py` |
| `pip install -e .` | Installs the package (uses stdlib + ffplay backend) |
| `pip install -e '.[audio]'` | Installs with optional `pygame` dependency for lower latency |
| `python3 -m unittest discover -s tests -v` | Run tests directly (sets `PYTHONPATH=src`) |
| `python3 -m ping_a <host>` | Run the CLI directly |

## Architecture

- **Prober** (`prober.py`): Calls the system `ping` command via subprocess, parses stdout for RTT/TTL/size. Resolves host IPs via `socket.getaddrinfo`. Linux-only; uses `cap_net_raw` when ICMP sockets are unavailable.
- **Events** (`events.py`): `EventDecider` decides when to trigger sounds based on mode (`reply`/`timeout`/`change`/`failure`) and optional latency threshold.
- **Stats** (`stats.py`): Accumulates transmitted/received counts, loss percentage, RTT min/avg/max/mdev.
- **Audio** (`audio.py`: Generates synthesized beeps (`generate_beep_wav`), loads WAV/MP3/OGG via `ffmpeg`, caches decoded WAVs. Backends: `pygame` (low latency) → `ffplay` → `bell` (terminal beep) → `null` (silent).
- **CLI** (`cli.py`): Argparse-based, wires everything together. Supports `--sound`, `--sound-down`, `--sound-up`, `--on reply/timeout/change/failure`, `--latency-threshold`, `--backend auto/pygame/ffplay/bell/null`, `--volume`, `--repeat`, `--tone`, `--device`, `--json`, `--no-audio`.

## Data flow

1. CLI parses args → creates `Prober`, resolves sounds via `audio`, creates `EventDecider`, creates `Stats`/`AudioPlayer`.
2. Loop: `prober.probe(seq)` → system `ping` → parse reply → `Stats.record()` → `EventDecider.on_result()` → if event, `AudioPlayer.play(sound)`.
3. Output: human-readable per-line ping stats, or JSON lines if `--json`.
4. Summary printed on exit (loss%, RTT stats, elapsed time).

## Commands cheat sheet

```bash
# Install
pip install -e .                    # stdlib backends
pip install -e '.[audio]'           # + pygame

# Basic usage
ping-a 1.1.1.1                      # beep on each reply
ping-a example.com -i 0.5 -a       # alias for --on reply

# Custom sounds
ping-a 1.1.1.1 --sound alarm.mp3   # custom alarm
ping-a 10.0.0.5 --on change --sound-down caida.wav --sound-up vuelta.wav

# Modes
ping-a 8.8.8.8 --on timeout        # beep on timeout only
ping-a 1.1.1.1 --on change         # beep only when up/down changes

# Audio backends
ping-a 1.1.1.1 --backend pygame     # low latency (needs pygame)
ping-a 1.1.1.1 --backend ffplay     # uses ffplay
ping-a 1.1.1.1 --backend null       # no sound

# JSON output
ping-a 1.1.1.1 -c 5 --json --backend null

# Latency threshold
ping-a 8.8.8.8 --latency-threshold 100

# Options
ping-a host -c 5 -W 2 -s 56        # count, timeout, payload size
```

## Notable conventions & gotchas

- **OS**: Linux only. Uses system `ping` (iputils); requires `cap_net_raw` capability when ICMP sockets are unprivileged.
- **Audio dependencies**:
  - `pygame` → lowest latency, hardware-mixed playback.
  - `ffplay` → decodes MP3/WAV via ffmpeg; ~100–200 ms startup latency.
  - `bell` → terminal `\a` bell (last resort).
  - `null` → silent (used in tests/CI).
- **ffmpeg** is required for MP3/OGG support. Install: `sudo apt install ffmpeg` (Ubuntu).
- **pygame** is optional; if not installed, the tool falls back to `ffplay` then `bell`.
- **`--device`** only applies to the `pygame` backend (selects output audio device).
- **`--no-audio`** disables sound entirely (intended for tests/CI).
- **MP3 files** are decoded by ffmpeg to WAV PCM 16-bit mono 44.1 kHz. WAV files are loaded directly.
- **Sound caching**: decoded WAVs are cached under `~/.cache/ping-a/` keyed by SHA1 hash to avoid re-decoding.
- **Return codes**: 0 = all replies received, 1 = packet loss, 2 = usage/DNS/network error.
- **JSON output**: one JSON line per event, plus a summary on stderr.
- **Tests**: use `unittest`, no external dependencies needed (mocked prober/audio). Tests set `sys.path` to `src/` and use `PYTHONPATH=src`.