#!/usr/bin/env python3
"""Copia data/ y knowledge/data/ a un destino externo (pensado para cron).

Uso:
    python scripts/backup_data.py --dest /ruta/a/almacenamiento/externo

También acepta la variable de entorno BACKUP_DEST_DIR en lugar de --dest.
Cada ejecución crea un subdirectorio con timestamp para no pisar backups
anteriores.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent / "extranjeria_bot"
SOURCES = [
    PACKAGE_DIR / "data",
    PACKAGE_DIR / "knowledge" / "data",
]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        default=os.getenv("BACKUP_DEST_DIR"),
        help="Directorio externo donde guardar el backup (o env BACKUP_DEST_DIR)",
    )
    return parser.parse_args(argv)


def run_backup(dest_root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = dest_root / f"backup_{timestamp}"

    for source in SOURCES:
        if not source.exists():
            continue
        target = backup_dir / source.relative_to(PACKAGE_DIR)
        shutil.copytree(source, target)

    return backup_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    if not args.dest:
        print(
            "Falta el destino del backup: usa --dest o define BACKUP_DEST_DIR.",
            file=sys.stderr,
        )
        return 1

    dest_root = Path(args.dest)
    dest_root.mkdir(parents=True, exist_ok=True)

    backup_dir = run_backup(dest_root)
    print(f"Backup completado en: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
