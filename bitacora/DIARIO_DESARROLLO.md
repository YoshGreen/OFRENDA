# Diario de Desarrollo — El Tío de la Mina

Registro cronológico de sesiones de trabajo.
Formato: cada entrada es un bloque Markdown creado por `python tools/diario.py add`.

---

## [2026-11-26 20:16] Fase 0 — Fundacion del proyecto

**Hecho:**
Creada toda la estructura: config.py (constantes, Celda, Dificultad, Recompensa, config_hash), mapa.py (MAPA_BASE 24x24, BFS, MapaInfo, validar_mapa, generar por semilla), tools/diario.py (CLI de registro), backend/bitacora.py (RunLogger esqueleto con manifiesto JSON + CSV). Creados directorios: backend/, bitacora/, tools/, frontend/js/, backend/tests/, backend/models/. Creados .gitignore, pytest.ini, requirements.txt, __init__.py para todos los paquetes.

**Decisiones registradas:**
MAPA_BASE fijo en config.py como lista de listas; el generador por semilla permuta posiciones de vetas dentro de sus zonas conservando paredes/bocamina/altares/carburo. Las vetas de plata deben estar en filas 8-15 y el MAPA_BASE original tenia plata en zona profunda: se corrigio. Se necesitaban 6 vetas de plata pero el mapa original solo tenia 4: se anadieron 2 en fila 15.

**Pendiente:**
Fase 1 completada en esta misma sesion

---

## [2026-11-26 20:16] Fase 1 — Entorno MDP, TioFSM y tests

**Hecho:**
Implementados mina_env.py (MinaEnv, EstadoMinero, encode_state, decode_state, Accion), tio_fsm.py (TioFSM con FSM probabilistica PATRULLANDO/ALERTADO/PERSIGUIENDO, embestida, deteccion por ruido y vision). Tests: test_encoding.py (5 tests, ida/vuelta, rango 0-5183) y test_env.py (29 tests: mapa, cooldown, capacidad, muerte con ore, ofrenda, soltar, recarga, truncamiento, determinismo, viabilidad de bateria). 34/34 en verde en 1.63s.

**Decisiones registradas:**
Escape solo ocurre si el minero se movio a la bocamina en este episodio (flag en_bocamina_inicio). La ofrenda se activa con ofrenda_turnos=duracion en el paso 2 y se decrementa en el paso 4 del mismo turno, quedando en duracion-1 al final del turno de activacion. La penalizacion TURNO_NORMAL solo se aplica a mineros que siguen activos al final del turno (vivos y no escapados). Un minero en bocamina con bateria=0 no muere si su bateria era exactamente 0 al inicio del turno (el consumo de paso 4 ya no puede bajarla mas).

**Pendiente:**
Fase 2: rl_agents.py, trainer.py, train.py, RunLogger completo, test_agents.py, test_convergence.py, test_bitacora.py

---
