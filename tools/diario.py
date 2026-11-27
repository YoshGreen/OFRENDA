"""
tools/diario.py — CLI para añadir entradas al diario de desarrollo.

Uso:
    python tools/diario.py add \\
        --fase 0 \\
        --titulo "Fundación del proyecto" \\
        --hecho "Creados config.py, mapa.py, diario.py, bitacora.py" \\
        --decisiones "Mapa base fijo en MAPA_BASE; generador aleatoria permuta vetas" \\
        --pendiente "Implementar mina_env.py y tio_fsm.py"
"""
from __future__ import annotations

import argparse
import textwrap
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIARIO = RAIZ / "bitacora" / "DIARIO_DESARROLLO.md"


def _timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def cmd_add(args: argparse.Namespace) -> None:
    """Añade una nueva entrada al diario."""
    DIARIO.parent.mkdir(parents=True, exist_ok=True)
    if not DIARIO.exists():
        DIARIO.write_text(
            "# Diario de Desarrollo — El Tío de la Mina\n\n---\n",
            encoding="utf-8",
        )

    hecho     = args.hecho or "(sin descripción)"
    decisiones = args.decisiones or "(ninguna)"
    pendiente  = args.pendiente or "(nada)"

    entrada = textwrap.dedent(f"""
        ## [{_timestamp()}] Fase {args.fase} — {args.titulo}

        **Hecho:**
        {hecho}

        **Decisiones registradas:**
        {decisiones}

        **Pendiente:**
        {pendiente}

        ---
    """)

    with DIARIO.open("a", encoding="utf-8") as f:
        f.write(entrada)

    print(f"✓ Entrada añadida al diario: Fase {args.fase} — {args.titulo}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gestiona el diario de desarrollo de El Tío de la Mina."
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_add = sub.add_parser("add", help="Añade una entrada al diario.")
    p_add.add_argument("--fase",       type=int,   required=True, help="Número de fase (0-9)")
    p_add.add_argument("--titulo",     type=str,   required=True, help="Título de la sesión")
    p_add.add_argument("--hecho",      type=str,   default="",    help="Qué se implementó")
    p_add.add_argument("--decisiones", type=str,   default="",    help="Decisiones de diseño")
    p_add.add_argument("--pendiente",  type=str,   default="",    help="Qué queda por hacer")
    p_add.set_defaults(func=cmd_add)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
