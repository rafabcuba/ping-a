# ping-a

Ping con alarma sonora propia para Linux. Reproduce un pitido sintetizado o
un archivo **WAV/MP3** cada vez que el host responde, falla, o cambia de
estado. No usa los sonidos del sistema operativo.

## Características

- Sondeo con el `ping` del sistema (iputils), sin necesidad de root.
- Pitido por defecto **generado por código** (dos tonos, 880 Hz y 1175 Hz).
- Alarma personalizada con `--sound archivo.wav|mp3|ogg`.
- Reproducción en un hilo aparte: el sondeo nunca se bloquea.
- Backends: `pygame` (baja latencia) → `ffplay` → campana del terminal.
- Modos de disparo: `reply`, `timeout`, `change`, `failure`.
- Estadísticas tipo ping y salida JSON opcional.
- Paquete instalable y script standalone de un solo archivo.

## Requisitos

- Linux con `iputils-ping`.
- Python 3.9 o superior.
- `ffmpeg`/`ffplay` para decodificar MP3 y como backend de audio
  (normalmente ya vienen instalados en Ubuntu).
- Opcional: `pygame` para menor latencia.

En Ubuntu:

```bash
sudo apt install iputils-ping ffmpeg
```

## Instalación

### Como paquete (recomendado)

```bash
cd /home/rbg/proyectos/pina
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[audio]'
```

Si no quieres instalar `pygame`, usa `pip install -e .` y el comando
funcionará con `ffplay`.

También puedes instalarlo de forma aislada con `pipx` o `uv`:

```bash
pipx install '.[audio]'
# o
uv tool install '.[audio]'
```

### Script standalone

```bash
python3 scripts/build_standalone.py
./dist/ping-a 1.1.1.1
```

El standalone solo usa la biblioteca estándar y el backend `ffplay`.

## Uso

```bash
ping-a <host> [opciones]
```

### Ejemplos

Alarma en cada respuesta (equivalente a `ping -a`):

```bash
ping-a 1.1.1.1
ping-a example.com -i 0.5 -a
```

Usar un MP3 propio:

```bash
ping-a 1.1.1.1 --sound ~/alarmas/alarma.mp3 --volume 0.9
```

Avisar solo cuando el servidor se cae o se recupera:

```bash
ping-a 10.0.0.5 --on change --sound-down caida.wav --sound-up vuelta.wav
```

Sonar solo si la latencia supera 100 ms:

```bash
ping-a 8.8.8.8 --latency-threshold 100
```

Repetir la alarma tres veces y usar el pitido sintetizado:

```bash
ping-a 1.1.1.1 --repeat 3 --tone 1200
```

Salida JSON para integrar con otros sistemas:

```bash
ping-a 1.1.1.1 -c 5 --json --backend null
```

## Opciones

| Opción | Descripción |
|---|---|
| `-i, --interval SEG` | Intervalo entre pings (def. 1.0, mínimo 0.2) |
| `-c, --count N` | Número de pings (def. 0 = infinito) |
| `-W, --timeout SEG` | Espera por respuesta (def. 2) |
| `-s, --size BYTES` | Payload ICMP (def. 56) |
| `-a, --audible` | Alias de `--on reply` |
| `-f, --sound ARCHIVO` | Alarma WAV/MP3/OGG |
| `--sound-down ARCHIVO` | Sonido específico para caída |
| `--sound-up ARCHIVO` | Sonido específico para recuperación |
| `--volume 0..1` | Volumen (def. 0.8) |
| `--repeat N` | Repeticiones por evento (def. 1) |
| `--tone HZ` | Frecuencia del pitido sintetizado (def. 880) |
| `--on MODO` | `reply`, `timeout`, `change` o `failure` |
| `--latency-threshold MS` | Solo suena si el RTT supera ese valor |
| `--backend` | `auto`, `pygame`, `ffplay`, `bell` o `null` |
| `--device NOMBRE` | Dispositivo de salida (backend pygame) |
| `--no-audio` | No reproducir sonido |
| `--json` | Una línea JSON por evento |
| `--version` | Versión del programa |

### Modos de `--on`

| Modo | Comportamiento |
|---|---|
| `reply` | Suena en cada respuesta correcta (defecto) |
| `timeout` | Suena en cada intento sin respuesta |
| `change` | Suena solo al cambiar entre arriba/abajo |
| `failure` | Suena al iniciar una caída y al recuperarse |

## Cómo funciona el audio

1. El sonido se genera o se decodifica **una sola vez al arrancar**.
   - WAV/MP3/OGG → `ffmpeg` lo convierte a WAV PCM 16-bit mono 44.1 kHz.
   - Sin archivo → se sintetiza un doble pitido con envolvente para evitar
     clics.
2. El WAV resultante se precarga en memoria.
3. Cada evento se encola y un hilo dedicado lo reproduce. Si llega otro
   evento mientras suena, se descarta para no solapar.
4. El backend se elige automáticamente: `pygame` si está instalado, si no
   `ffplay`, y como último recurso la campana del terminal.

## Códigos de salida

| Código | Significado |
|---|---|
| `0` | Todas las respuestas recibidas |
| `1` | Al menos un paquete perdido (o ninguno recibido) |
| `2` | Error de uso, DNS o red |

## Desarrollo

```bash
make test
make standalone
```

Los tests usan `unittest` y no requieren dependencias externas:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Limitaciones

- Solo Linux: el parser y las opciones (`-W`, `-6`) son de iputils.
- En esta máquina los sockets ICMP sin privilegios están deshabilitados
  (`ping_group_range = 1 0`), por eso se usa el `ping` del sistema con
  `cap_net_raw` en lugar de ICMP nativo en Python.
- El backend `ffplay` tarda ~100–200 ms en arrancar cada reproducción; si
  necesitas la mínima latencia, instala el extra `[audio]` (pygame).
- `--device` solo aplica al backend `pygame`.
- El MP3 requiere `ffmpeg` para decodificarse.
