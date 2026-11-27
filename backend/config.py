"""
config.py — Constantes globales de El Tío de la Mina.

Todos los valores numéricos del juego viven aquí.
El frontend nunca los duplica; los recibe de /api/config.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import IntEnum


# ---------------------------------------------------------------------------
# Código de celda
# ---------------------------------------------------------------------------
class Celda(IntEnum):
    PASILLO   = 0
    PARED     = 1
    BOCAMINA  = 2
    PLATA     = 3
    ORO       = 4
    ALTAR     = 5
    CARBURO   = 6


# ---------------------------------------------------------------------------
# Mapa base 24×24
# 0=pasillo, 1=pared, 2=bocamina, 3=plata, 4=oro, 5=altar, 6=carburo
# ---------------------------------------------------------------------------
#  Zonas: filas 0-7 superior (bocamina+carburo), 8-15 media, 16-23 profunda
MAPA_BASE: list[list[int]] = [
    # fila 0
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    # fila 1 — bocamina en (1,1)
    [1,2,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,1],
    # fila 2
    [1,0,1,1,0,1,1,0,1,1,1,0,1,0,1,1,1,0,1,0,1,1,0,1],
    # fila 3 — estación de carburo zona superior (3,11)
    [1,0,1,0,0,0,0,0,0,0,0,6,0,0,0,0,0,0,0,0,0,1,0,1],
    # fila 4
    [1,0,0,0,1,1,1,0,1,1,1,0,1,0,1,1,1,0,1,0,0,0,0,1],
    # fila 5
    [1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,0,1],
    # fila 6
    [1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,0,0,0,0,1],
    # fila 7
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,0,0,1],
    # fila 8 — inicio zona media
    [1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,0,1],
    # fila 9 — altar (9,5), vetas de plata
    [1,0,0,0,0,5,0,0,0,0,0,3,0,0,0,0,0,3,0,0,0,0,0,1],
    # fila 10
    [1,0,1,1,0,1,0,1,1,0,1,0,1,1,0,1,0,1,1,0,1,0,1,1],
    # fila 11 — altar (11,11), vetas de plata
    [1,0,0,0,0,0,0,0,0,0,0,5,0,0,0,3,0,0,0,0,0,0,0,1],
    # fila 12 — segunda estación de carburo (12,18)
    [1,0,1,1,0,1,1,0,1,0,1,0,1,0,1,0,1,0,6,0,1,0,1,1],
    # fila 13 — altar (13,17), vetas de plata
    [1,0,0,0,0,0,0,3,0,0,0,0,0,0,0,0,0,5,0,0,0,0,0,1],
    # fila 14
    [1,0,1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1],
    # fila 15 — 2 vetas de plata adicionales para cumplir mínimo ≥6
    [1,0,0,3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,3,0,0,0,1],
    # fila 16 — inicio zona profunda
    [1,1,0,1,1,0,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1,1,0,1],
    # fila 17 — vetas de oro
    [1,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0,0,0,0,0,0,1],
    # fila 18
    [1,0,1,1,0,1,0,1,1,0,1,0,1,0,1,0,1,0,1,1,0,1,0,1],
    # fila 19 — vetas de oro
    [1,0,0,0,4,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0,0,0,1],
    # fila 20
    [1,0,1,0,1,1,1,0,1,1,1,0,1,1,1,0,1,0,1,1,1,0,1,1],
    # fila 21 — vetas de oro
    [1,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0,0,0,0,0,0,0,0,1],
    # fila 22
    [1,0,1,1,0,1,1,0,1,0,1,0,1,0,1,0,1,0,1,1,0,1,0,1],
    # fila 23 — fondo
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]

# Coordenadas notables del mapa base
BOCAMINA: tuple[int, int] = (1, 1)
ALTARES: list[tuple[int, int]] = [(9, 5), (11, 11), (13, 17)]
CARBURO: list[tuple[int, int]] = [(3, 11), (12, 18)]


# ---------------------------------------------------------------------------
# Mecánicas de carga
# ---------------------------------------------------------------------------
# nivel_carga → (turnos_por_casilla, radio_ruido, bateria_por_turno_pct)
CARGA_TABLA: dict[int, tuple[int, int, float]] = {
    0: (1, 3, 0.5),
    1: (1, 3, 0.5),
    2: (2, 5, 0.75),
    3: (3, 7, 1.0),
}

CAPACIDAD_MAX: int = 6       # unidades de peso máximas
PESO_PLATA: int = 1
PESO_ORO: int = 2

# Valor de los minerales (puntuación visible)
BS_PLATA: int = 500
BS_ORO: int = 1_200
BS_SUPERVIVENCIA: int = 500
BS_PENALIZACION_TURNO: int = 2    # −2 Bs por turno de salida


# ---------------------------------------------------------------------------
# Ofrenda
# ---------------------------------------------------------------------------
OFRENDA_DURACION_BASE: int = 15      # turnos de protección (Normal)
OFRENDA_RADIO_FACTOR: float = 0.5   # El Tío reduce radio a la mitad
OFRENDA_PERSECUCION_MAX: int = 2    # solo persigue a dist ≤ 2


# ---------------------------------------------------------------------------
# Batería
# ---------------------------------------------------------------------------
BATERIA_INICIAL: float = 100.0  # %
BATERIA_LINTERNA_FACTOR: float = 0.5  # apagada → gasta la mitad


# ---------------------------------------------------------------------------
# Recompensas RL (§2.6)
# ---------------------------------------------------------------------------
class Recompensa:
    ESCAPAR_CON_MINERAL_BASE: float = 50.0
    ESCAPAR_CON_PLATA_UNIT: float = 30.0
    ESCAPAR_CON_ORO_UNIT: float = 70.0
    ESCAPAR_VACIO: float = -10.0
    PICAR_PLATA: float = 4.0
    PICAR_ORO: float = 8.0
    RECOGER_SOLTADO: float = 0.0
    TURNO_NORMAL: float = -1.0
    ACCION_INVALIDA: float = -4.0
    OFRENDAR: float = -6.0
    APAGAR_LINTERNA: float = -2.0
    SOLTAR_CARGA: float = -3.0
    RECARGAR: float = 5.0
    CAPTURADO: float = -100.0
    SIN_BATERIA: float = -100.0
    TRUNCAMIENTO: float = 0.0   # se bootstrapea


# ---------------------------------------------------------------------------
# El Tío — FSM
# ---------------------------------------------------------------------------
class EstadoTio(IntEnum):
    PATRULLANDO  = 0
    ALERTADO     = 1
    PERSIGUIENDO = 2


TIO_VELOCIDAD: int = 1              # casillas/turno base
TIO_ALERTA_TURNOS: int = 6          # turnos máximos en celda de alerta
TIO_PERSECUCION_PERDIDA: int = 8    # turnos sin ver → vuelve a patrullar
TIO_VER_DISTANCIA: int = 4          # distancia visión con linterna
TIO_VER_DISTANCIA_OFRENDA: int = 2  # con ofrenda activa
TIO_QUIETO_PROB: float = 0.15       # prob de quedarse quieto en patrulla
TIO_LINTERNA_APAGADA_DETECCION: float = 0.2  # factor detección sin linterna
TIO_FILA_ZONA_MEDIA: int = 8        # empieza zona media en fila 8
TIO_POSICION_INICIAL: tuple[int, int] = (17, 10)   # zona profunda


# ---------------------------------------------------------------------------
# Dificultades
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Dificultad:
    nombre: str
    ofrenda_duracion: int
    embestida_cooldown: int
    bateria_mult: float
    radio_ruido_delta: int   # suma al radio de la tabla de carga


DIFICULTADES: dict[str, Dificultad] = {
    "facil":     Dificultad("facil",     20, 8, 0.80, -1),
    "normal":    Dificultad("normal",    15, 5, 1.00,  0),
    "pesadilla": Dificultad("pesadilla", 12, 3, 1.25, +1),
}
DIFICULTAD_DEFAULT: str = "normal"


# ---------------------------------------------------------------------------
# Hiper-parámetros RL por defecto
# ---------------------------------------------------------------------------
@dataclass
class HiperparametrosRL:
    alpha: float = 0.1
    gamma: float = 0.95
    epsilon_start: float = 1.0
    epsilon_min: float = 0.05
    epsilon_decay_fraction: float = 0.6   # llega a epsilon_min al 60 % del entrenamiento
    n_episodios: int = 5_000
    num_miners: int = 3
    seed: int = 42


# ---------------------------------------------------------------------------
# Espacio de estados
# ---------------------------------------------------------------------------
STATE_DIMS: tuple[int, ...] = (4, 3, 2, 4, 3, 2, 3, 3)
# dist_tio, tio_lado, ofrenda_activa, nivel_carga, bateria, altar_cerca, dist_bocamina, botin_disponible
N_ESTADOS: int = 1
for _d in STATE_DIMS:
    N_ESTADOS *= _d  # = 5184
N_ACCIONES: int = 7


# ---------------------------------------------------------------------------
# Juego / episodio
# ---------------------------------------------------------------------------
MAX_STEPS: int = 300
EVAL_EVERY: int = 250
EVAL_EPISODES: int = 100

# Checkpoints de experiencia (fracción del entrenamiento)
CHECKPOINT_FRACS: list[float] = [0.0, 0.02, 0.10, 0.30, 1.0]
CHECKPOINT_NOMBRES: list[str] = ["novato", "aprendiz", "veterano", "experto", "final"]

# Agresividad del Tío durante entrenamiento (aleatorización)
TIO_AGRESIVIDAD_MIN: float = 0.7
TIO_AGRESIVIDAD_MAX: float = 1.3

# Visual ticks por nivel de carga (para el frontend)
VISUAL_TICKS: dict[int, int] = {0: 1, 1: 1, 2: 2, 3: 3}

# Dimensiones del mapa
FILAS: int = 24
COLS: int = 24

# Tick de red (ms) por defecto
TICK_MS_DEFAULT: int = 450


# ---------------------------------------------------------------------------
# Hash de configuración (detecta cambio entre cerebro y dificultad)
# ---------------------------------------------------------------------------
def config_hash(dificultad: str = DIFICULTAD_DEFAULT) -> str:
    """Hash SHA-256 de los valores que afectan al entrenamiento."""
    d = DIFICULTADES[dificultad]
    datos = {
        "mapa_shape": [FILAS, COLS],
        "bocamina": list(BOCAMINA),
        "altares": [list(a) for a in ALTARES],
        "carburo": [list(c) for c in CARBURO],
        "capacidad_max": CAPACIDAD_MAX,
        "ofrenda_duracion": d.ofrenda_duracion,
        "embestida_cooldown": d.embestida_cooldown,
        "bateria_mult": d.bateria_mult,
        "radio_ruido_delta": d.radio_ruido_delta,
        "recompensas": {
            "escapar_base": Recompensa.ESCAPAR_CON_MINERAL_BASE,
            "capturado": Recompensa.CAPTURADO,
            "sin_bateria": Recompensa.SIN_BATERIA,
        },
        "max_steps": MAX_STEPS,
        "state_dims": list(STATE_DIMS),
        "n_acciones": N_ACCIONES,
    }
    raw = json.dumps(datos, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
