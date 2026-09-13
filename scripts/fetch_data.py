"""Descarga el open data de baloncesto de SkillCorner en data/raw.

Son unos 730 MB: el tracking viaja por Git LFS, asi que hace falta tener
git-lfs instalado (https://git-lfs.com). El dataset no se versiona en este
repositorio, se descarga.

Uso: python scripts/fetch_data.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/SkillCorner/opendata-basketball.git"
ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "raw" / "opendata-basketball"


def main() -> int:
    if shutil.which("git") is None:
        print("No encuentro git en el PATH.", file=sys.stderr)
        return 1

    if (TARGET / "data" / "matches.json").exists():
        print(f"El dataset ya esta en {TARGET}. Nada que hacer.")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    print(f"Clonando {REPO} en {TARGET} (unos 730 MB, tarda un rato)...")
    result = subprocess.run(["git", "clone", "--depth", "1", REPO, str(TARGET)], check=False)
    if result.returncode != 0:
        print("El clonado ha fallado.", file=sys.stderr)
        return result.returncode

    if not (TARGET / "data" / "matches.json").exists():
        print("El clonado termino pero no encuentro data/matches.json.", file=sys.stderr)
        return 1

    tracking = list(TARGET.glob("data/matches/*/*_tracking_data.jsonl.gz"))
    small = [p for p in tracking if p.stat().st_size < 1_000_000]
    if small:
        print(
            f"Aviso: {len(small)} ficheros de tracking pesan menos de 1 MB. "
            "Suele significar que git-lfs no estaba instalado y solo se han "
            "bajado los punteros. Instala git-lfs y ejecuta 'git lfs pull' "
            f"dentro de {TARGET}.",
            file=sys.stderr,
        )
        return 1

    print(f"Listo: {len(tracking)} partidos con tracking en {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
