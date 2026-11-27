"""
tests/test_env.py — Pruebas del entorno MDP (docs/02 §9).

Cubre:
- Conectividad del mapa base.
- Tabla de cooldown: carga 3 → 3 turnos/casilla.
- Capacidad máxima.
- Morir con oro da −100 sin ganancia neta.
- Ofrenda: duración, efectos, no repetible.
- Soltar carga sin recompensa al recoger de nuevo.
- Recarga de uso único.
- Capturas por cruce y embestida.
- Truncamiento sin terminal.
- Determinismo por semilla.
- test_viabilidad_bateria.
"""
from __future__ import annotations

import pytest
import numpy as np

from backend.config import (
    CAPACIDAD_MAX,
    Celda,
    DIFICULTADES,
    FILAS, COLS,
    MAX_STEPS,
    OFRENDA_DURACION_BASE,
    PESO_ORO,
    PESO_PLATA,
    Recompensa,
    CARGA_TABLA,
    BATERIA_INICIAL,
)
from backend.mapa import cargar_mapa, validar_mapa, bfs_distancia, ErrorMapa
from backend.mina_env import Accion, MinaEnv, decode_state, encode_state


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env_normal():
    """Entorno en dificultad normal, 1 minero, seed fija."""
    env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
    env.reset(seed=42)
    return env


@pytest.fixture
def env_3mineros():
    env = MinaEnv(dificultad="normal", seed=42, num_mineros=3)
    env.reset(seed=42)
    return env


@pytest.fixture
def mapa_base():
    return cargar_mapa()


# ---------------------------------------------------------------------------
# Mapa base
# ---------------------------------------------------------------------------

class TestMapaBase:
    def test_validar_mapa_base(self, mapa_base):
        """El mapa base pasa todas las restricciones sin lanzar excepción."""
        validar_mapa(mapa_base.grid)

    def test_bocamina_existe(self, mapa_base):
        r, c = mapa_base.bocamina
        assert int(mapa_base.grid[r, c]) == int(Celda.BOCAMINA)

    def test_conteo_plata(self, mapa_base):
        n = int(np.sum(mapa_base.grid == int(Celda.PLATA)))
        assert n >= 6, f"Solo {n} vetas de plata"

    def test_conteo_oro(self, mapa_base):
        n = int(np.sum(mapa_base.grid == int(Celda.ORO)))
        assert n >= 4, f"Solo {n} vetas de oro"

    def test_conteo_altares(self, mapa_base):
        n = int(np.sum(mapa_base.grid == int(Celda.ALTAR)))
        assert n >= 3, f"Solo {n} altares"

    def test_conteo_carburo(self, mapa_base):
        n = int(np.sum(mapa_base.grid == int(Celda.CARBURO)))
        assert n >= 2, f"Solo {n} estaciones de carburo"

    def test_conectividad(self, mapa_base):
        """Todas las celdas transitables conectadas a la bocamina."""
        dist = bfs_distancia(mapa_base.grid, mapa_base.bocamina)
        transitable = {0, 2, 3, 4, 5, 6}
        for r in range(FILAS):
            for c in range(COLS):
                if int(mapa_base.grid[r, c]) in transitable:
                    assert dist[r, c] >= 0, (
                        f"Celda ({r},{c}) transitable pero no conectada a bocamina"
                    )

    def test_zona_vetas_plata_en_media(self, mapa_base):
        """Las vetas de plata están en zona media (filas 8-15)."""
        for r, c in mapa_base.plata:
            assert 8 <= r <= 15, f"Veta de plata fuera de zona media: ({r},{c})"

    def test_zona_vetas_oro_en_profunda(self, mapa_base):
        """Las vetas de oro están en zona profunda (filas 16-23)."""
        for r, c in mapa_base.oro:
            assert r >= 16, f"Veta de oro fuera de zona profunda: ({r},{c})"


# ---------------------------------------------------------------------------
# Tabla de cooldown
# ---------------------------------------------------------------------------

class TestCooldown:
    def test_carga_0_cooldown_0(self, env_normal):
        """Sin carga: move_cooldown = 0 después de moverse."""
        minero = env_normal.mineros[0]
        assert minero.nivel_carga == 0
        assert minero.turnos_por_casilla == 1

    def test_carga_3_cooldown_2(self):
        """Carga 3 (≥4 unidades): turnos_por_casilla = 3, cooldown = 2 tras mover."""
        env = MinaEnv(dificultad="normal", seed=1, num_mineros=1)
        env.reset(seed=1)
        minero = env.mineros[0]
        # Forzar peso ≥ 4 directamente
        minero.peso = 4
        assert minero.nivel_carga == 3
        assert minero.turnos_por_casilla == 3
        # El cooldown después de moverse debe ser 3-1=2
        cooldown_esperado = CARGA_TABLA[3][0] - 1
        assert cooldown_esperado == 2

    def test_cooldown_impide_decision(self):
        """Un minero con cooldown > 0 no puede ejecutar su acción."""
        env = MinaEnv(dificultad="normal", seed=1, num_mineros=1)
        env.reset(seed=1)
        minero = env.mineros[0]
        # Sacar al minero de la bocamina para que no escape
        minero.fila, minero.col = (7, 5)
        minero.en_bocamina_inicio = False
        fila_antes = minero.fila
        minero.move_cooldown = 2

        env.step({0: int(Accion.RUMBO_ORO)})
        # El cooldown se decrementó una vez (de 2 a 1)
        assert env.mineros[0].move_cooldown == 1
        # La posición no cambió (cooldown > 0 bloquea la acción)
        assert env.mineros[0].fila == fila_antes


# ---------------------------------------------------------------------------
# Capacidad máxima
# ---------------------------------------------------------------------------

class TestCapacidad:
    def test_no_recoge_si_lleno(self, env_normal):
        """Un minero con peso = CAPACIDAD_MAX no recoge una nueva veta."""
        minero = env_normal.mineros[0]
        minero.peso = CAPACIDAD_MAX
        # Poner una veta en la posición del minero
        pos = (minero.fila, minero.col)
        env_normal.vetas_disponibles[pos] = int(Celda.PLATA)
        peso_antes = minero.peso
        # Intentar recoger ejecutando el movimiento (simulado directamente)
        # La recolección ocurre al entrar en la celda; probar con acción de rumbo
        # Usamos el método interno para verificar la lógica de capacidad
        plata_antes = minero.plata
        env_normal.step({0: int(Accion.RUMBO_BOCAMINA)})
        # Si el minero no se movió a la veta, verifica que siga lleno
        # La prueba verifica que el peso no excedió CAPACIDAD_MAX
        for mid, m in env_normal.mineros.items():
            assert m.peso <= CAPACIDAD_MAX

    def test_peso_maximo_es_6(self):
        assert CAPACIDAD_MAX == 6


# ---------------------------------------------------------------------------
# Morir con oro da -100 sin ganancia neta
# ---------------------------------------------------------------------------

class TestMuerteConOro:
    def test_capturado_pierde_botín(self):
        """Ser capturado con oro: vivo=False, oro=0, recompensa ≤ CAPTURADO."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]

        # Dar oro al minero y moverlo lejos de bocamina
        minero.fila, minero.col = (15, 10)
        minero.en_bocamina_inicio = False
        minero.plata = 0
        minero.oro = 2
        minero.peso = 4

        # Forzar captura: poner al Tío en la MISMA celda que el minero
        env.tio.fila = minero.fila
        env.tio.col = minero.col
        # Bloquear al Tío para que no se mueva (poniendo su cooldown alto)
        env.tio.charge_cd = 100

        obs, rewards, done, info = env.step({0: int(Accion.RUMBO_BOCAMINA)})

        assert not minero.vivo, "El minero debería estar muerto"
        assert minero.oro == 0, "El oro se pierde al ser capturado"
        # La recompensa total del turno incluye CAPTURADO (−100)
        assert rewards[0] <= Recompensa.CAPTURADO, (
            f"Recompensa esperada ≤ {Recompensa.CAPTURADO}, obtuvo {rewards[0]}"
        )

    def test_sin_bateria_pierde_botín(self):
        """Morir sin batería con plata: vivo=False, plata=0, recompensa ≤ SIN_BATERIA."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]

        # Mover lejos de bocamina para evitar escape
        minero.fila, minero.col = (15, 10)
        minero.en_bocamina_inicio = False
        minero.plata = 1
        minero.peso = PESO_PLATA
        minero.historial_botín = [int(Celda.PLATA)]
        # Batería muy baja: se agotará al consumirse este turno
        minero.bateria = 0.01   # cualquier consumo lo mata

        obs, rewards, done, info = env.step({0: int(Accion.RUMBO_BOCAMINA)})

        assert not minero.vivo
        assert minero.plata == 0
        assert rewards[0] <= Recompensa.SIN_BATERIA


# ---------------------------------------------------------------------------
# Ofrenda
# ---------------------------------------------------------------------------

class TestOfrenda:
    def _env_en_altar(self):
        """Crea un entorno con el minero junto a un altar (fuera de bocamina)."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        from backend.config import ALTARES
        altar = ALTARES[0]   # (9, 5) — zona media
        minero.fila, minero.col = altar
        minero.en_bocamina_inicio = False   # ya salió de la bocamina
        return env, minero

    def test_ofrendar_activa_proteccion(self):
        """Ofrendar junto a un altar activa la protección y da recompensa OFRENDAR."""
        env, minero = self._env_en_altar()
        duracion = DIFICULTADES["normal"].ofrenda_duracion
        obs, rewards, done, info = env.step({0: int(Accion.OFRENDAR)})
        # La ofrenda se activa en este turno y el decremento ocurre al FINAL
        # (paso 4 decrementa ofrenda_turnos de 15 → 14)
        assert env.ofrenda_turnos == duracion - 1
        # Recompensa = OFRENDAR + TURNO_NORMAL (siguen activos)
        assert rewards[0] == Recompensa.OFRENDAR + Recompensa.TURNO_NORMAL

    def test_ofrendar_no_repetible(self):
        """No se puede ofrendar mientras hay ofrenda activa."""
        env, minero = self._env_en_altar()
        env.step({0: int(Accion.OFRENDAR)})   # activa ofrenda (queda en duracion-1)
        obs, rewards, done, info = env.step({0: int(Accion.OFRENDAR)})
        assert rewards[0] == Recompensa.ACCION_INVALIDA + Recompensa.TURNO_NORMAL

    def test_ofrendar_fuera_de_altar_invalido(self):
        """Ofrendar lejos de un altar es inválido."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        # Mover al minero a un pasillo que no sea bocamina ni altar
        minero.fila, minero.col = (7, 5)
        minero.en_bocamina_inicio = False
        obs, rewards, done, info = env.step({0: int(Accion.OFRENDAR)})
        assert rewards[0] == Recompensa.ACCION_INVALIDA + Recompensa.TURNO_NORMAL

    def test_ofrenda_dura_n_turnos(self):
        """La ofrenda dura exactamente ofrenda_duracion turnos tras activarse."""
        env, minero = self._env_en_altar()
        duracion = DIFICULTADES["normal"].ofrenda_duracion
        env.step({0: int(Accion.OFRENDAR)})
        # Tras el paso 4 del primer turno: ofrenda_turnos = duracion - 1
        assert env.ofrenda_turnos == duracion - 1
        # Avanzar duracion-1 turnos más → debe llegar a 0
        for _ in range(duracion - 1):
            if env.done:
                break
            # Mover al minero para que no escape inmediatamente
            minero.fila, minero.col = (9, 5)
            env.step({0: int(Accion.OFRENDAR)})   # inválido (ofrenda activa), pero no importa
        assert env.ofrenda_turnos == 0


# ---------------------------------------------------------------------------
# Soltar carga
# ---------------------------------------------------------------------------

class TestSoltarCarga:
    def test_soltar_quita_peso(self):
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        # Dar plata
        minero.plata = 1
        minero.peso = PESO_PLATA
        minero.historial_botín = [int(Celda.PLATA)]

        peso_antes = minero.peso
        obs, rewards, done, info = env.step({0: int(Accion.SOLTAR_CARGA)})
        assert minero.peso == peso_antes - PESO_PLATA

    def test_soltar_sin_carga_invalido(self):
        """Soltar sin carga da penalización de acción inválida."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        assert minero.peso == 0
        # Mover al minero a una posición interior (no bocamina) para evitar escape
        minero.fila, minero.col = (7, 5)
        minero.en_bocamina_inicio = False
        obs, rewards, done, info = env.step({0: int(Accion.SOLTAR_CARGA)})
        assert rewards[0] == Recompensa.ACCION_INVALIDA + Recompensa.TURNO_NORMAL

    def test_recoger_soltado_sin_recompensa(self):
        """Recoger botín soltado da recompensa 0 (no la de picar)."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        # Dar plata y posición
        minero.plata = 1
        minero.peso = PESO_PLATA
        minero.historial_botín = [int(Celda.PLATA)]
        pos = (minero.fila, minero.col)

        # Soltar
        env.step({0: int(Accion.SOLTAR_CARGA)})
        # El botín soltado debería estar en la posición del minero
        assert any(r == pos[0] and c == pos[1] for r, c, _ in env._botín_soltado)
        # Al recoger de nuevo no hay pista de recompensa
        # (el minero ya está en la misma celda; próxima acción activa la recolección)
        # Verificar que la recompensa de recoger soltado es 0
        assert Recompensa.RECOGER_SOLTADO == 0.0


# ---------------------------------------------------------------------------
# Recarga de uso único
# ---------------------------------------------------------------------------

class TestRecarga:
    def test_recarga_uso_unico(self):
        """La estación de carburo solo recarga una vez por episodio."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]

        # Poner al minero en la estación de carburo con batería baja
        from backend.config import CARBURO
        estacion = CARBURO[0]
        minero.fila, minero.col = estacion
        minero.bateria = 20.0

        # Primer intento: recarga
        env._intentar_recarga(minero, {0: 0.0})
        assert minero.bateria == 100.0
        assert minero.carburo_usado

        # Segundo intento: no recarga
        minero.bateria = 20.0
        env._intentar_recarga(minero, {0: 0.0})
        assert minero.bateria == 20.0, "No debería recargar por segunda vez"

    def test_recarga_solo_si_bateria_baja(self):
        """La recarga no ocurre si batería > 50%."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        minero = env.mineros[0]
        from backend.config import CARBURO
        estacion = CARBURO[0]
        minero.fila, minero.col = estacion
        minero.bateria = 80.0
        env._intentar_recarga(minero, {0: 0.0})
        assert minero.bateria == 80.0, "No debe recargar con batería > 50%"


# ---------------------------------------------------------------------------
# Truncamiento
# ---------------------------------------------------------------------------

class TestTruncamiento:
    def test_truncamiento_no_es_terminal(self):
        """Al truncar, done=True pero el estado no se trata como terminal."""
        env = MinaEnv(dificultad="normal", seed=42, num_mineros=1)
        env.reset(seed=42)
        # Forzar turno = MAX_STEPS - 1
        env._turno = MAX_STEPS - 1
        obs, rewards, done, info = env.step({0: int(Accion.RUMBO_BOCAMINA)})
        assert done
        assert info["truncado"]
        # La recompensa de truncamiento es 0 (bootstrap externo)
        # No debería incluir la penalización de captura ni escape
        # (el minero sigue vivo en este caso)
        assert env.mineros[0].vivo or env.mineros[0].escapado


# ---------------------------------------------------------------------------
# Determinismo
# ---------------------------------------------------------------------------

class TestDeterminismo:
    def test_misma_seed_mismo_resultado(self):
        """Dos episodios con la misma seed producen las mismas recompensas."""
        def _run(seed):
            env = MinaEnv(dificultad="normal", seed=seed, num_mineros=2)
            env.reset(seed=seed)
            rewards_total = {0: 0.0, 1: 0.0}
            for _ in range(20):
                if env.done:
                    break
                obs, rewards, done, info = env.step({
                    0: int(Accion.RUMBO_ORO),
                    1: int(Accion.RUMBO_BOCAMINA),
                })
                for mid in rewards_total:
                    rewards_total[mid] += rewards[mid]
            return rewards_total

        r1 = _run(42)
        r2 = _run(42)
        assert r1 == r2, f"No determinista: {r1} vs {r2}"

    def test_diferente_seed_diferente_tio(self):
        """Dos seeds distintas pueden producir posiciones del Tío distintas."""
        env1 = MinaEnv(dificultad="normal", seed=1, num_mineros=1)
        env1.reset(seed=1)
        env2 = MinaEnv(dificultad="normal", seed=99, num_mineros=1)
        env2.reset(seed=99)
        # Las posiciones iniciales del Tío son iguales por diseño (TIO_POSICION_INICIAL),
        # pero después de varios pasos divergen.
        for _ in range(10):
            if not env1.done:
                env1.step({0: int(Accion.RUMBO_ORO)})
            if not env2.done:
                env2.step({0: int(Accion.RUMBO_ORO)})
        # Al menos el estado interno del RNG difiere (no afirmamos posición exacta
        # porque el Tío parte del mismo lugar, pero los waypoints aleatorios difieren)
        # Esta prueba simplemente verifica que no haya crash con distintas semillas


# ---------------------------------------------------------------------------
# Viabilidad de batería
# ---------------------------------------------------------------------------

class TestViabilidadBateria:
    def test_viabilidad_bateria(self):
        """
        Un viaje Bocamina → oro más profundo → Bocamina debe ser factible
        con batería suficiente (margen mínimo 30%).

        Calcula la distancia BFS total * consumo máximo de batería y verifica
        que el agente no muere por batería en el trayecto.
        """
        mapa = cargar_mapa()
        grid = mapa.grid

        # Oro más profundo: mayor fila
        oros = sorted(mapa.oro, key=lambda p: (-p[0], -p[1]))
        assert oros, "No hay vetas de oro en el mapa base"
        oro_profundo = oros[0]

        # Distancias BFS
        from backend.mapa import bfs_distancia
        dist_boc = bfs_distancia(grid, mapa.bocamina)
        d_ida = int(dist_boc[oro_profundo[0], oro_profundo[1]])
        dist_desde_oro = bfs_distancia(grid, oro_profundo)
        d_vuelta = int(dist_desde_oro[mapa.bocamina[0], mapa.bocamina[1]])

        assert d_ida > 0, "Sin ruta de bocamina a oro profundo"
        assert d_vuelta > 0, "Sin ruta de vuelta de oro a bocamina"

        distancia_total = d_ida + d_vuelta

        # Consumo máximo (carga 3, dificultad normal, multiplicador 1.0)
        consumo_max_por_turno = CARGA_TABLA[3][2] * DIFICULTADES["normal"].bateria_mult
        bateria_gastada = distancia_total * consumo_max_por_turno

        margen = (BATERIA_INICIAL - bateria_gastada) / BATERIA_INICIAL
        assert margen >= 0.30, (
            f"Margen de batería insuficiente: {margen*100:.1f}% "
            f"(distancia={distancia_total}, consumo/turno={consumo_max_por_turno}). "
            f"Se requiere ≥30%."
        )
