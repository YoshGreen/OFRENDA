# CLAUDE.md / AGENTS.md — El Tío de la Mina (RL 3D)

> Archivo maestro para **Claude Code**, **Antigravity** y **Kimi Code**. `AGENTS.md` es una copia idéntica de este archivo (si tu herramienta usa otra ruta de reglas, copia este contenido allí). Si modificas uno, modifica el otro.

## 1. Qué es este proyecto
Videojuego 3D de terror en navegador, basado en la leyenda boliviana de **El Tío de la Mina** (Cerro Rico, Potosí). Una cuadrilla de mineros controlados por **Aprendizaje por Refuerzo tabular** (Q-Learning y SARSA) explora un socavón de `24x24` celdas buscando plata y oro, gestionando su avaricia (peso y lentitud), su batería y las ofrendas (*ch'alla*) para escapar con vida de **El Tío**, un demonio gigante con cuernos.

Es un proyecto universitario de **Machine Learning (Aprendizaje por Refuerzo)**: MDP, Bellman, Diferencias Temporales, Q-Learning y SARSA. El producto final es **un juego**, no un dashboard. Todo lo analítico (métricas, gráficas, registros) vive **fuera del juego**, en la carpeta `bitacora/`.

## 2. Principios NO negociables
1. **Lógica en Python, gráficos en JS.** Todo el juego (turnos, colisiones, Tío, recompensas) vive en `backend/` sobre una matriz discreta. El servidor es **autoritativo**; el frontend solo renderiza, interpola y envía entradas.
2. **RL tabular puro.** Tablas Q en NumPy, Q-Learning (*off-policy*) y SARSA (*on-policy*), ecuaciones de Bellman, TD, `ε`-voraz. **Prohibido** PyTorch/TensorFlow y reglas fijas de decisión para los mineros IA (`if tio_cerca: huir`). El BFS se usa solo como **navegación de bajo nivel** de las macro-acciones de rumbo (ver `docs/02`).
3. **Recompensa diferida.** El pago fuerte del botín se entrega solo al **cruzar la Bocamina con vida**. Al picar solo hay una pista pequeña. Evita el exploit de "morir rico".
4. **Dos métricas separadas.** *Recompensa RL* (interna, para aprender) y *Puntuación en Bs* (visible al jugador).
5. **Entrenamiento offline y headless**, solo por CLI (`python -m backend.train ...`). El juego **no entrena**, **no muestra gráficas, Q-values, mapas de calor ni paneles de ML**. El HUD del juego es solo de juego (batería, carga, puntaje, avisos).
6. **Bitácora obligatoria.** Cada corrida de entrenamiento y cada sesión de trabajo se registra en `bitacora/` (ver `docs/05`). El frontend jamás lee ni muestra la bitácora.
7. **Determinismo.** Con la misma `seed`, el entorno y el entrenamiento deben dar resultados idénticos.
8. **Calidad visual profesional.** Mineros con animación de caminar convincente y El Tío aterrador y enorme (ver `docs/03`). Sin assets externos pesados: modelos procedurales con Three.js.
9. **60 FPS** en preset de calidad "Media" en una laptop con GPU integrada.
10. **Idioma:** todo texto visible, comentarios de dominio y documentación en **español**.

## 3. Stack
- **Backend:** Python 3.11+, `numpy`, `fastapi`, `uvicorn`, `websockets`, `pydantic`, `pytest`.
- **Frontend:** HTML5, CSS3, JavaScript ES Modules sin paso de build, **Three.js con versión fija** (`three@0.160.0` vía `importmap` desde CDN o copia local en `frontend/vendor/`). Audio con Web Audio API procedural.
- **Prohibido:** Unity, Godot, PyTorch/TensorFlow, motores de física (Cannon/Ammo), librerías de gráficas dentro del juego.

## 4. Estructura del repositorio
```text
el-tio-de-la-mina-rl/
├── CLAUDE.md / AGENTS.md
├── README.md
├── docs/
│   ├── 01_VISION_Y_REGLAS_DEL_JUEGO.md
│   ├── 02_ESPECIFICACION_RL.md
│   ├── 03_ESPECIFICACION_3D_Y_PERSONAJES.md
│   ├── 04_MENU_Y_MODOS_DE_JUEGO.md
│   ├── 05_BITACORA_Y_REGISTRO.md
│   └── 06_PLAN_Y_PROMPTS.md
├── backend/
│   ├── requirements.txt
│   ├── config.py            # constantes, mapa base, recompensas, hiperparámetros, dificultades
│   ├── mapa.py              # mapa base, generador por semilla, BFS precalculado
│   ├── mina_env.py          # entorno MDP discreto multi-minero
│   ├── tio_fsm.py           # comportamiento de El Tío (FSM probabilística)
│   ├── rl_agents.py         # TabularRLAgent (q_learning | sarsa), cerebros
│   ├── trainer.py           # bucle headless, evaluación, checkpoints
│   ├── train.py             # CLI de entrenamiento
│   ├── bitacora.py          # RunLogger: manifiestos, métricas, chart_specs
│   ├── game_session.py      # bucle de partida por modos (tick, humanos, IA)
│   ├── server.py            # FastAPI: REST + WebSocket + estáticos
│   ├── models/              # cerebros entrenados (<brain_id>/)
│   └── tests/
├── bitacora/                # registro fuera del juego (ver docs/05)
├── tools/
│   ├── diario.py            # añade entradas al diario de desarrollo
│   ├── experimentos.py      # lotes: ablaciones, comparativas, semillas
│   └── exportar_corrida.py  # empaqueta una corrida para el dashboard externo
└── frontend/
    ├── index.html
    ├── styles.css
    ├── dev/debug_2d.html    # visor 2D solo para desarrollo (no enlazado en el menú)
    └── js/
        ├── main.js              # arranque, máquina de pantallas
        ├── net.js               # WebSocket y REST
        ├── screens/             # menu, como_se_juega, modos, opciones, pausa, resultados
        ├── world/               # mina_3d.js, iluminacion.js, particulas.js
        ├── actors/              # minero_rig.js, tio_rig.js, animacion.js
        ├── camera/              # cameras.js, director.js
        ├── input/               # teclado y mouse por modo
        └── audio/               # audio_procedural.js
```

## 5. Orden de lectura antes de programar
1. Este archivo y las **últimas 3 entradas** de `bitacora/DIARIO_DESARROLLO.md` (estado actual y traspasos).
2. `docs/01` siempre. Luego según la tarea: `docs/02` (backend/RL), `docs/03` (3D), `docs/04` (menú/modos), `docs/05` (registro).
3. `docs/06` para saber en qué fase estás y sus criterios de aceptación.

## 6. Protocolo de trabajo (varios agentes comparten este repo)
- Trabaja **una fase a la vez**, en orden. No avances si los criterios de aceptación de la fase actual no pasan.
- No edites archivos que pertenecen a otra fase sin dejarlo anotado en el diario.
- Antes de terminar una sesión: ejecuta `pytest -v`, y registra con `python tools/diario.py add --fase N --titulo "..." --hecho "..." --decisiones "..." --pendiente "..."`.
- Si una instrucción de la documentación es ambigua o contradictoria, **no inventes en silencio**: elige la opción más simple, regístrala en `bitacora/DECISIONES.md` y continúa.
- Commits pequeños y descriptivos en español (`feat(env): cooldown por carga`).
- Valores numéricos viven **solo** en `backend/config.py`. Nunca se duplican en el frontend: el servidor los envía en `/api/config`.

## 7. Definición de "terminado"
Una tarea está terminada solo si: (1) cumple los criterios de la fase, (2) `pytest -v` pasa, (3) no hay errores en consola del navegador, (4) no hay `TODO`/código de relleno, (5) el diario está actualizado.

## 8. Comandos
```bash
cd backend && python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v
python -m backend.train --algorithm q_learning --episodes 5000 --gamma 0.95 --alpha 0.1 --seed 42 --name audaz
uvicorn backend.server:app --reload --host 0.0.0.0 --port 8000   # juego en http://localhost:8000
```

## 9. Convenciones
- **Python:** type hints estrictos, docstrings breves en español, `dataclasses`/`enum` para estados y acciones.
- **JavaScript:** ES Modules, sin globales, `InstancedMesh` para paredes, sin asignar objetos dentro del bucle de render, `dispose()` de geometrías/materiales al cambiar de pantalla.
- **Archivos pequeños y cohesivos.** Un módulo = una responsabilidad.

## 10. Qué NO hacer
- No poner gráficas, Q-values, mapas de calor ni sliders de hiperparámetros en el juego.
- No sustituir la Tabla Q por heurísticas.
- No usar Manhattan donde la spec pide distancia por camino (BFS).
- No bajar la altura del túnel por debajo de lo que exige El Tío (ver `docs/03`).
- No descargar modelos `.glb` ni texturas externas.
