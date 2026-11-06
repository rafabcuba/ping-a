#!/usr/bin/env python3
"""Genera dist/ping-a como un único archivo ejecutable (solo stdlib).

El script standalone usa el backend ffplay, por lo que no necesita pygame.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "ping_a"
ORDER = ("stats.py", "prober.py", "events.py", "audio.py", "cli.py")
MAIN_GUARD = re.compile(
    r'^if __name__ == "__main__":.*\Z',
    re.MULTILINE | re.DOTALL,
)


def read_version() -> str:
    text = (SRC / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("no se pudo leer __version__")
    return match.group(1)


def strip_module(text: str) -> str:
    lines = []
    skipping_import = False
    for line in text.splitlines():
        stripped = line.strip()
        if skipping_import:
            if ")" in stripped:
                skipping_import = False
            continue
        if stripped.startswith("from __future__ import"):
            continue
        if stripped.startswith("from .") or stripped.startswith("import ."):
            if "(" in stripped and ")" not in stripped:
                skipping_import = True
            continue
        lines.append(line)
    cleaned = MAIN_GUARD.sub("", "\n".join(lines))
    return cleaned.strip() + "\n"


def main() -> int:
    version = read_version()
    parts = [
        "#!/usr/bin/env python3",
        '"""ping-a - ping con alarma sonora personalizada.',
        "",
        "Archivo generado automáticamente por scripts/build_standalone.py.",
        "No editar a mano: modifica src/ping_a/ y vuelve a generar.",
        '"""',
        "from __future__ import annotations",
        "",
        f'__version__ = "{version}"',
        "",
    ]
    for name in ORDER:
        parts.append("# " + "=" * 70)
        parts.append(f"# {name}")
        parts.append("# " + "=" * 70)
        parts.append(
            strip_module((SRC / name).read_text(encoding="utf-8"))
        )

    parts.append(
        'if __name__ == "__main__":\n'
        "    raise SystemExit(main())\n"
    )

    output = ROOT / "dist" / "ping-a"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    output.chmod(
        output.stat().st_mode
        | stat.S_IXUSR
        | stat.S_IXGRP
        | stat.S_IXOTH
    )
    print(f"generado: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
