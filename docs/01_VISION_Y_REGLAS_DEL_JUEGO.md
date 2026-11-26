# 01 — Visión y Reglas del Juego

## 1. Visión
**El Tío de la Mina** es un juego de terror y supervivencia en un socavón del Cerro Rico de Potosí. El jugador (o la IA) es un minero que debe sacar mineral y volver a la Bocamina antes de que lo alcance **El Tío**, el guardián demoníaco de la mina. Cada decisión es un dilema de riesgo: más botín significa más peso, más lentitud y más ruido; una ofrenda cuesta tiempo hoy pero protege mañana.

### Pilares de experiencia
1. **Tensión por decisión:** codicia vs. supervivencia.
2. **Atmósfera:** oscuridad total, linternas, niebla, ojos rojos a lo lejos, sonido.
3. **Cultura:** la *ch'alla* (coca, cigarro, alcohol) como mecánica central, no como adorno.
4. **IA visible sin gráficas:** el público entiende que los mineros "aprenden" porque los ve comportarse distinto según su nivel de experiencia (Novato, Aprendiz, Experto), no por paneles.

### Contexto académico (solo para documentación y defensa, no para el juego)
| Concepto de la materia | Dónde aparece |
| :--- | :--- |
| Agente | Cada minero IA (cuadrilla con *parameter sharing*) |
| Entorno | Socavón `24x24` + El Tío |
| Estado / Acción / Recompensa | `docs/02` |
| Política | `ε`-voraz al entrenar, `argmax Q` al jugar |
| Exploración vs. explotación | Decaimiento de `ε` |
| Objetivo a largo plazo | `γ` alto aprende a ofrendar; `γ` bajo no |
| Q-Learning vs. SARSA | Cerebros "Audaz" y "Prudente" |

## 2. El mapa (`24x24`)
Matriz de enteros. Coordenadas `(fila, columna)`; fila 0 arriba.

| Código | Celda |
| :---: | :--- |
| `0` | Pasillo |
| `1` | Pared de roca (bloquea movimiento y visión) |
| `2` | **Bocamina** (inicio y salida) |
| `3` | Veta de plata (peso 1) |
| `4` | Veta de oro (peso 2) |
| `5` | Altar de El Tío |
| `6` | Estación de carburo (recarga batería) |

### Zonas
- **Superior (filas 0–7):** Bocamina y una estación de carburo. Segura.
- **Media (filas 8–15):** galerías con vetas de plata, 3 altares en cruces y una segunda estación de carburo.
- **Profunda (filas 16–23):** cámaras de oro. Territorio de El Tío.

### Restricciones del mapa base (`MAPA_BASE` en `config.py`, validadas por test)
- Conectividad total por BFS entre la Bocamina y **todas** las celdas transitables, altares, estaciones y vetas.
- Al menos **2 rutas distintas** hacia la zona profunda (permite emboscadas y rodeos).
- Mínimo 6 vetas de plata (zona media), 4 de oro (zona profunda), 3 altares, 2 estaciones de carburo.
- Pasillos mayormente de 1 celda de ancho con cámaras de `3x3`.
- Un viaje de ida y vuelta Bocamina → oro más profundo → Bocamina debe ser factible con batería (test `test_viabilidad_bateria`, margen mínimo 30%).
- Existe un generador por semilla (`mapa.generar(seed)`) que respeta las mismas restricciones. El **mapa base fijo** es el de referencia para entrenar y comparar.

## 3. Mecánicas

### 3.1 Turnos
El juego es **por turnos discretos con reloj fijo** (`tick`). Cada turno: los mineros listos eligen acción, se ejecutan, se mueve El Tío, se resuelven capturas y escapes. En modos con humano el tick corre en tiempo real (ver `docs/04`).

### 3.2 Avaricia: peso, lentitud y ruido
| `nivel_carga` | Peso | Turnos por casilla | Radio de ruido | Batería por turno |
| :---: | :---: | :---: | :---: | :---: |
| 0 Vacío | 0 | 1 | 3 | 0,5 % |
| 1 Ligero | 1–2 | 1 | 3 | 0,5 % |
| 2 Pesado | 3 | 2 | 5 | 0,75 % |
| 3 Avaricioso | ≥ 4 | 3 | 7 | 1,0 % |

- Plata pesa **1** (500 Bs), oro pesa **2** (1.200 Bs).
- **Capacidad máxima: 6 unidades.** Si una veta no cabe, no se recoge.
- Tras moverse una casilla, el minero queda en **recuperación** (`move_cooldown = turnos_por_casilla − 1`) y no puede decidir hasta terminar. Es el castigo de la codicia: El Tío no espera.
- **Soltar carga:** suelta la última veta recogida (plata −1, oro −2 de peso) en la celda actual. Queda recogible por cualquiera, pero **sin pista de recompensa** al recogerla de nuevo.
- **Recolección automática** al entrar en una celda con veta (si cabe).

### 3.3 La ofrenda (*ch'alla*)
- Se ejecuta estando **en o junto a un altar**. Cuesta 1 turno y `−6` de recompensa RL.
- Activa **15 turnos** de protección para **toda la cuadrilla**.
- Efectos sobre El Tío: radio de detección a la mitad, solo persigue a distancia `≤ 2`, y **no puede embestir**.
- No se puede ofrendar mientras haya una ofrenda activa.

### 3.4 Batería
- Se gasta por turno según la carga (tabla anterior). Apagar la linterna gasta la mitad.
- La **estación de carburo** recarga al 100 %; cada estación se puede usar **una vez por minero por episodio** (evita farmeo de recompensa).
- Batería en `0 %` = el minero muere en la oscuridad.

### 3.5 El Tío (resumen; detalle en `docs/02` §6)
Demonio gigante que patrulla la zona media-profunda. Oye el ruido de la carga y ve las linternas. Se mueve 1 casilla por turno, y al perseguir puede **embestir** (2 casillas) cada pocos turnos. Un minero ligero casi nunca es alcanzado por detrás; un minero cargado, acorralado o con la salida bloqueada, sí.

## 4. Fin del episodio y puntuación
Un minero **sale del tablero** al ser atrapado, al morir sin batería o al cruzar la Bocamina. El episodio termina cuando **todos** salieron o se alcanzan `max_steps = 300` turnos (truncamiento).

### Puntuación en Bs (visible, por minero)
`Bs = 500 × plata_entregada + 1.200 × oro_entregado + 500 (si sobrevive) − 2 × turno_de_salida`

Un minero atrapado o sin batería pierde su botín y puntúa `0`.

### Puntuación del Tío (modo "Ser El Tío")
`1.000 por captura + valor en Bs del botín perdido por los mineros atrapados + 300 por minero que muere sin batería`.

## 5. Dificultades
Presets definidos en `config.py`. Los cerebros se entrenan en **Normal**; el manifiesto de cada cerebro guarda el hash de configuración y el juego avisa si se usa en otra dificultad.

| Parámetro | Fácil | Normal | Pesadilla |
| :--- | :---: | :---: | :---: |
| Duración de la ofrenda (turnos) | 20 | 15 | 12 |
| Enfriamiento de la embestida (turnos) | 8 | 5 | 3 |
| Multiplicador de consumo de batería | 0,8 | 1,0 | 1,25 |
| Radio de ruido (+) | −1 | 0 | +1 |

## 6. Texto de la leyenda (pantalla "¿Cómo se juega?")
Redactar en español, tono sobrio, sin gráficas. Secciones: **La leyenda**, **Tu objetivo**, **La avaricia pesa**, **La ofrenda protege**, **Cómo piensa El Tío**, **Controles de cada modo**, **¿Quién juega por la IA?** (explicación en una frase: "Los mineros de la IA aprendieron por prueba y error, miles de expediciones, a decidir cuándo ofrendar, cuándo soltar carga y cuándo volver").
