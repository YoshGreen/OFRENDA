# 06 — Plan de Implementación por Fases y Prompts

Orden obligatorio. No se pasa a la siguiente fase sin cumplir los criterios de aceptación de la actual. Cada fase termina con `pytest -v` en verde (cuando aplique) y una entrada en `bitacora/DIARIO_DESARROLLO.md`.

## Resumen
| Fase | Objetivo | Entregable principal |
| :-: | :--- | :--- |
| 0 | Fundación y bitácora | Estructura, `config.py`, mapa base validado, `tools/diario.py`, esqueleto de `RunLogger` |
| 1 | Entorno MDP | `mina_env.py`, `tio_fsm.py`, `mapa.py` + pruebas |
| 2 | RL tabular, entrenamiento y registro | `rl_agents.py`, `trainer.py`, `train.py`, `bitacora.py` completo, cerebros y checkpoints |
| 3 | Servidor y sesiones de juego | `server.py`, `game_session.py`, WS `/ws/game`, visor `dev/debug_2d.html` |
| 4 | Mundo 3D y cámaras | Mina, luces, niebla, cámaras 0/1–3/T/Tab/C (con marcadores simples) |
| 5 | Mineros animados | Rig, caminar por distancia, estados y eventos |
| 6 | El Tío | Modelo demoníaco, animaciones, sistema de terror |
| 7 | Menú y modos | Pantallas, Modo A, B, C |
| 8 | Audio, postproceso y calidad | Audio procedural, presets, optimización |
| 9 | Duelo, extras y cierre | Modo D, replays, experimentos finales, README, entrega |

## Fase 0 — Fundación
- Crear estructura de `CLAUDE.md` §4, `requirements.txt`, `.gitignore`, `README.md`.
- `config.py`: constantes (mapa, recompensas, dificultades, umbrales de estado, hiperparámetros) con `config_hash()`.
- `mapa.py`: `MAPA_BASE` y generador por semilla cumpliendo `docs/01` §2; BFS y matriz de distancias.
- `tools/diario.py` y `backend/bitacora.py` (clase `RunLogger` con manifiesto y CSV mínimos).
- **Aceptación:** pruebas de conectividad y de restricciones del mapa pasan; `tools/diario.py add` escribe una entrada válida.

## Fase 1 — Entorno MDP
- `MinaEnv` completo según `docs/02` §2: macro-acciones y comandos, semi-MDP, orden del turno, capacidad, soltar carga, ofrenda, batería, recarga única, capturas por cruce y embestida, truncamiento.
- `tio_fsm.py` según `docs/02` §6.
- **Aceptación:** `test_env.py` y `test_encoding.py` al 100 %, incluyendo: carga 3 ⇒ 3 turnos por casilla; morir con oro da `−100` sin ganancia; recoger botín soltado no da recompensa; determinismo por semilla; `test_viabilidad_bateria`.

## Fase 2 — RL, entrenamiento y registro
- `TabularRLAgent` (Q-Learning y SARSA, semi-MDP con `γ^k`), `trainer.py` con evaluación y checkpoints, `train.py` CLI, `RunLogger` completo (CSV, eval, summary, chart_specs, index).
- `tools/experimentos.py` con los lotes de `docs/05` §13.
- **Aceptación:** `test_agents.py`, `test_convergence.py`, `test_bitacora.py` en verde; una corrida real de 5.000 episodios por algoritmo guardada en `bitacora/runs/` con su cerebro y checkpoints en `backend/models/`; comparación Q-Learning vs SARSA impresa en consola y registrada; tiempos reales anotados en el diario.

## Fase 3 — Servidor y sesiones
- `server.py` con `/api/config`, `/api/map`, `/api/brains`, estáticos y `/ws/game` según `docs/02` §8.
- `game_session.py`: bucle por tick, buffer de entrada de humano (1 posición), modos `observer`, `human`, `tio`, `duel` (puede dejarse `duel` listo para la Fase 9), pausa y velocidad.
- `frontend/dev/debug_2d.html`: visor 2D de desarrollo (no enlazado).
- **Aceptación:** `test_server.py` en verde; se puede ver una partida completa en el visor 2D en los tres modos; entrenar o cargar no bloquea el servidor.

## Fase 4 — Mundo 3D y cámaras
- Mina procedural, luces, niebla, partículas ambientales, Bocamina, altares y vetas; marcadores simples (cápsulas) para mineros y Tío; cámaras `0`, `1–3`, `T`, `Tab`, `C`; interpolación con `visual_ticks`.
- **Aceptación:** 60 FPS en Media, sin errores de consola, cambio de cámara sin saltos, el túnel acomoda 3,6 m.

## Fase 5 — Mineros animados
- Rig completo y ciclo de caminar por distancia (`docs/03` §3), inclinación por carga, saco de botín, linterna real, ojos, animaciones de evento.
- **Aceptación:** checklist visual de `docs/03` §9 (puntos de mineros).

## Fase 6 — El Tío
- Modelo demoníaco con cuernos, dientes, brasa, capa, cola y pezuñas; animaciones de patrulla, alerta/rugido, persecución, embestida, ofrenda y captura; sistema de terror (sacudidas, viñeta, parpadeo de linternas, latido).
- **Aceptación:** checklist visual de `docs/03` §9 (puntos del Tío); ≤ 30.000 triángulos; 60 FPS en Media.

## Fase 7 — Menú y modos
- Pantallas de `docs/04`, "¿Cómo se juega?", mini-tutorial, Opciones, Pausa, Informe; Modo A, Modo B, Modo C.
- **Aceptación:** criterios de `docs/04` §5.

## Fase 8 — Audio, postproceso y calidad
- `audio_procedural.js`, presets Baja/Media/Alta, viñeta, grano, bloom, accesibilidad (reducir sacudidas), optimización final.
- **Aceptación:** sin cortes de audio al pausar/reanudar; 60 FPS en Media; Baja corre en hardware modesto.

## Fase 9 — Duelo, extras y cierre
- Modo D (Duelo de Cerebros); al menos **Replay de expediciones**; experimentos finales con `tools/experimentos.py` (Q vs SARSA, `γ=0,2` vs `0,95`, con/sin altares, generalización a mapas no vistos, 5 semillas); `README.md` académico; exportación para el dashboard.
- **Aceptación:** una partida de cada modo sin errores; todas las corridas documentadas en `bitacora/`; `README.md` con instalación, comandos y mapa de la documentación.

---

## Prompts listos para copiar
> **Prefacio común (pegar antes de cada prompt):** *Lee `CLAUDE.md`, las últimas 3 entradas de `bitacora/DIARIO_DESARROLLO.md` y los documentos de `docs/` indicados. Trabaja solo en esta fase. No uses código de relleno. Ejecuta `pytest -v` cuando corresponda. Al terminar, registra tu trabajo con `python tools/diario.py add` y anota decisiones ambiguas en `bitacora/DECISIONES.md`.*

### Prompt 1 — Fases 0 y 1
> Lee `docs/01_VISION_Y_REGLAS_DEL_JUEGO.md` y `docs/02_ESPECIFICACION_RL.md` §1–2 y §6–7. Implementa la Fase 0 y la Fase 1: estructura del repositorio, `config.py`, `mapa.py` (mapa base validado y generador por semilla), `tools/diario.py`, esqueleto de `RunLogger`, `mina_env.py` y `tio_fsm.py`, con `test_env.py` y `test_encoding.py`. Respeta macro-acciones, semi-MDP por enfriamiento, capacidad máxima, recarga de uso único, recompensa diferida y orden del turno. Itera hasta que todas las pruebas pasen.

### Prompt 2 — Fase 2
> Lee `docs/02` completo y `docs/05`. Implementa `rl_agents.py`, `trainer.py`, `train.py` y el `RunLogger` completo. Q-Learning y SARSA con *parameter sharing*, `γ^k` por enfriamiento, decaimiento de `ε` al 60 % del entrenamiento, evaluación `greedy` y `ε=0,1`, checkpoints de experiencia y registro completo en `bitacora/`. Entrena 5.000 episodios por algoritmo, mide tiempos reales y deja las corridas registradas. Añade `test_agents.py`, `test_convergence.py`, `test_bitacora.py` con umbrales calibrados y anotados en `DECISIONES.md`.

### Prompt 3 — Fase 3
> Lee `docs/02` §8 y `docs/04` §2–3. Implementa `server.py` y `game_session.py` con REST y `/ws/game` según el contrato, tick fijo en el servidor, buffer de entrada de una posición para el humano, modos `observer`, `human` y `tio`, y el visor `frontend/dev/debug_2d.html`. El servidor no debe bloquearse durante operaciones largas. Añade `test_server.py`.

### Prompt 4 — Fases 4 y 5
> Lee `docs/03` completo. Implementa el mundo 3D (`world/`), las cámaras (`camera/`) y los mineros animados (`actors/minero_rig.js`, `animacion.js`) conectados al WebSocket. Caminar con fase por distancia recorrida, inclinación por carga, linterna real, ojos expresivos, animaciones de evento e interpolación con `visual_ticks`. Usa `three@0.160.0` fijo, `InstancedMesh` para paredes y respeta los presupuestos de luces y rendimiento.

### Prompt 5 — Fase 6
> Lee `docs/03` §4 y §9. Implementa `actors/tio_rig.js`: demonio de 3,6 m con cuernos curvos, dientes afilados, ojos rojos emisivos, puro con brasa, capa, cola y pezuñas; animaciones de patrulla, rugido, persecución, embestida, ofrenda y captura; y el sistema de terror (sacudida de cámara, viñeta, latido, parpadeo de linternas). Verifica el checklist visual y el presupuesto de triángulos.

### Prompt 6 — Fases 7 y 8
> Lee `docs/04` completo y `docs/03` §7–8. Implementa las pantallas (menú con fondo 3D vivo, "¿Cómo se juega?" con mini-tutorial, opciones, pausa, informe), el Modo A, el Modo B y el Modo C, el audio procedural y los presets de calidad. No incluyas gráficas, Q-values ni indicadores de IA. Cumple los criterios de aceptación de `docs/04` §5.

### Prompt 7 — Fase 9
> Lee `docs/04` §3 (Modo D y modos futuros) y `docs/05` §13. Implementa el Modo D (Duelo de Cerebros) y el Replay de expediciones desde `bitacora/`; ejecuta los experimentos finales con `tools/experimentos.py`, genera las comparativas y escribe el `README.md` académico. Registra todo en el diario.

---

## Riesgos y mitigaciones
| Riesgo | Mitigación |
| :--- | :--- |
| El 3D consume demasiado tiempo | Fases 4–6 se validan primero con marcadores y el visor 2D; el backend ya está probado antes |
| Entrenamiento lento | Medir en Fase 2; bucle con enteros/listas planas; si no basta, reducir episodios o el espacio de estados (decisión registrada) |
| Q-Learning y SARSA parecen iguales | Comparar desempeño durante el entrenamiento y con `ε=0,1`, varias semillas, intervalos de confianza |
| El humano en modo Tío rompe a la IA | Aleatorización de agresividad del Tío en el entrenamiento; cerebro Experto |
| Dos agentes de código editan lo mismo | Dueño por fase, diario y `DECISIONES.md` como traspaso |
| Afirmaciones de originalidad sin sustento | Verificar manualmente repositorios y tiendas antes de afirmar "inédito" |
