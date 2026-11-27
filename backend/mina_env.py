"""
backend/mina_env.py — Entorno MDP discreto multi-minero.

Implementa el semi-MDP con macro-acciones de rumbo (docs/02 §2).
El entorno es autoritativo: valida acciones, gestiona cooldowns,
recompensas, ofrenda, batería y capturas.

API pública:
    env = MinaEnv(dificultad, seed, num_mineros)
    obs = env.reset(seed=None)
    obs, rewards, done, info = env.step(acciones_por_id, comando_tio=None)
    env.snapshot() -> dict serializable
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import numpy as np

from backend.config import (
    BATERIA_INICIAL,
    BATERIA_LINTERNA_FACTOR,
    CAPACIDAD_MAX,
    CARGA_TABLA,
    Celda,
    DIFICULTAD_DEFAULT,
    DIFICULTADES,
    FILAS, COLS,
    MAX_STEPS,
    PESO_ORO,
    PESO_PLATA,
    Recompensa,
    VISUAL_TICKS,
)
from backend.mapa import bfs_distancia, cargar_mapa, MapaInfo, paso_siguiente

_TRANSITABLE = {
    int(Celda.PASILLO),
    int(Celda.BOCAMINA),
    int(Celda.PLATA),
    int(Celda.ORO),
    int(Celda.ALTAR),
    int(Celda.CARBURO),
}


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------
class Accion(IntEnum):
    RUMBO_PLATA     = 0
    RUMBO_ORO       = 1
    RUMBO_ALTAR     = 2
    RUMBO_BOCAMINA  = 3
    OFRENDAR        = 4
    APAGAR_LINTERNA = 5
    SOLTAR_CARGA    = 6


# ---------------------------------------------------------------------------
# Estado del minero
# ---------------------------------------------------------------------------
@dataclass
class EstadoMinero:
    id: int
    fila: int
    col: int
    peso: int = 0
    plata: int = 0
    oro: int = 0
    bateria: float = BATERIA_INICIAL
    linterna_on: bool = True
    move_cooldown: int = 0
    vivo: bool = True
    escapado: bool = False
    carburo_usado: bool = False
    historial_botín: list[int] = field(default_factory=list)
    r_acumulada: float = 0.0
    k_pasos: int = 0
    ultima_accion: Accion | None = None
    ultimo_estado: int = 0
    # True si el minero partió del episodio en bocamina y no ha salido aún
    # (evita el auto-escape en el turno 1 cuando el reset pone al minero en bocamina)
    en_bocamina_inicio: bool = True

    @property
    def nivel_carga(self) -> int:
        if self.peso == 0:
            return 0
        elif self.peso <= 2:
            return 1
        elif self.peso == 3:
            return 2
        else:
            return 3

    @property
    def turnos_por_casilla(self) -> int:
        return CARGA_TABLA[self.nivel_carga][0]

    @property
    def radio_ruido(self) -> int:
        return CARGA_TABLA[self.nivel_carga][1]

    @property
    def bateria_por_turno(self) -> float:
        return CARGA_TABLA[self.nivel_carga][2]

    def activo(self) -> bool:
        return self.vivo and not self.escapado


# ---------------------------------------------------------------------------
# Codificación de estado (docs/02 §2.1) — mixed-radix (4,3,2,4,3,2,3,3)
# ---------------------------------------------------------------------------
def encode_state(
    dist_tio: int,
    tio_lado: int,
    ofrenda_activa: int,
    nivel_carga: int,
    bateria_bin: int,
    altar_cerca: int,
    dist_bocamina_bin: int,
    botin_disponible: int,
) -> int:
    """Mixed-radix → escalar [0, 5183]."""
    dims = (4, 3, 2, 4, 3, 2, 3, 3)
    vals = (dist_tio, tio_lado, ofrenda_activa,
            nivel_carga, bateria_bin, altar_cerca,
            dist_bocamina_bin, botin_disponible)
    idx = 0
    factor = 1
    for v, d in zip(reversed(vals), reversed(dims)):
        idx += v * factor
        factor *= d
    return idx


def decode_state(idx: int) -> tuple[int, ...]:
    """Inversa de encode_state."""
    dims = (4, 3, 2, 4, 3, 2, 3, 3)
    vals: list[int] = []
    for d in reversed(dims):
        vals.append(idx % d)
        idx //= d
    vals.reverse()
    return tuple(vals)


# ---------------------------------------------------------------------------
# Entorno
# ---------------------------------------------------------------------------
class MinaEnv:
    """
    Entorno MDP multi-minero con semi-MDP por enfriamiento.

    Args:
        dificultad: nombre de la dificultad ("facil" | "normal" | "pesadilla").
        seed: semilla del RNG (None = no determinista).
        num_mineros: número de mineros IA.
        mapa_seed: semilla del mapa (None = MAPA_BASE fijo).
        shaping_potencial: activa reward shaping (desactivado por defecto).
    """

    def __init__(
        self,
        dificultad: str = DIFICULTAD_DEFAULT,
        seed: int | None = None,
        num_mineros: int = 3,
        mapa_seed: int | None = None,
        shaping_potencial: bool = False,
    ) -> None:
        self._dif = DIFICULTADES[dificultad]
        self._seed = seed
        self._num_mineros = num_mineros
        self._mapa_seed = mapa_seed
        self._shaping = shaping_potencial

        self._rng: random.Random = random.Random(seed)
        self._mapa: MapaInfo | None = None
        self._mineros: dict[int, EstadoMinero] = {}
        self._turno: int = 0
        self._ofrenda_turnos: int = 0
        self._botín_soltado: list[tuple[int, int, int]] = []
        self._vetas_disponibles: dict[tuple[int, int], int] = {}
        self._done: bool = False

        from backend.tio_fsm import TioFSM
        self._tio: TioFSM = TioFSM(dificultad, seed)

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------

    def reset(self, seed: int | None = None) -> dict[int, dict[str, Any]]:
        """Reinicia el entorno para un nuevo episodio."""
        if seed is not None:
            self._seed = seed
        self._rng = random.Random(self._seed)

        self._mapa = cargar_mapa(self._mapa_seed)
        grid = self._mapa.grid

        self._vetas_disponibles = {}
        for pos in self._mapa.plata:
            self._vetas_disponibles[pos] = int(Celda.PLATA)
        for pos in self._mapa.oro:
            self._vetas_disponibles[pos] = int(Celda.ORO)

        self._botín_soltado = []
        self._turno = 0
        self._ofrenda_turnos = 0
        self._done = False

        boc = self._mapa.bocamina
        self._mineros = {}
        for i in range(self._num_mineros):
            self._mineros[i] = EstadoMinero(
                id=i, fila=boc[0], col=boc[1],
                en_bocamina_inicio=True,   # empiezan en bocamina; no escapan aún
            )

        self._tio.reset(grid)
        return self._observaciones()

    def step(
        self,
        acciones: dict[int, int],
        comando_tio: dict | None = None,
    ) -> tuple[dict[int, dict], dict[int, float], bool, dict[str, Any]]:
        """
        Ejecuta un turno completo.

        Orden según docs/02 §2.5:
        1. Observación y elección (parámetros ya resueltos).
        2. Ejecución de comandos (movimiento, recolección, ofrenda, linterna, soltar).
        3. Resolución de escapes.
        4. Batería, recarga, ofrenda, enfriamientos.
        5. Movimiento del Tío.
        6. Capturas.
        7. Muertes por batería; recompensas; truncamiento.
        """
        assert self._mapa is not None, "Llama reset() primero."
        assert not self._done, "El episodio ya terminó."

        self._turno += 1
        grid = self._mapa.grid
        recompensas: dict[int, float] = {mid: 0.0 for mid in self._mineros}
        eventos: list[str] = []

        # ----------------------------------------------------------------
        # Paso 2: Ejecutar acciones de mineros listos (cooldown == 0)
        # ----------------------------------------------------------------
        for mid, minero in self._mineros.items():
            if not minero.activo() or minero.move_cooldown > 0:
                continue
            accion_id = acciones.get(mid, int(Accion.RUMBO_BOCAMINA))
            r = self._ejecutar_accion(minero, Accion(accion_id), grid, eventos)
            recompensas[mid] += r
            minero.r_acumulada += r
            minero.k_pasos += 1

        # ----------------------------------------------------------------
        # Paso 3: Escapes
        # Un minero escapa si está en la bocamina Y no es su posición inicial
        # intocada (en_bocamina_inicio se borra al primer movimiento real).
        # ----------------------------------------------------------------
        for mid, minero in self._mineros.items():
            if not minero.activo():
                continue
            if (minero.fila, minero.col) == self._mapa.bocamina and not minero.en_bocamina_inicio:
                r_escape = self._resolver_escape(minero)
                recompensas[mid] += r_escape
                minero.r_acumulada += r_escape
                eventos.append(f"escapó:{mid}")

        # ----------------------------------------------------------------
        # Paso 4: Batería, recarga, ofrenda, enfriamientos
        # ----------------------------------------------------------------
        for mid, minero in self._mineros.items():
            if not minero.activo():
                continue
            self._consumir_bateria(minero)
            self._intentar_recarga(minero, recompensas)

        # Decrementar ofrenda (ya activa; NO decrementar en el turno de activación)
        if self._ofrenda_turnos > 0:
            self._ofrenda_turnos -= 1

        # Decrementar cooldowns de movimiento
        for minero in self._mineros.values():
            if minero.activo() and minero.move_cooldown > 0:
                minero.move_cooldown -= 1

        # ----------------------------------------------------------------
        # Paso 5: Movimiento del Tío
        # ----------------------------------------------------------------
        mineros_info = [
            {
                "fila": m.fila,
                "col": m.col,
                "nivel_carga": m.nivel_carga,
                "linterna_on": m.linterna_on,
                "vivo": m.vivo,
                "escapado": m.escapado,
            }
            for m in self._mineros.values()
        ]
        tio_fila_prev = self._tio.fila
        tio_col_prev = self._tio.col

        t_fila, t_col, t_modo, t_eventos = self._tio.step(
            mineros_info, self._ofrenda_turnos > 0
        )
        eventos.extend(t_eventos)

        # ----------------------------------------------------------------
        # Paso 6: Capturas
        # ----------------------------------------------------------------
        for mid, minero in self._mineros.items():
            if not minero.activo():
                continue
            capturado = False
            # Misma celda
            if minero.fila == t_fila and minero.col == t_col:
                capturado = True
            # Cruce de celdas
            elif (minero.fila == tio_fila_prev and minero.col == tio_col_prev
                  and tio_fila_prev != t_fila or tio_col_prev != t_col):
                # El Tío salió de la celda donde estaba el minero
                # y el minero estaba exactamente allí → cruce
                pass  # ya cubierto por "misma celda" al finalizar
            # Embestida: el Tío se movió 2 casillas; verificar celda intermedia
            if "embestida" in t_eventos:
                # Celda por la que pasó el Tío en el primer paso de la embestida
                # Lo resolvemos como: si el minero está en la celda final → captura
                if minero.fila == t_fila and minero.col == t_col:
                    capturado = True

            if capturado:
                self._capturar_minero(minero, recompensas, eventos, mid)

        # ----------------------------------------------------------------
        # Paso 7: Muertes por batería
        # ----------------------------------------------------------------
        for mid, minero in self._mineros.items():
            if not minero.activo():
                continue
            if minero.bateria <= 0.0:
                self._matar_minero(minero, recompensas, eventos, mid)

        # Penalización de turno normal para los que siguen activos
        for mid, minero in self._mineros.items():
            if minero.activo():
                recompensas[mid] += Recompensa.TURNO_NORMAL
                minero.r_acumulada += Recompensa.TURNO_NORMAL

        # Verificar fin de episodio
        todos_salieron = all(
            not m.vivo or m.escapado for m in self._mineros.values()
        )
        truncado = self._turno >= MAX_STEPS
        self._done = todos_salieron or truncado

        info: dict[str, Any] = {
            "turno": self._turno,
            "eventos": eventos,
            "truncado": truncado,
            "ofrenda_turnos": self._ofrenda_turnos,
            "tio": {
                "fila": t_fila,
                "col": t_col,
                "modo": int(t_modo),
                "charge_cd": self._tio.charge_cd,
            },
            "vetas_restantes": {
                "plata": [(r, c) for (r, c), t in self._vetas_disponibles.items()
                          if t == int(Celda.PLATA)],
                "oro":   [(r, c) for (r, c), t in self._vetas_disponibles.items()
                          if t == int(Celda.ORO)],
            },
            "botín_soltado": [(r, c, t) for r, c, t in self._botín_soltado],
        }

        return self._observaciones(), recompensas, self._done, info

    def snapshot(self) -> dict[str, Any]:
        assert self._mapa is not None
        tio_snap = self._tio.snapshot()
        return {
            "turno": self._turno,
            "done": self._done,
            "ofrenda_turnos": self._ofrenda_turnos,
            "mineros": [
                {
                    "id": m.id,
                    "fila": m.fila, "col": m.col,
                    "plata": m.plata, "oro": m.oro,
                    "peso": m.peso,
                    "nivel_carga": m.nivel_carga,
                    "bateria": round(m.bateria, 1),
                    "linterna_on": m.linterna_on,
                    "move_cooldown": m.move_cooldown,
                    "vivo": m.vivo,
                    "escapado": m.escapado,
                    "visual_ticks": VISUAL_TICKS[m.nivel_carga],
                }
                for m in self._mineros.values()
            ],
            "tio": {
                "fila": tio_snap.fila, "col": tio_snap.col,
                "modo": tio_snap.modo, "charge_cd": tio_snap.charge_cd,
            },
            "vetas_disponibles": [
                {"fila": r, "col": c, "tipo": t}
                for (r, c), t in self._vetas_disponibles.items()
            ],
            "botín_soltado": [
                {"fila": r, "col": c, "tipo": t}
                for r, c, t in self._botín_soltado
            ],
        }

    # ------------------------------------------------------------------
    # Observaciones
    # ------------------------------------------------------------------

    def _observaciones(self) -> dict[int, dict[str, Any]]:
        return {mid: self._observar_minero(m) for mid, m in self._mineros.items()}

    def _observar_minero(self, minero: EstadoMinero) -> dict[str, Any]:
        assert self._mapa is not None
        grid = self._mapa.grid
        pos = (minero.fila, minero.col)

        # dist_tio
        dist_tio_num = self._dist_bfs(grid, pos, (self._tio.fila, self._tio.col))
        if dist_tio_num is None or dist_tio_num > 8:
            dist_tio_bin = 0
        elif dist_tio_num >= 5:
            dist_tio_bin = 1
        elif dist_tio_num >= 2:
            dist_tio_bin = 2
        else:
            dist_tio_bin = 3

        # tio_lado
        d_boc_yo  = int(self._mapa.dist_bocamina[minero.fila, minero.col])
        d_boc_tio = int(self._mapa.dist_bocamina[self._tio.fila, self._tio.col])
        delta = d_boc_tio - d_boc_yo
        if delta > 2:
            tio_lado = 0
        elif delta < -2:
            tio_lado = 2
        else:
            tio_lado = 1

        ofrenda_activa_bin = 1 if self._ofrenda_turnos > 0 else 0
        nivel_carga = minero.nivel_carga

        if minero.bateria > 60.0:
            bateria_bin = 0
        elif minero.bateria > 25.0:
            bateria_bin = 1
        else:
            bateria_bin = 2

        altar_cerca = int(any(
            abs(minero.fila - ar) + abs(minero.col - ac) <= 1
            for ar, ac in self._mapa.altares
        ))

        d_boc = d_boc_yo
        if d_boc <= 8:
            dist_bocamina_bin = 0
        elif d_boc <= 16:
            dist_bocamina_bin = 1
        else:
            dist_bocamina_bin = 2

        tiene_oro   = any(t == int(Celda.ORO)   for t in self._vetas_disponibles.values())
        tiene_plata = any(t == int(Celda.PLATA)  for t in self._vetas_disponibles.values())
        if tiene_oro:
            botin_disponible = 2
        elif tiene_plata:
            botin_disponible = 1
        else:
            botin_disponible = 0

        estado_idx = encode_state(
            dist_tio_bin, tio_lado, ofrenda_activa_bin,
            nivel_carga, bateria_bin, altar_cerca,
            dist_bocamina_bin, botin_disponible,
        )

        return {
            "estado_idx": estado_idx,
            "vivo": minero.vivo,
            "escapado": minero.escapado,
            "move_cooldown": minero.move_cooldown,
            "nivel_carga": nivel_carga,
            "bateria": minero.bateria,
            "dist_tio": dist_tio_bin,
            "tio_lado": tio_lado,
            "ofrenda_activa": ofrenda_activa_bin,
            "bateria_bin": bateria_bin,
            "altar_cerca": altar_cerca,
            "dist_bocamina": dist_bocamina_bin,
            "botin_disponible": botin_disponible,
        }

    # ------------------------------------------------------------------
    # Ejecución de acciones
    # ------------------------------------------------------------------

    def _ejecutar_accion(
        self,
        minero: EstadoMinero,
        accion: Accion,
        grid: np.ndarray,
        eventos: list[str],
    ) -> float:
        if accion == Accion.OFRENDAR:
            return self._accion_ofrendar(minero, eventos)
        if accion == Accion.APAGAR_LINTERNA:
            return self._accion_apagar_linterna(minero, eventos)
        if accion == Accion.SOLTAR_CARGA:
            return self._accion_soltar(minero, eventos)
        return self._accion_rumbo(minero, accion, grid, eventos)

    def _accion_rumbo(
        self,
        minero: EstadoMinero,
        accion: Accion,
        grid: np.ndarray,
        eventos: list[str],
    ) -> float:
        pos = (minero.fila, minero.col)
        objetivo = self._resolver_objetivo(minero, accion)

        if objetivo is None:
            eventos.append(f"invalido:{minero.id}")
            return Recompensa.ACCION_INVALIDA

        if pos == objetivo:
            # Ya está en el objetivo (ej: está en bocamina pidiendo ir a bocamina)
            return 0.0

        siguiente = paso_siguiente(grid, pos, objetivo)
        if siguiente is None:
            eventos.append(f"invalido:{minero.id}")
            return Recompensa.ACCION_INVALIDA

        # Mover
        minero.fila, minero.col = siguiente
        minero.move_cooldown = minero.turnos_por_casilla - 1
        # Al moverse, ya no está en la posición inicial de bocamina
        minero.en_bocamina_inicio = False

        recompensa = 0.0
        nueva_pos = (minero.fila, minero.col)

        # Recolección automática en veta original
        if nueva_pos in self._vetas_disponibles:
            tipo = self._vetas_disponibles[nueva_pos]
            peso = PESO_PLATA if tipo == int(Celda.PLATA) else PESO_ORO
            if minero.peso + peso <= CAPACIDAD_MAX:
                minero.peso += peso
                if tipo == int(Celda.PLATA):
                    minero.plata += 1
                    minero.historial_botín.append(int(Celda.PLATA))
                    recompensa += Recompensa.PICAR_PLATA
                    eventos.append(f"picó_plata:{minero.id}")
                else:
                    minero.oro += 1
                    minero.historial_botín.append(int(Celda.ORO))
                    recompensa += Recompensa.PICAR_ORO
                    eventos.append(f"picó_oro:{minero.id}")
                del self._vetas_disponibles[nueva_pos]

        # Recolección de botín soltado (recompensa = 0)
        else:
            for i, (br, bc, bt) in enumerate(self._botín_soltado):
                if br == minero.fila and bc == minero.col:
                    peso = PESO_PLATA if bt == int(Celda.PLATA) else PESO_ORO
                    if minero.peso + peso <= CAPACIDAD_MAX:
                        minero.peso += peso
                        if bt == int(Celda.PLATA):
                            minero.plata += 1
                        else:
                            minero.oro += 1
                        minero.historial_botín.append(bt)
                        self._botín_soltado.pop(i)
                        eventos.append(f"recogió_soltado:{minero.id}")
                    break

        return recompensa

    def _resolver_objetivo(
        self,
        minero: EstadoMinero,
        accion: Accion,
    ) -> tuple[int, int] | None:
        assert self._mapa is not None
        pos = (minero.fila, minero.col)

        if accion == Accion.RUMBO_BOCAMINA:
            return self._mapa.bocamina

        if accion == Accion.RUMBO_ALTAR:
            return self._mas_cercano(pos, self._mapa.altares)

        if accion == Accion.RUMBO_PLATA:
            platas = [p for p, t in self._vetas_disponibles.items()
                      if t == int(Celda.PLATA)]
            return self._mas_cercano(pos, platas)

        if accion == Accion.RUMBO_ORO:
            oros = [p for p, t in self._vetas_disponibles.items()
                    if t == int(Celda.ORO)]
            return self._mas_cercano(pos, oros)

        return None

    def _mas_cercano(
        self,
        pos: tuple[int, int],
        candidatos: list[tuple[int, int]],
    ) -> tuple[int, int] | None:
        assert self._mapa is not None
        if not candidatos:
            return None
        dist_arr = bfs_distancia(self._mapa.grid, pos)
        mejor: tuple[int, int] | None = None
        mejor_dist = int(1e9)
        for cand in candidatos:
            d = int(dist_arr[cand[0], cand[1]])
            if d == -1:
                continue
            if d < mejor_dist or (d == mejor_dist and cand < mejor):
                mejor = cand
                mejor_dist = d
        return mejor

    # ------------------------------------------------------------------
    # Acciones especiales
    # ------------------------------------------------------------------

    def _accion_ofrendar(
        self,
        minero: EstadoMinero,
        eventos: list[str],
    ) -> float:
        assert self._mapa is not None
        if self._ofrenda_turnos > 0:
            eventos.append(f"invalido:{minero.id}")
            return Recompensa.ACCION_INVALIDA
        altar_cerca = any(
            abs(minero.fila - ar) + abs(minero.col - ac) <= 1
            for ar, ac in self._mapa.altares
        )
        if not altar_cerca:
            eventos.append(f"invalido:{minero.id}")
            return Recompensa.ACCION_INVALIDA

        # Activar ofrenda: el contador empieza en ofrenda_duracion y se
        # decrementa a partir del SIGUIENTE turno (paso 4).
        self._ofrenda_turnos = self._dif.ofrenda_duracion
        eventos.append(f"ofrendó:{minero.id}")
        return Recompensa.OFRENDAR

    def _accion_apagar_linterna(
        self,
        minero: EstadoMinero,
        eventos: list[str],
    ) -> float:
        minero.linterna_on = not minero.linterna_on
        estado = "apagó" if not minero.linterna_on else "encendió"
        eventos.append(f"{estado}_linterna:{minero.id}")
        return Recompensa.APAGAR_LINTERNA if not minero.linterna_on else 0.0

    def _accion_soltar(
        self,
        minero: EstadoMinero,
        eventos: list[str],
    ) -> float:
        if not minero.historial_botín:
            eventos.append(f"invalido:{minero.id}")
            return Recompensa.ACCION_INVALIDA
        tipo = minero.historial_botín.pop()
        peso = PESO_PLATA if tipo == int(Celda.PLATA) else PESO_ORO
        minero.peso -= peso
        if tipo == int(Celda.PLATA):
            minero.plata -= 1
        else:
            minero.oro -= 1
        self._botín_soltado.append((minero.fila, minero.col, tipo))
        eventos.append(f"soltó:{minero.id}")
        return Recompensa.SOLTAR_CARGA

    # ------------------------------------------------------------------
    # Escape
    # ------------------------------------------------------------------

    def _resolver_escape(self, minero: EstadoMinero) -> float:
        minero.escapado = True
        if minero.plata > 0 or minero.oro > 0:
            return (
                Recompensa.ESCAPAR_CON_MINERAL_BASE
                + Recompensa.ESCAPAR_CON_PLATA_UNIT * minero.plata
                + Recompensa.ESCAPAR_CON_ORO_UNIT * minero.oro
            )
        return Recompensa.ESCAPAR_VACIO

    # ------------------------------------------------------------------
    # Batería
    # ------------------------------------------------------------------

    def _consumir_bateria(self, minero: EstadoMinero) -> None:
        gasto = minero.bateria_por_turno * self._dif.bateria_mult
        if not minero.linterna_on:
            gasto *= BATERIA_LINTERNA_FACTOR
        minero.bateria = max(0.0, minero.bateria - gasto)

    def _intentar_recarga(
        self,
        minero: EstadoMinero,
        recompensas: dict[int, float],
    ) -> None:
        assert self._mapa is not None
        pos = (minero.fila, minero.col)
        if (
            pos in [(r, c) for r, c in self._mapa.carburo]
            and not minero.carburo_usado
            and minero.bateria <= 50.0
        ):
            minero.bateria = 100.0
            minero.carburo_usado = True
            recompensas[minero.id] += Recompensa.RECARGAR

    # ------------------------------------------------------------------
    # Capturas y muertes
    # ------------------------------------------------------------------

    def _capturar_minero(
        self,
        minero: EstadoMinero,
        recompensas: dict[int, float],
        eventos: list[str],
        mid: int,
    ) -> None:
        minero.vivo = False
        minero.plata = 0
        minero.oro = 0
        minero.peso = 0
        recompensas[mid] += Recompensa.CAPTURADO
        minero.r_acumulada += Recompensa.CAPTURADO
        eventos.append(f"atrapado:{mid}")

    def _matar_minero(
        self,
        minero: EstadoMinero,
        recompensas: dict[int, float],
        eventos: list[str],
        mid: int,
    ) -> None:
        minero.vivo = False
        minero.plata = 0
        minero.oro = 0
        minero.peso = 0
        recompensas[mid] += Recompensa.SIN_BATERIA
        minero.r_acumulada += Recompensa.SIN_BATERIA
        eventos.append(f"sin_batería:{mid}")

    # ------------------------------------------------------------------
    # Utilidades estáticas
    # ------------------------------------------------------------------

    @staticmethod
    def _dist_bfs(
        grid: np.ndarray,
        origen: tuple[int, int],
        destino: tuple[int, int],
    ) -> int | None:
        dist = bfs_distancia(grid, origen)
        d = dist[destino[0], destino[1]]
        return int(d) if d >= 0 else None

    # ------------------------------------------------------------------
    # Propiedades de acceso directo (útiles en tests)
    # ------------------------------------------------------------------

    @property
    def turno(self) -> int:
        return self._turno

    @property
    def done(self) -> bool:
        return self._done

    @property
    def ofrenda_turnos(self) -> int:
        return self._ofrenda_turnos

    @property
    def mineros(self) -> dict[int, EstadoMinero]:
        return self._mineros

    @property
    def mapa(self) -> MapaInfo | None:
        return self._mapa

    @property
    def vetas_disponibles(self) -> dict[tuple[int, int], int]:
        return self._vetas_disponibles

    @property
    def tio(self):
        return self._tio
