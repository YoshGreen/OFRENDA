# 02 — Especificación de RL y Backend (`backend/`)

## 1. Idea de diseño: macro-acciones de rumbo
Los mineros IA **no deciden hacia qué casilla caminar**, deciden **qué objetivo perseguir**. El BFS solo resuelve el camino (navegación de bajo nivel). Así la Tabla Q aprende las decisiones que importan (ir al altar, soltar carga, volver, esconderse) y no hay que moldear la recompensa por distancia.

> Justificación para la defensa: es una versión simple de RL jerárquico (acciones temporalmente extendidas). La política sigue siendo 100 % aprendida; el BFS es el equivalente a "saber caminar".

## 2. MDP formal `(S, A, P, R, γ)`

### 2.1 Estado egocéntrico por minero (5.184 estados)
| # | Variable | Valores | N | Definición |
| :-: | :--- | :--- | :-: | :--- |
| 0 | `dist_tio` | 0: >8, 1: 5–8, 2: 2–4, 3: ≤1 | 4 | Distancia **por camino (BFS)** al Tío |
| 1 | `tio_lado` | 0: Tío más adentro, 1: similar, 2: Tío entre yo y la salida | 3 | `Δ = d_boc(tío) − d_boc(yo)`; `Δ>2 → 0`, `|Δ|≤2 → 1`, `Δ<−2 → 2` |
| 2 | `ofrenda_activa` | 0/1 | 2 | `turnos_ofrenda > 0` |
| 3 | `nivel_carga` | 0–3 | 4 | Ver `docs/01` §3.2 |
| 4 | `bateria` | 0: >60 %, 1: 26–60 %, 2: ≤25 % | 3 | |
| 5 | `altar_cerca` | 0/1 | 2 | En o adyacente (4-vecindad) a un altar |
| 6 | `dist_bocamina` | 0: ≤8, 1: 9–16, 2: >16 | 3 | Distancia BFS a la Bocamina |
| 7 | `botin_disponible` | 0: nada, 1: solo plata, 2: hay oro | 3 | Vetas sin recoger en el mapa (no cuenta botín soltado) |

`|S| = 4·3·2·4·3·2·3·3 = 5.184`. Codificación mixed-radix en `encode_state()` con test de ida y vuelta (`decode_state`). Tabla Q: `np.zeros((5184, 7), dtype=np.float64)`.

Todos los umbrales viven en `config.py`. `d_boc` se precalcula con un BFS desde la Bocamina al cargar el mapa; las distancias entre dos celdas arbitrarias se obtienen con BFS bajo demanda o matriz precalculada `24x24 × 24x24` (576×576 enteros, < 1 MB).

### 2.2 Acciones (7)
| ID | Acción | Efecto |
| :-: | :--- | :--- |
| 0 | `RUMBO_PLATA` | Un paso por el camino más corto hacia la veta de plata más cercana |
| 1 | `RUMBO_ORO` | Ídem hacia el oro |
| 2 | `RUMBO_ALTAR` | Ídem hacia el altar más cercano |
| 3 | `RUMBO_BOCAMINA` | Ídem hacia la Bocamina |
| 4 | `OFRENDAR` | Válida junto a un altar sin ofrenda activa |
| 5 | `APAGAR_LINTERNA` | 1 turno sin luz: el Tío no ve al minero (ruido sigue) |
| 6 | `SOLTAR_CARGA` | Suelta la última veta recogida |

Reglas de resolución:
- "Más cercana" = menor distancia BFS; desempate determinista por `(fila, columna)`.
- **Acción inválida** (objetivo inexistente, sin camino, ofrendar sin altar o con ofrenda activa, soltar sin carga) = *no-op* con penalización `−4`.
- El BFS **ignora** al Tío y a otros mineros (no hay evasión incorporada).

### 2.3 Comandos de bajo nivel
El entorno recibe por minero un `ComandoMinero(tipo, arg)`:
`MOVER(dir)`, `OFRENDAR`, `LINTERNA(on|off)`, `SOLTAR`, `QUIETO`. Las macro-acciones se traducen a comandos con `resolver_macro(estado, accion)`. Los **humanos** envían comandos de bajo nivel directamente. El log guarda ambos.

### 2.4 Semi-MDP por enfriamiento
Un minero **decide solo cuando `move_cooldown == 0`**. Entre decisiones acumula recompensa `R_acc` y cuenta `k` turnos. La transición de aprendizaje es `(s, a, R_acc, s', k)` y el descuento es `γ^k`.

### 2.5 Orden del turno
1. Observación de los mineros listos y elección de acción (IA) o lectura del buffer de entrada (humano).
2. Ejecución de comandos: movimiento, recolección, ofrenda, linterna, soltar.
3. Resolución de **escapes** (entrar a la Bocamina es seguro: se evalúa antes de mover al Tío).
4. Consumo de batería, recarga en estaciones, decremento de ofrenda y enfriamientos.
5. Movimiento de El Tío (FSM, §6).
6. **Capturas**: el Tío y el minero comparten celda, o se cruzaron al intercambiar celdas, o el Tío pasó por la celda del minero durante una embestida.
7. Muertes por batería; cálculo de recompensas; truncamiento si `turno == max_steps`.

### 2.6 Recompensa `R(s, a, s')`
| Evento | `r` |
| :--- | :---: |
| Escapar con mineral | `+50 + 30·plata + 70·oro` |
| Escapar vacío | `−10` |
| Picar plata / oro (veta original) | `+4` / `+8` |
| Recoger botín soltado | `0` |
| Turno normal en la mina | `−1` |
| Acción inválida | `−4` |
| Ofrenda válida | `−6` |
| Apagar linterna | `−2` |
| Soltar carga | `−3` |
| Recargar (batería ≤ 50 %, uso único) | `+5` |
| Ser atrapado | `−100` |
| Batería a 0 % | `−100` |
| Truncamiento (300 turnos) | `0` (se bootstrapea con `γ·V(s')`, no es terminal) |

**Shaping:** desactivado por defecto. Existe el flag `shaping_potencial` (potential-based, `F = γΦ(s') − Φ(s)`, `Φ = −β·d_boc`) solo para experimentos documentados en la bitácora.

## 3. Algoritmos (`rl_agents.py`)
Clase `TabularRLAgent(algorithm="q_learning" | "sarsa", alpha, gamma, epsilon_*, rng)`.

- **ε-voraz:** acción aleatoria con prob. `ε`; si no, `argmax_a Q(s,a)` con desempate aleatorio **entre las acciones válidas** (máscara de validez opcional configurable, desactivada por defecto para que aprenda a evitar inválidas).
- **Decaimiento:** `ε_ep = max(ε_min, ε_0 · λ^ep)` con `λ = (ε_min/ε_0)^(1/(f·N))`, `f = 0,6`. Así `ε` llega al mínimo al 60 % del entrenamiento sin importar `N` (1.000, 5.000 o 10.000 episodios).
- **Q-Learning:** `δ = R_acc + γ^k · max_a' Q(s',a') − Q(s,a)`.
- **SARSA:** `δ = R_acc + γ^k · Q(s',a') − Q(s,a)` con `a'` elegida por la misma política `ε`-voraz.
- Estado terminal: el término de bootstrap vale 0. Truncamiento: se bootstrapea.
- **Parameter sharing:** todos los mineros de un **cerebro** leen y escriben la misma Tabla Q. En el modo Duelo hay varios cerebros, cada uno con su tabla.
- Se registra `|δ|` en cada actualización.

Hiperparámetros por defecto: `α=0,1`, `γ=0,95`, `ε: 1,0→0,05`, `N=5.000`, `num_miners=3`, `seed=42`.

## 4. Entrenamiento (`trainer.py`, `train.py`)
- **Robustez:** en cada episodio se aleatoriza la agresividad del Tío en `[0,7 ; 1,3]` (multiplica radios y probabilidades) y la posición inicial de patrulla. Opcional: entrenar con `K` mapas generados por semilla y evaluar en mapas no vistos (experimento de generalización).
- **Evaluación periódica** (cada `eval_every=250` episodios): 100 episodios con semillas disjuntas a las de entrenamiento, en dos modos: `greedy (ε=0)` y `ε=0,1`. SARSA y Q-Learning se distinguen sobre todo en el desempeño **durante el entrenamiento** y con `ε>0`.
- **Checkpoints de experiencia** para el juego: episodio `0` (Novato), 2 %, 10 %, 30 % y 100 % del entrenamiento, más `best` por evaluación. El menú los presenta como Novato / Aprendiz / Veterano / Experto.
- **Rendimiento:** el bucle interno usa enteros y listas planas; evita crear objetos por paso. Meta orientativa: 5.000 episodios en ≤ 60 s en una laptop común. **Medir y registrar** el tiempo real en el manifiesto; no asumir cifras.
- Toda corrida escribe en `bitacora/` mediante `RunLogger` (ver `docs/05`).

### CLI
```bash
python -m backend.train --algorithm sarsa --episodes 10000 --gamma 0.95 --alpha 0.1 \
  --epsilon-start 1.0 --epsilon-min 0.05 --num-miners 3 --seed 7 --name prudente \
  --difficulty normal --notes "primera corrida de SARSA con decaimiento 60%"
```

## 5. Cerebros (`backend/models/<brain_id>/`)
```text
q_table.npy        # Tabla Q final
brain.json         # id, nombre_visible, algoritmo, descripcion_leyenda, checkpoint, episodio, config_hash, run_id
checkpoints/       # q_ep0.npy, q_ep100.npy, ...
```
`GET /api/brains` devuelve solo lo que el juego necesita (nombre, descripción en lenguaje de la leyenda, nivel de experiencia). **Nunca** métricas.

## 6. El Tío (`tio_fsm.py`)
FSM probabilística, determinista dada la semilla.
- **PATRULLANDO:** caminata sesgada hacia la zona profunda y hacia las vetas de oro; escoge waypoints; 15 % de probabilidad de quedarse quieto un turno.
- **ALERTADO:** si algún minero está a distancia BFS `≤ radio_efectivo` (radio de ruido según carga; mitad con ofrenda; si el minero apagó linterna, la probabilidad de detección se multiplica por `0,2`), va a la última celda donde lo percibió durante hasta 6 turnos.
- **PERSIGUIENDO:** si ve a un minero (linterna encendida a distancia `≤ 4`, o `≤ 2` con ofrenda; o ruido) avanza por BFS hacia el más cercano. Si lo pierde 8 turnos vuelve a patrullar.
- **Embestida:** persiguiendo, con distancia `≤ 3` y enfriamiento en 0, se mueve **2 casillas** en un turno. Enfriamiento según dificultad. Deshabilitada con ofrenda activa.
- Velocidad base: 1 casilla/turno. Un minero con carga 0–1 iguala su velocidad; cargado, no.
- Para el modo "Ser El Tío", el humano reemplaza la FSM (ver `docs/04`); el entorno expone el mismo contrato de comandos para el Tío (`MOVER`, `EMBESTIR`, `RUGIR`, `OSCURIDAD`).

## 7. API del entorno (`mina_env.py`)
```python
env = MinaEnv(config, seed)
obs = env.reset(seed)                       # dict minero_id -> estado discreto + info
obs, rewards, done, info = env.step(comandos, comando_tio=None)
env.snapshot()                              # dict serializable (ver §8)
```
`info` incluye eventos del turno (`picó`, `soltó`, `ofrendó`, `atrapado`, `escapó`, `sin_batería`, `embestida`, `rugido`) que alimentan animaciones, audio y registros.

## 8. Contrato de red

### REST
- `GET /api/config` → constantes públicas (tamaños, tiempos de tick, dificultades, radios).
- `GET /api/map?seed=` → matriz, Bocamina, altares, vetas, estaciones.
- `GET /api/brains` → cerebros disponibles (solo metadatos de juego).

### WebSocket `/ws/game`
Cliente → servidor:
```json
{"cmd":"start","mode":"observer|human|tio|duel","brains":{"cuadrilla_a":"audaz_experto"},
 "num_miners":3,"seed":123,"difficulty":"normal","tick_ms":450,"human_slot":0}
{"cmd":"input","action":{"type":"move","dir":"N"}}   // move|offer|light|drop|wait ; en modo tío: move|charge|roar|darkness
{"cmd":"pause"} {"cmd":"resume"} {"cmd":"set_speed","speed":2} {"cmd":"quit"}
```
Servidor → cliente (un frame por turno):
```json
{"turn":42,"done":false,"result":null,"offering_turns":11,
 "miners":[{"id":0,"brain":"audaz_experto","row":14,"col":9,"facing":2,"alive":true,"escaped":false,
   "silver":1,"gold":1,"load_level":2,"move_cooldown":1,"battery":68,"light_on":true,
   "is_human":false,"score_bs":0,"visual_ticks":2,"last_event":"moved"}],
 "tio":{"row":17,"col":10,"facing":0,"mode":"ALERTADO","detection_radius":3,"charge_cd":2,"is_human":false},
 "remaining_silver":[[10,4]],"remaining_gold":[[19,12]],"dropped_loot":[],"events":["offered:0"]}
```
`visual_ticks` indica en cuántos ticks debe completarse la animación del movimiento (lentitud visible por carga). Los campos de depuración (`state_idx`, `q_values`) solo se envían con `"debug": true` en `start` y **no se muestran en el juego**; sirven para registrar replays.

Servidor autoritativo: el tick corre en el servidor; la entrada humana se **almacena en un buffer de una posición** y se consume en el siguiente tick.

## 9. Pruebas obligatorias
- `test_env.py`: conectividad del mapa, tabla de cooldown (carga 3 ⇒ 3 turnos/casilla), capacidad máxima, **morir con oro da −100 sin ganancia neta**, ofrenda (duración, efectos, no repetible), soltar carga sin recompensa al recoger de nuevo, recarga de uso único, capturas por cruce y embestida, truncamiento sin terminal, determinismo por semilla, `test_viabilidad_bateria`.
- `test_encoding.py`: ida y vuelta de `encode_state/decode_state`, rango `[0, 5183]`.
- `test_agents.py`: actualización TD correcta a mano para Q-Learning y SARSA, con `k > 1`.
- `test_convergence.py`: Q-Learning y SARSA a `γ=0,95` superan al agente aleatorio en tasa de escape y en Bs medios; el agente con `γ=0,95` ofrenda más que uno con `γ=0,2`. Umbrales conservadores definidos tras medir y anotados en `bitacora/DECISIONES.md`.
- `test_bitacora.py`: una corrida corta genera manifiesto, CSV, resumen, chart_specs e índice válidos.
- `test_server.py`: cliente WebSocket completo en modo observador, humano y tío.
