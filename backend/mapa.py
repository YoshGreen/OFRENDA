"""
mapa.py — Mapa del socavón: validación, BFS, generador por semilla.

API pública:
    cargar_mapa(seed=None)   -> MapaInfo
    bfs_distancia(mapa, origen) -> np.ndarray[FILAS, COLS]  (-1 = inacc.)
    ruta_bfs(mapa, origen, destino) -> list[tuple[int,int]] | None

MapaInfo agrupa la matriz, posiciones especiales y matrices de distancia
precalculadas desde la Bocamina y entre celdas arbitrarias.
"""
from __future__ import annotations

import copy
import random
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from backend.config import (
    BOCAMINA,
    ALTARES,
    CARBURO,
    Celda,
    COLS,
    FILAS,
    MAPA_BASE,
)

# Alias
_TRANSITABLE = {Celda.PASILLO, Celda.BOCAMINA, Celda.PLATA, Celda.ORO, Celda.ALTAR, Celda.CARBURO}


# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------
@dataclass
class MapaInfo:
    """Contiene el mapa y todas sus estructuras derivadas."""
    grid: np.ndarray            # shape (24,24) dtype int8
    bocamina: tuple[int, int]
    altares: list[tuple[int, int]]
    carburo: list[tuple[int, int]]
    plata: list[tuple[int, int]]
    oro: list[tuple[int, int]]
    # Distancias BFS desde la Bocamina a cada celda; -1 = inaccesible
    dist_bocamina: np.ndarray   # shape (24,24) dtype int16

    def transitable(self, fila: int, col: int) -> bool:
        return int(self.grid[fila, col]) in _TRANSITABLE

    def celdas_transitables(self) -> list[tuple[int, int]]:
        """Lista de todas las coordenadas transitables."""
        result: list[tuple[int, int]] = []
        for r in range(FILAS):
            for c in range(COLS):
                if self.transitable(r, c):
                    result.append((r, c))
        return result


# ---------------------------------------------------------------------------
# BFS helpers
# ---------------------------------------------------------------------------
_DIRS4 = ((-1, 0), (1, 0), (0, -1), (0, 1))


def bfs_distancia(grid: np.ndarray, origen: tuple[int, int]) -> np.ndarray:
    """
    Distancia BFS desde `origen` a todas las celdas transitables.
    Devuelve array int16 (FILAS×COLS); -1 = inaccesible o pared.
    """
    dist = np.full((FILAS, COLS), -1, dtype=np.int16)
    fr, fc = origen
    if int(grid[fr, fc]) not in _TRANSITABLE:
        return dist
    dist[fr, fc] = 0
    cola: deque[tuple[int, int]] = deque()
    cola.append((fr, fc))
    while cola:
        r, c = cola.popleft()
        d = dist[r, c]
        for dr, dc in _DIRS4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < FILAS and 0 <= nc < COLS and dist[nr, nc] == -1:
                if int(grid[nr, nc]) in _TRANSITABLE:
                    dist[nr, nc] = d + 1
                    cola.append((nr, nc))
    return dist


def ruta_bfs(
    grid: np.ndarray,
    origen: tuple[int, int],
    destino: tuple[int, int],
) -> list[tuple[int, int]] | None:
    """
    Camino más corto de `origen` a `destino` (BFS).
    Devuelve lista de celdas (incluye origen y destino) o None si no hay ruta.
    """
    if origen == destino:
        return [origen]
    padre: dict[tuple[int, int], tuple[int, int] | None] = {origen: None}
    cola: deque[tuple[int, int]] = deque([origen])
    fr, fc = origen
    if int(grid[fr, fc]) not in _TRANSITABLE:
        return None
    while cola:
        r, c = cola.popleft()
        for dr, dc in _DIRS4:
            nr, nc = r + dr, c + dc
            if 0 <= nr < FILAS and 0 <= nc < COLS and (nr, nc) not in padre:
                if int(grid[nr, nc]) in _TRANSITABLE:
                    padre[(nr, nc)] = (r, c)
                    if (nr, nc) == destino:
                        # reconstruir ruta
                        ruta: list[tuple[int, int]] = []
                        cur: tuple[int, int] | None = destino
                        while cur is not None:
                            ruta.append(cur)
                            cur = padre[cur]
                        ruta.reverse()
                        return ruta
                    cola.append((nr, nc))
    return None


def paso_siguiente(
    grid: np.ndarray,
    origen: tuple[int, int],
    destino: tuple[int, int],
) -> tuple[int, int] | None:
    """
    Primer paso del camino BFS de `origen` a `destino` (excluyendo el origen).
    Útil para resolver macro-acciones: saber en qué dirección moverse.
    Devuelve None si no hay ruta o ya está en el destino.
    """
    ruta = ruta_bfs(grid, origen, destino)
    if ruta is None or len(ruta) < 2:
        return None
    return ruta[1]


# ---------------------------------------------------------------------------
# Validación del mapa base
# ---------------------------------------------------------------------------
class ErrorMapa(ValueError):
    """Error de restricción del mapa."""


def validar_mapa(grid: np.ndarray) -> None:
    """
    Lanza ErrorMapa si alguna restricción de docs/01 §2 no se cumple.
    Llamado por cargar_mapa y por los tests.
    """
    # 1. Bocamina existe
    boc_r, boc_c = BOCAMINA
    if int(grid[boc_r, boc_c]) != Celda.BOCAMINA:
        raise ErrorMapa(f"Bocamina no encontrada en {BOCAMINA}")

    # 2. Conteos mínimos
    flat = grid.flatten()
    n_plata  = int(np.sum(flat == Celda.PLATA))
    n_oro    = int(np.sum(flat == Celda.ORO))
    n_altar  = int(np.sum(flat == Celda.ALTAR))
    n_carburo = int(np.sum(flat == Celda.CARBURO))

    if n_plata < 6:
        raise ErrorMapa(f"Se requieren ≥6 vetas de plata, hay {n_plata}")
    if n_oro < 4:
        raise ErrorMapa(f"Se requieren ≥4 vetas de oro, hay {n_oro}")
    if n_altar < 3:
        raise ErrorMapa(f"Se requieren ≥3 altares, hay {n_altar}")
    if n_carburo < 2:
        raise ErrorMapa(f"Se requieren ≥2 estaciones de carburo, hay {n_carburo}")

    # 3. Conectividad total por BFS desde la Bocamina
    dist = bfs_distancia(grid, BOCAMINA)
    for r in range(FILAS):
        for c in range(COLS):
            if int(grid[r, c]) in _TRANSITABLE and dist[r, c] == -1:
                raise ErrorMapa(
                    f"Celda ({r},{c}) transitable pero no conectada a la Bocamina"
                )

    # 4. Altares y estaciones declarados en config deben estar en el grid
    for pos in ALTARES:
        r, c = pos
        if int(grid[r, c]) != Celda.ALTAR:
            raise ErrorMapa(f"Altar declarado en config no encontrado en {pos}")
    for pos in CARBURO:
        r, c = pos
        if int(grid[r, c]) != Celda.CARBURO:
            raise ErrorMapa(f"Carburo declarado en config no encontrado en {pos}")

    # 5. Al menos 2 rutas distintas hacia zona profunda (filas 16+)
    # Estrategia: buscar 2 celdas transitables de acceso a zona profunda
    # (fila 16) y verificar que sean alcanzables por BFS independiente
    accesos_profunda = [
        (r, c) for r in range(16, FILAS) for c in range(COLS)
        if int(grid[r, c]) in _TRANSITABLE
    ]
    if len(accesos_profunda) < 2:
        raise ErrorMapa("Zona profunda tiene menos de 2 celdas transitables")

    # Verificar al menos 2 caminos distintos: BFS desde 2 celdas distintas
    # de zona profunda llegan a la bocamina (ya garantizado por conectividad)
    # Verificación más precisa: hay 2 "entradas" a zona profunda desde zona media
    entradas_profunda: list[tuple[int, int]] = []
    for r in range(16, FILAS):
        for c in range(COLS):
            if int(grid[r, c]) not in _TRANSITABLE:
                continue
            # tiene vecino en zona media
            for dr, dc in _DIRS4:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 16 and 0 <= nc < COLS and int(grid[nr, nc]) in _TRANSITABLE:
                    entradas_profunda.append((r, c))
                    break
    if len(entradas_profunda) < 2:
        raise ErrorMapa(
            f"Se requieren ≥2 rutas hacia zona profunda; solo hay {len(entradas_profunda)}"
        )


# ---------------------------------------------------------------------------
# Generador de mapas por semilla
# ---------------------------------------------------------------------------
def _coordenadas_tipo(grid: np.ndarray, tipo: int) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for r in range(FILAS):
        for c in range(COLS):
            if int(grid[r, c]) == tipo:
                result.append((r, c))
    return result


def generar(seed: int) -> MapaInfo:
    """
    Genera un mapa por semilla que cumple las restricciones de docs/01 §2.
    Estrategia: parte del MAPA_BASE y hace permutaciones de vetas
    (plata y oro intercambian posiciones en sus zonas), conservando
    la estructura de paredes, bocamina, altares y estaciones.
    Así el mapa generado siempre es válido y la variedad es suficiente
    para los experimentos de generalización.
    """
    rng = random.Random(seed)
    grid = np.array(MAPA_BASE, dtype=np.int8)

    # Recolectar posiciones de vetas en sus zonas
    plata_pos = _coordenadas_tipo(grid, Celda.PLATA)   # zona media (fila 8-15)
    oro_pos   = _coordenadas_tipo(grid, Celda.ORO)     # zona profunda (fila 16+)

    # Limpiar vetas (convertir a pasillo)
    for r, c in plata_pos:
        grid[r, c] = Celda.PASILLO
    for r, c in oro_pos:
        grid[r, c] = Celda.PASILLO

    # Volvemos a colocar vetas en posiciones aleatorias dentro de las zonas
    # pero usando solo celdas de pasillo que existen en la zona correcta
    def _pasillos_zona(fila_ini: int, fila_fin: int) -> list[tuple[int, int]]:
        return [
            (r, c) for r in range(fila_ini, fila_fin) for c in range(COLS)
            if int(grid[r, c]) == Celda.PASILLO
        ]

    candidatos_media   = _pasillos_zona(8, 16)
    candidatos_profunda = _pasillos_zona(16, FILAS)

    # Elegir posiciones aleatorias para las vetas (manteniendo al menos los mínimos)
    n_plata = max(len(plata_pos), 6)
    n_oro   = max(len(oro_pos), 4)

    rng.shuffle(candidatos_media)
    rng.shuffle(candidatos_profunda)

    nuevas_plata = candidatos_media[:n_plata]
    nuevas_oro   = candidatos_profunda[:n_oro]

    for r, c in nuevas_plata:
        grid[r, c] = Celda.PLATA
    for r, c in nuevas_oro:
        grid[r, c] = Celda.ORO

    return _construir_mapa_info(grid)


# ---------------------------------------------------------------------------
# Constructor de MapaInfo
# ---------------------------------------------------------------------------
def _construir_mapa_info(grid: np.ndarray) -> MapaInfo:
    """Construye MapaInfo a partir de un grid validado."""
    plata = _coordenadas_tipo(grid, Celda.PLATA)
    oro   = _coordenadas_tipo(grid, Celda.ORO)
    dist_boc = bfs_distancia(grid, BOCAMINA)
    return MapaInfo(
        grid=grid.copy(),
        bocamina=BOCAMINA,
        altares=list(ALTARES),
        carburo=list(CARBURO),
        plata=plata,
        oro=oro,
        dist_bocamina=dist_boc,
    )


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------
def cargar_mapa(seed: int | None = None) -> MapaInfo:
    """
    Carga y valida el mapa.
    - seed=None → MAPA_BASE fijo.
    - seed=int  → mapa generado por semilla.
    Lanza ErrorMapa si las restricciones no se cumplen.
    """
    if seed is None:
        grid = np.array(MAPA_BASE, dtype=np.int8)
    else:
        return generar(seed)   # generar ya llama a _construir_mapa_info

    validar_mapa(grid)
    return _construir_mapa_info(grid)
