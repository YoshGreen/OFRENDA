"""
backend/tio_fsm.py — FSM probabilística de El Tío.

Estados: PATRULLANDO → ALERTADO → PERSIGUIENDO → PATRULLANDO
Determinista dada la semilla; agresividad escalable para entrenamiento.

API pública:
    TioFSM.reset(grid, pos_inicial)
    TioFSM.step(mineros_visibles, grid, ofrenda_activa) -> (nueva_pos, nuevo_modo, eventos)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from backend.config import (
    Celda,
    Dificultad,
    DIFICULTADES,
    DIFICULTAD_DEFAULT,
    EstadoTio,
    FILAS,
    COLS,
    TIO_AGRESIVIDAD_MAX,
    TIO_AGRESIVIDAD_MIN,
    TIO_ALERTA_TURNOS,
    TIO_FILA_ZONA_MEDIA,
    TIO_LINTERNA_APAGADA_DETECCION,
    TIO_PERSECUCION_PERDIDA,
    TIO_POSICION_INICIAL,
    TIO_QUIETO_PROB,
    TIO_VER_DISTANCIA,
    TIO_VER_DISTANCIA_OFRENDA,
    TIO_VELOCIDAD,
    CARGA_TABLA,
)
from backend.mapa import bfs_distancia, paso_siguiente, ruta_bfs

_TRANSITABLE = {
    int(Celda.PASILLO),
    int(Celda.BOCAMINA),
    int(Celda.PLATA),
    int(Celda.ORO),
    int(Celda.ALTAR),
    int(Celda.CARBURO),
}
_DIRS4 = ((-1, 0), (1, 0), (0, -1), (0, 1))


@dataclass
class InfoTio:
    """Snapshot serializable del estado del Tío."""
    fila: int
    col: int
    modo: int           # EstadoTio
    charge_cd: int      # cooldown de embestida
    is_human: bool = False


class TioFSM:
    """
    FSM probabilística de El Tío.

    Args:
        dificultad: nombre de la dificultad (clave de DIFICULTADES).
        seed: semilla de aleatoriedad (None = no determinista).
        agresividad: factor multiplicativo de radios/probs (0.7–1.3 en entrenamiento).
    """

    def __init__(
        self,
        dificultad: str = DIFICULTAD_DEFAULT,
        seed: int | None = None,
        agresividad: float = 1.0,
    ) -> None:
        self._dif: Dificultad = DIFICULTADES[dificultad]
        self._rng: random.Random = random.Random(seed)
        self._agresividad: float = max(TIO_AGRESIVIDAD_MIN, min(TIO_AGRESIVIDAD_MAX, agresividad))

        # Estado interno
        self.fila: int = TIO_POSICION_INICIAL[0]
        self.col: int = TIO_POSICION_INICIAL[1]
        self.modo: EstadoTio = EstadoTio.PATRULLANDO
        self.charge_cd: int = 0                     # cooldown de embestida
        self._alerta_pos: tuple[int, int] | None = None
        self._alerta_turnos: int = 0
        self._perdida_turnos: int = 0               # turnos sin ver al perseguido
        self._waypoint: tuple[int, int] | None = None
        self._grid: np.ndarray | None = None

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def reset(
        self,
        grid: np.ndarray,
        pos_inicial: tuple[int, int] | None = None,
    ) -> None:
        """Reinicia el Tío para un nuevo episodio."""
        self._grid = grid
        pos = pos_inicial if pos_inicial is not None else TIO_POSICION_INICIAL
        self.fila, self.col = pos
        self.modo = EstadoTio.PATRULLANDO
        self.charge_cd = 0
        self._alerta_pos = None
        self._alerta_turnos = 0
        self._perdida_turnos = 0
        self._waypoint = None

    def step(
        self,
        mineros: list[dict],      # lista de {fila, col, nivel_carga, linterna_on, vivo, escapado}
        ofrenda_activa: bool,
    ) -> tuple[int, int, EstadoTio, list[str]]:
        """
        Ejecuta un turno del Tío.

        Args:
            mineros: información de cada minero vivo y no escapado.
            ofrenda_activa: True si hay ofrenda vigente.

        Returns:
            (nueva_fila, nueva_col, nuevo_modo, eventos)
            eventos: lista de strings como ["embestida", "rugido"]
        """
        assert self._grid is not None, "Llama reset() antes de step()"
        grid = self._grid
        eventos: list[str] = []

        # Decrementar cooldown de embestida
        if self.charge_cd > 0:
            self.charge_cd -= 1

        # Filtrar mineros activos
        mineros_activos = [
            m for m in mineros
            if m.get("vivo", True) and not m.get("escapado", False)
        ]

        # --- Detección ---
        objetivo = self._detectar(mineros_activos, ofrenda_activa)

        # --- Transiciones de estado ---
        if self.modo == EstadoTio.PATRULLANDO:
            if objetivo is not None:
                self.modo = EstadoTio.ALERTADO
                self._alerta_pos = (objetivo["fila"], objetivo["col"])
                self._alerta_turnos = 0

        elif self.modo == EstadoTio.ALERTADO:
            if objetivo is not None:
                # Puede upgradear a persecución directa
                self.modo = EstadoTio.PERSIGUIENDO
                self._perdida_turnos = 0
            else:
                self._alerta_turnos += 1
                if self._alerta_turnos >= TIO_ALERTA_TURNOS:
                    self.modo = EstadoTio.PATRULLANDO
                    self._alerta_pos = None

        elif self.modo == EstadoTio.PERSIGUIENDO:
            if objetivo is not None:
                self._perdida_turnos = 0
            else:
                self._perdida_turnos += 1
                if self._perdida_turnos >= TIO_PERSECUCION_PERDIDA:
                    self.modo = EstadoTio.PATRULLANDO
                    self._perdida_turnos = 0

        # --- Movimiento según estado ---
        if self.modo == EstadoTio.PATRULLANDO:
            self._mover_patrulla(grid)

        elif self.modo == EstadoTio.ALERTADO:
            if self._alerta_pos:
                self._mover_hacia(grid, self._alerta_pos)

        elif self.modo == EstadoTio.PERSIGUIENDO:
            if objetivo is not None:
                destino = (objetivo["fila"], objetivo["col"])
                dist_a_obj = self._distancia_bfs(grid, (self.fila, self.col), destino)

                # Embestida: dist ≤ 3, cooldown = 0, sin ofrenda
                puede_embestir = (
                    dist_a_obj is not None
                    and dist_a_obj <= 3
                    and self.charge_cd == 0
                    and not ofrenda_activa
                )
                if puede_embestir:
                    self._embestir(grid, destino)
                    self.charge_cd = self._dif.embestida_cooldown
                    eventos.append("embestida")
                else:
                    self._mover_hacia(grid, destino)

                # Rugido ocasional al perseguir
                if self._rng.random() < 0.15:
                    eventos.append("rugido")

        return self.fila, self.col, self.modo, eventos

    # ------------------------------------------------------------------
    # Detección
    # ------------------------------------------------------------------

    def _detectar(
        self,
        mineros: list[dict],
        ofrenda_activa: bool,
    ) -> dict | None:
        """
        Devuelve el minero más cercano detectado (por ruido o visión),
        o None si no detecta a nadie.
        """
        if not mineros or self._grid is None:
            return None

        mejor: dict | None = None
        mejor_dist: float = float("inf")

        for m in mineros:
            dist = self._distancia_bfs(self._grid, (self.fila, self.col), (m["fila"], m["col"]))
            if dist is None:
                continue

            nivel = m.get("nivel_carga", 0)
            linterna = m.get("linterna_on", True)
            radio_ruido_base = CARGA_TABLA[min(nivel, 3)][1]
            radio_ruido = int(radio_ruido_base * self._agresividad)
            if ofrenda_activa:
                radio_ruido = max(1, radio_ruido // 2)

            # Detección por ruido
            detectado_ruido = dist <= radio_ruido

            # Detección por visión (linterna)
            radio_vision = TIO_VER_DISTANCIA_OFRENDA if ofrenda_activa else TIO_VER_DISTANCIA
            radio_vision = int(radio_vision * self._agresividad)
            prob_vision = 1.0 if linterna else TIO_LINTERNA_APAGADA_DETECCION
            detectado_vision = linterna and dist <= radio_vision
            if not linterna and dist <= radio_vision:
                detectado_vision = self._rng.random() < TIO_LINTERNA_APAGADA_DETECCION

            if detectado_ruido or detectado_vision:
                if dist < mejor_dist:
                    mejor = m
                    mejor_dist = dist

        return mejor

    # ------------------------------------------------------------------
    # Movimiento
    # ------------------------------------------------------------------

    def _mover_hacia(self, grid: np.ndarray, destino: tuple[int, int]) -> None:
        """Avanza un paso hacia el destino por BFS."""
        siguiente = paso_siguiente(grid, (self.fila, self.col), destino)
        if siguiente:
            self.fila, self.col = siguiente

    def _embestir(self, grid: np.ndarray, destino: tuple[int, int]) -> None:
        """Avanza hasta 2 casillas hacia el destino."""
        for _ in range(2):
            siguiente = paso_siguiente(grid, (self.fila, self.col), destino)
            if siguiente is None:
                break
            self.fila, self.col = siguiente

    def _mover_patrulla(self, grid: np.ndarray) -> None:
        """
        Patrulla sesgada hacia zona profunda y vetas de oro.
        15 % de prob de quedarse quieto.
        """
        if self._rng.random() < TIO_QUIETO_PROB:
            return

        # Si no hay waypoint o ya llegó, elegir nuevo
        if self._waypoint is None or (self.fila, self.col) == self._waypoint:
            self._waypoint = self._elegir_waypoint(grid)

        if self._waypoint:
            siguiente = paso_siguiente(grid, (self.fila, self.col), self._waypoint)
            if siguiente:
                self.fila, self.col = siguiente
            else:
                self._waypoint = None   # camino bloqueado; re-elegir en siguiente turno

    def _elegir_waypoint(self, grid: np.ndarray) -> tuple[int, int] | None:
        """
        Elige un waypoint de patrulla con sesgo hacia zona profunda y vetas de oro.
        70 % zona profunda (fila ≥ 16), 30 % zona media (fila 8-15).
        """
        # Recopilar candidatos
        candidatos_profunda: list[tuple[int, int]] = []
        candidatos_media: list[tuple[int, int]] = []
        for r in range(FILAS):
            for c in range(COLS):
                if int(grid[r, c]) in _TRANSITABLE and (r, c) != (self.fila, self.col):
                    if r >= 16:
                        candidatos_profunda.append((r, c))
                    elif r >= TIO_FILA_ZONA_MEDIA:
                        candidatos_media.append((r, c))

        zona = candidatos_profunda if (
            candidatos_profunda and self._rng.random() < 0.7
        ) else candidatos_media

        if not zona:
            zona = candidatos_profunda + candidatos_media
        if not zona:
            return None

        # Sesgo adicional a vetas de oro
        oro_waypoints = [(r, c) for r, c in zona if int(grid[r, c]) == int(Celda.ORO)]
        if oro_waypoints and self._rng.random() < 0.4:
            return self._rng.choice(oro_waypoints)
        return self._rng.choice(zona)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @staticmethod
    def _distancia_bfs(
        grid: np.ndarray,
        origen: tuple[int, int],
        destino: tuple[int, int],
    ) -> int | None:
        """Distancia BFS entre dos celdas; None si sin ruta."""
        dist = bfs_distancia(grid, origen)
        d = dist[destino[0], destino[1]]
        return int(d) if d >= 0 else None

    def snapshot(self) -> InfoTio:
        return InfoTio(
            fila=self.fila,
            col=self.col,
            modo=int(self.modo),
            charge_cd=self.charge_cd,
        )
