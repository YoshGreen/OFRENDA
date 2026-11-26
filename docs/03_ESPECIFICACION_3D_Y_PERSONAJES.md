# 03 — Especificación 3D, Personajes y Atmósfera (`frontend/`)

## 1. Dirección de arte
Terror claustrofóbico de mina, personajes estilizados y expresivos (inspiración visual: *R.E.P.O.*, solo referencia estética). Oscuridad dominante; la luz cuenta la historia.

| Uso | Hex |
| :--- | :---: |
| Fondo / oscuridad | `#000000` |
| Roca | `#1a1714` a `#2b2520` |
| Madera de vigas | `#3b2a1a` |
| Peligro / El Tío (ojos, brasas) | `#FF1E1E` |
| Oro | `#FFD700` |
| Plata | `#C8D6E5` |
| Altar / velas | `#FF8C00` |
| Bocamina (luz exterior) | `#88CCFF` |
| Mineros | `#F4C430` (1), `#38BDF8` (2), `#FB923C` (3), `#A78BFA` (4, modo Duelo) |

## 2. Escala y mundo
- `TILE_SIZE = 2.0 m`. `(fila, col) → (x = col·2, z = fila·2)`.
- **`WALL_HEIGHT = 4.2 m`** (el túnel debe acomodar a El Tío de 3,6 m; sus cuernos rozan el techo cuando se yergue).
- Mineros: 1,7 m. **El Tío: 3,6 m** (más de dos veces el tamaño de un minero).
- Cámara en primera persona: minero a 1,55 m, Tío a 3,2 m.

### Escenario (`world/mina_3d.js`)
- Paredes con **un `InstancedMesh`**, geometría de cubo con ligero bisel y textura procedural de roca (`CanvasTexture`, normal map sintético). Techo y suelo por planos instanciados; el suelo con variación de rugosidad.
- Vigas de madera cada 3–4 celdas en pasillos rectos (instanciadas). Rieles, cuerdas, charcos con reflejo barato (planos con `roughness` baja), telarañas y polvo en suspensión (partículas `Points`).
- **Bocamina:** arco de madera con luz fría `#88CCFF` y rayos volumétricos falsos (planos aditivos). Es el faro visual del escape.
- **Altares:** pedestal de piedra, figurita roja del Tío, velas con llama animada (sprite aditivo) y `PointLight` naranja con parpadeo (`sin` + ruido). Al ofrendar: humo de cigarro, hojas de coca y gotas de alcohol (partículas), y el altar brilla durante la ofrenda activa.
- **Vetas:** cúmulos de cristales (octaedros/prismas) con material `emissive`; brillo pulsante y destellos. Al ser picadas, se rompen en fragmentos que desaparecen.
- **Estación de carburo:** farol colgante con llama azul-verdosa y silbido de gas.
- **Niebla:** `FogExp2(0x000000, 0.075)` en primera persona; `0.02` en panorámica. Ambiental `0x11131a` a `0.25` (FP) y `0.8` (panorámica).

### Luces y rendimiento
- Máximo **8 luces dinámicas activas**: linternas (`SpotLight`) de mineros vivos, luz roja del Tío, y altares/estaciones más cercanos a la cámara. El resto usa brillo emisivo falso. Sombras solo en la linterna del minero observado y, en calidad Alta, en la del Tío.
- Presets de calidad (Opciones): **Baja** (sin postproceso, sin sombras, partículas mínimas), **Media** (viñeta, grano ligero), **Alta** (bloom en ojos/cristales/llamas, sombras de linterna, partículas completas). Objetivo: 60 FPS en Media.
- Sin asignaciones en el bucle de render; reutilizar vectores/cuaterniones; `dispose()` al salir de partida.

## 3. Mineros: modelo y animación

### 3.1 Modelo procedural (`actors/minero_rig.js`)
Rig jerárquico de `THREE.Group` (sin esqueleto/skinning):
```text
raíz
└─ caderas (y=0,95)
   ├─ torso (pivote en cintura)
   │   ├─ cabeza (cuello) → casco + faro + SpotLight; ojos grandes con pupilas (sello R.E.P.O.)
   │   ├─ brazo_izq (pivote hombro) → antebrazo → mano
   │   ├─ brazo_der (pivote hombro) → antebrazo → mano (pico/lámpara)
   │   └─ mochila / saco de botín (visible según carga)
   ├─ muslo_izq → pantorrilla → bota
   └─ muslo_der → pantorrilla → bota
```
Geometría: cápsulas, cilindros y esferas; `flatShading` suave; traje del color del minero; chaleco reflectante; botas oscuras. Pupilas rotan hacia El Tío cuando está cerca.

### 3.2 Ciclo de caminar (que realmente parezca caminar)
- **La fase avanza por distancia recorrida, no por tiempo:** `fase += (Δdistancia / longitud_zancada) · 2π`. Así los pies no patinan, y si el minero va lento, camina lento.
- `longitud_zancada = 1,1 m` (ligero), `0,8 m` (pesado), `0,6 m` (avaricioso).
- Piernas: balanceo de muslo `±35°` (ligero) a `±18°` (avaricioso); la pantorrilla flexiona solo en la fase de elevación (`max(0, sin(fase+φ))`); la bota se mantiene plana al apoyar.
- Brazos en contrafase a las piernas, `±25°`; con carga, un brazo sostiene el saco y casi no balancea.
- Rebote vertical de caderas `0,04 m` (ligero) y `0,08 m` (pesado) con doble frecuencia; balanceo lateral leve del torso y contrarrotación de la cabeza para estabilizar la mirada; la linterna oscila con retraso (resorte amortiguado).
- **Inclinación del torso por carga:** `0°, 8°, 20°, 35°` con interpolación suave. Con carga 3, rodillas flexionadas y arrastre de pies, y aro rojo pulsante en el suelo (ruido alto).
- **Duración visual del movimiento:** el servidor envía `visual_ticks`; el rig interpola de la celda origen a la destino durante `visual_ticks × tick_ms`, de modo que un minero pesado se **ve** avanzando despacio.
- **Giro:** `yaw` con `slerp` y velocidad angular limitada; el cuerpo gira tras la cabeza (la cabeza anticipa).
- **Mezcla de estados** por pesos (idle ↔ caminar ↔ cargado) con `lerp` de amplitudes; nunca cambios bruscos de pose. Idle: respiración, parpadeo y mirada que recorre el túnel.

### 3.3 Animaciones de evento (`actors/animacion.js`)
| Evento | Animación |
| :--- | :--- |
| `picó` | Golpes de pico (2–3), chispas y fragmentos de cristal |
| `ofrendó` | Se arrodilla, vierte alcohol, enciende cigarro, deja coca; murmullo |
| `soltó` | Se quita el saco, lo deja caer con rebote |
| linterna apagada | Se agacha, luz se extingue con un último parpadeo |
| Tío cerca (`dist_tio ≥ 2`) | Ojos muy abiertos, pupilas hacia El Tío, respiración agitada, paso nervioso, linterna temblando |
| `atrapado` | El Tío lo levanta/golpea, la linterna rueda por el suelo y se apaga |
| `sin_batería` | La luz agoniza, cae de rodillas |
| `escapó` | Corre hacia la luz azul, silueta recortada, desaparece |

## 4. El Tío: demonio gigante

### 4.1 Aspecto (`actors/tio_rig.js`)
Objetivo: **imponente, grotesco, aterrador**, y a la vez reconocible como El Tío de la tradición minera (figura roja con cuernos y cigarro).
- **Altura 3,6 m**, postura encorvada que se yergue a 4,0 m al rugir; hombros anchos, torso musculoso, brazos largos que casi tocan el suelo y manos con garras de 25 cm.
- **Cabeza:** cráneo alargado, mandíbula prominente con **dientes irregulares afilados** (geometría de conos), boca en rictus permanente; **cuernos grandes y curvos** de ~1,1 m (`TubeGeometry` sobre `CatmullRomCurve3`, radio decreciente, material hueso agrietado con borde rojo). Pómulos marcados y cejas bajas.
- **Ojos:** dos puntos `emissive` `#FF1E1E` con bloom, visibles a decenas de metros entre la niebla; destellan al detectar.
- **Cigarro:** un puro grueso entre los dientes con **brasa naranja** que pulsa y emite humo (guiño a la ch'alla).
- **Piel y vestimenta:** carbón rojizo oscuro con rim light rojo; capa/harapos a modo de tela flotante con simulación simple de oscilación (`sin` por segmento); collar de hojas de coca y serpentinas secas.
- **Piernas digitígradas** de macho cabrío con **pezuñas** hendidas; **cola** larga serpenteante.
- Humo/vapor rojizo que se desprende del cuerpo (partículas lentas).
- Material con `flatShading`, rugosidad alta y emisivo sutil en venas/grietas para silueta legible a oscuras. Presupuesto de polígonos: ≤ 30.000 triángulos (solo hay una instancia).

### 4.2 Animación
- **Caminar pesado:** zancada larga y lenta, cada pisada con descenso de caderas, balanceo de brazos, cuernos y cabeza que giran como olfateando; cola y capa con retardo. Cada pisada dispara un **evento de pisada** (sacudida de cámara proporcional a la cercanía, polvo, vibración de luces cercanas y sonido grave).
- **Patrullando:** cabeza baja, ojos que barren; respiración audible.
- **Alertado:** se detiene, **rugido** (se yergue, cabeza atrás, boca abierta, destello de ojos, las linternas de los mineros cercanos parpadean), y luego olfatea hacia la última posición percibida.
- **Persiguiendo:** baja el torso, brazos hacia adelante, paso acelerado, ojos intensos, aura roja más fuerte.
- **Embestida:** pose de carga, estela de polvo y brasas, sonido de cuerno y pisadas aceleradas.
- **Ofrenda activa:** El Tío se encoge ligeramente, mira el altar, baja la agresividad visual; el aura disminuye. (La mecánica ya lo refleja; la animación lo hace legible.)
- **Captura:** agarra al minero, lo alza y lo azota o devora en cámara oscura; la pantalla "respira" en rojo.

### 4.3 Sistema de terror (efectos ligados a la cercanía)
Calculado en el frontend a partir de la distancia visual al Tío, para la cámara activa:
- **Sacudida de cámara** y *head-bob* más rápido; viñeta roja creciente; leve aberración cromática en calidad Alta.
- **Latido** (audio procedural) cuya frecuencia crece al acercarse; respiración del Tío; silencio repentino antes de un susto.
- **Parpadeo y caída de linternas** cuando el Tío ruge.
- **Silueta lejana:** los ojos rojos aparecen y desaparecen en la niebla; susurros y risa grave direccionales (`PannerNode`).
- Ningún *jump scare* gratuito: el miedo debe nacer de lo que la IA o el jugador están decidiendo.

## 5. Interpolación Cuadrícula → 3D
- Posición y `yaw` objetivo = celda del frame más reciente. Duración de interpolación = `visual_ticks × tick_ms` (minero) o `1 tick` (Tío; la embestida usa un ease-in rápido).
- La velocidad de reproducción (`speed`) acelera animaciones de forma proporcional y limita `visual_ticks` para que a 8x no haya saltos.
- Si llegan frames atrasados, se **descarta el exceso** y se salta al último estado sin teletransportes visibles (se acelera la interpolación).

## 6. Cámaras (`camera/cameras.js`, `camera/director.js`)
| Tecla | Cámara |
| :---: | :--- |
| `0` | Panorámica elevada con `OrbitControls` (zoom/rotación), luz general, niebla reducida |
| `1`–`3` (`4` en Duelo) | Primera persona del minero N, con *head-bob*, niebla densa y linterna real |
| `T` | Primera persona de El Tío |
| `Tab` | Siguiente agente vivo |
| `C` | **Director automático:** cambia al agente en mayor tensión (Tío cerca, ofrendando, a punto de escapar), con cortes suaves y mínimo 6 s por plano |

Si el agente observado muere o escapa: aviso limpio y salto suave al siguiente agente vivo o a la panorámica; nunca rompe la cámara.

## 7. Audio procedural (`audio/audio_procedural.js`)
Sin archivos externos: ambiente de cueva (ruido filtrado + goteo), eco de pasos (más lentos y graves con carga), picos sobre roca, crepitar de velas, cigarro, rugido del Tío (osciladores + ruido modulado + distorsión), pisadas graves, latido, susurros, silbido del carburo, campanilla al escapar. Volúmenes separados (música/efectos/ambiente) y un solo `AudioContext` iniciado tras la primera interacción del usuario.

## 8. HUD de juego (único permitido)
Batería y carga del minero observado/controlado, puntaje en Bs, ofrenda restante como **vela que se consume** (no número en gráfica), turno, aviso de teclas contextuales (`E` ofrendar junto al altar) y mensajes breves ("Minero 2 escapó"). Todo con estilo de linterna/papel gastado. **Ninguna gráfica, Q-value ni indicador de IA.**

## 9. Lista de verificación visual (QA de la Fase 5–8)
- [ ] Los pies no patinan; la cadencia coincide con la velocidad real.
- [ ] Un minero con carga 3 se ve y suena claramente más lento y pesado.
- [ ] El Tío se percibe como más del doble de alto que un minero y roza el techo al rugir.
- [ ] Sus ojos y su brasa se ven a 15+ celdas en la niebla.
- [ ] Las pisadas del Tío sacuden la cámara de forma proporcional.
- [ ] Cambiar de cámara no produce saltos ni errores en consola.
- [ ] 60 FPS en preset Media con 3 mineros + Tío + 3 altares.
