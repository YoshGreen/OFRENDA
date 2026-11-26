# 04 — Menú y Modos de Juego

## 1. Flujo de pantallas (`frontend/js/screens/`)
```text
Carga → Menú principal ─┬─ Jugar → Selección de modo → Configuración → Partida → Pausa ↔ Partida → Informe de la expedición
                        ├─ ¿Cómo se juega?
                        ├─ Opciones (calidad, audio, sensibilidad, controles)
                        └─ Acerca del proyecto
```
- **Menú principal:** título "EL TÍO DE LA MINA" sobre un fondo 3D vivo (cámara lenta por un túnel, linterna que parpadea, ojos rojos que aparecen y desaparecen). Música ambiental y sonido de goteo.
- **¿Cómo se juega?:** pantalla de paneles ilustrados con la leyenda, el objetivo, la avaricia, la ofrenda, cómo piensa El Tío, los controles de cada modo y una explicación breve de la IA (texto en `docs/01` §6). Sin gráficas. Incluye un mini-tutorial opcional de 60 s en la mina (mover, picar, ofrendar, escapar) disponible desde aquí.
- **Opciones:** calidad (Baja/Media/Alta), volúmenes, sensibilidad del mouse, intensidad de sacudidas y efectos de susto (accesibilidad), idioma fijo en español.
- **Pausa:** continuar, reiniciar expedición, opciones, salir al menú.
- **Informe de la expedición:** resumen en texto y números (no gráficas): resultado, turnos, Bs por minero, botín entregado, sobrevivientes, ofrendas, causa de cada baja. Botones: repetir, cambiar de modo, menú.

## 2. Reloj de juego
El motor es discreto pero corre **en tiempo real** con un `tick` fijo (por defecto `450 ms` con humano, ajustable `300–700 ms`). Las entradas del humano se guardan en un buffer de una posición y se ejecutan en el siguiente tick, de modo que la sensación es la de un *dungeon crawler* en tiempo real y no la de un juego por turnos de espera. En modo observador la velocidad es `0,5x – 8x`.

## 3. Modos

### Modo A — Observar la Cuadrilla (solo agentes)
- **Objetivo:** ver cómo deciden los mineros IA en todo el mapa o desde sus ojos.
- **Configuración:** cerebro (Audaz/Q-Learning, Prudente/SARSA), nivel de experiencia (Novato, Aprendiz, Veterano, Experto), 2 o 3 mineros, dificultad, semilla (aleatoria o fija).
- **Cámaras:** `0` panorámica, `1–3` primera persona de cada minero, `T` primera persona del Tío, `Tab` siguiente, `C` director automático. Pausa con `Espacio`, velocidad con `+`/`-`.
- **Uso en la presentación:** cambiar entre Novato y Experto muestra el aprendizaje sin una sola gráfica: el Novato corre a ciegas con las manos llenas de oro y cae; el Experto ofrenda, suelta carga a tiempo y escapa.

### Modo B — Entrar a la Mina (Humano + IA)
- **Objetivo:** sobrevivir y salir con más Bs que los mineros IA.
- **Jugador:** primera persona como Minero 1; los Mineros 2 y 3 los controla el cerebro elegido. La ofrenda protege a todos, también a ti: la cooperación es parte del dilema.
- **Controles (movimiento por cuadrícula, estilo dungeon crawler):**
  | Tecla | Acción |
  | :---: | :--- |
  | `W` | Avanzar una casilla hacia donde miras |
  | `S` | Retroceder una casilla |
  | `A` / `D` | Girar 90° (gratis) |
  | `Mouse` | Mirar libremente ±60° (solo visual) |
  | `E` | Ofrendar (junto a un altar) |
  | `F` | Apagar / encender linterna |
  | `Q` | Soltar carga |
  | `Espacio` | Esperar un turno |
  | `Esc` | Pausa |
- Rige el mismo peso, enfriamiento y ruido que a la IA: cargado, te mueves más lento y no puedes actuar durante la recuperación.
- **Resultado:** ranking de Bs. Ganas si sales con más Bs que cada IA; "Sobreviviente" si sales; "Víctima" si no. Si mueres, la cámara sigue a los demás hasta el final.

### Modo C — Ser El Tío (humano cazador)
- **Objetivo:** que ningún minero escape con botín: atrapar o agotar a más de la mitad de la cuadrilla en 300 turnos.
- **Jugador:** primera persona del demonio (3,2 m de altura de ojos). Los mineros los controla un cerebro **Experto**.
- **Controles:** `W/S/A/D` mover y girar (igual que Modo B), con las siguientes habilidades:
  | Tecla | Habilidad | Efecto | Enfriamiento |
  | :---: | :--- | :--- | :---: |
  | `Shift` | Embestida | Avanza 2–3 casillas; atrapa lo que cruces | Según dificultad |
  | `R` | Rugido | Aturde 1 turno a mineros a ≤ 3 casillas y revela por 4 turnos a los que están a ≤ 8 | 10 turnos |
  | `G` | Oscuridad | Apaga linternas a ≤ 5 casillas durante 3 turnos (la batería se agota el triple de rápido) | 14 turnos |
- **Sentidos del Tío:** ve haces de linterna como columnas de luz a gran distancia con línea de visión; el **ruido** de la carga pesada se muestra como ondas rojas en el suelo. Sin visión a través de paredes salvo con el rugido.
- **Ofrendas:** cuando hay ofrenda activa no puedes embestir y tu rugido y oscuridad se reducen a la mitad de alcance; una vela del altar se ve encendida en tu campo visual (diegético).
- **Puntuación:** `docs/01` §4. Resultado: "La mina tiene hambre" (victoria) o "Escaparon con tu tesoro" (derrota).
- **Nota para el backend:** los cerebros se entrenaron contra la FSM del Tío; el humano es más impredecible, por eso el entrenamiento aleatoriza la agresividad (`docs/02` §4).

### Modo D — Duelo de Cerebros (recomendado como cuarto modo)
- **Objetivo:** dos cuadrillas con **cerebros distintos** (Audaz/Q-Learning vs. Prudente/SARSA) en la **misma mina y con el mismo Tío**; gana la cuadrilla que reúna más Bs.
- 2 mineros por cuadrilla (4 en total), colores distintos, cada cuadrilla con su Tabla Q propia (*parameter sharing* por cerebro). Exige que ambos cerebros compartan el mismo `config_hash`.
- Cámaras como en el Modo A (`1–4`).
- **Valor para la defensa:** comparación directa Q-Learning vs. SARSA, observable en vivo.

### Modos futuros (opcionales, en orden de valor/esfuerzo)
1. **Replay de expediciones:** reproducir en 3D episodios guardados en `bitacora/` (mejor, peor, último), con cámaras libres. Útil para la defensa y para documentar.
2. **Apuesta del espectador:** antes de empezar, el público apuesta "¿quién sale vivo?"; se revela al final. Participativo, sin gráficas.
3. **Desafío por semilla:** misma mina y mismo comportamiento del Tío para todos; compartir la semilla y comparar puntajes.
4. **Supervivencia por niveles:** cada expedición exitosa añade un piso más profundo y un Tío más agresivo.

## 4. Selección de cerebros
El juego lista los cerebros desde `GET /api/brains`. Nombres sugeridos en lenguaje de leyenda: **Cuadrilla Audaz** (Q-Learning) y **Cuadrilla Prudente** (SARSA), cada una con niveles **Novato** (episodio 0), **Aprendiz**, **Veterano** y **Experto**. El menú nunca muestra métricas ni nombres técnicos de hiperparámetros.

## 5. Criterios de aceptación de menú y modos
- [ ] Desde el menú se puede entrar a cada modo y volver sin recargar la página ni dejar fugas de memoria (`dispose()`).
- [ ] "¿Cómo se juega?" cubre todas las mecánicas y los controles de cada modo.
- [ ] En el Modo B las entradas rápidas no se pierden ni se duplican; la recuperación por carga se siente (la entrada se ignora y el HUD lo indica con la animación del minero).
- [ ] En el Modo C las tres habilidades funcionan, respetan enfriamientos y cambian con la ofrenda.
- [ ] En cualquier modo, pausar congela física, animación y audio; reanudar no genera saltos.
- [ ] Ningún modo muestra gráficas, Q-values ni indicadores de IA.
