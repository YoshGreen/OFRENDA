# Decisiones de Diseño — El Tío de la Mina

Registro de decisiones tomadas ante ambigüedad o contradicción en la documentación.

---

## [2026-11-26] Fase 0-1 — Fundación y Entorno MDP

### D-01: Vetas de plata en zona media solamente

**Problema:** El MAPA_BASE original incluía vetas de plata en filas 21 (zona profunda). La especificación `docs/01 §2` define zona media como filas 8-15 para plata.

**Decisión:** Eliminar todas las vetas de plata de zona profunda. Añadir 2 vetas de plata en fila 15 (zona media) para cumplir el mínimo de 6 requerido.

**Justificación:** Cumplir estrictamente la restricción geográfica del documento. La fila 15 es la última de zona media y tiene un pasillo ancho disponible.

---

### D-02: Lógica de escape — flag `en_bocamina_inicio`

**Problema:** Al inicio de cada episodio, todos los mineros se spawnan en la Bocamina. Sin ningún control, el primer `step()` los haría escapar inmediatamente (con recompensa `ESCAPAR_VACIO = −10`).

**Decisión:** Añadir el campo `en_bocamina_inicio: bool = True` en `EstadoMinero`. Se pone en `False` la primera vez que el minero se mueve (en `_accion_rumbo`). El escape solo ocurre si el minero llega a bocamina con `en_bocamina_inicio = False`.

**Justificación:** La opción más simple que preserva la intención del diseño sin modificar el orden del turno.

---

### D-03: Decremento de ofrenda en el mismo turno de activación

**Problema:** `docs/01 §3.3` dice que la ofrenda "activa 15 turnos de protección" pero no especifica si el turno de activación cuenta como uno de los 15.

**Decisión:** La ofrenda se activa con `ofrenda_turnos = duracion` en el paso 2 (ejecución de acciones) y se decrementa en el paso 4 (el mismo turno). Al final del turno de activación, `ofrenda_turnos = duracion - 1`.

**Justificación:** El turno de activación cuesta acción + penalización, por lo que es razonable que ya consuma 1 turno de protección. Los tests verifican este comportamiento.

---

### D-04: `TURNO_NORMAL` solo para mineros activos

**Problema:** ¿Se aplica la penalización `−1` por turno a mineros que escaparon o murieron en este mismo turno?

**Decisión:** La penalización de turno (`TURNO_NORMAL = −1`) se aplica **solo** a los mineros que siguen activos (`vivo=True` y `escapado=False`) al final del paso 7.

**Justificación:** Un minero que muere o escapa ya recibió su recompensa final (CAPTURADO/SIN_BATERIA/ESCAPAR). Sumar además `TURNO_NORMAL` duplicaría la penalización de forma injusta.

---

### D-05: Generador de mapas por semilla — permutación de vetas

**Problema:** `docs/01 §2` pide un `generar(seed)` que respete las mismas restricciones del mapa base.

**Decisión:** El generador parte del `MAPA_BASE`, limpia las vetas (plata y oro), y las redistribuye aleatoriamente dentro de sus zonas geográficas correctas (plata en filas 8-15, oro en filas 16-23), respetando mínimos. La estructura de paredes, bocamina, altares y estaciones es invariante.

**Justificación:** Garantiza conectividad (la estructura de paredes no cambia) y cumple todas las restricciones sin necesidad de un generador procedural completo. Suficiente para los experimentos de generalización de la Fase 9.

---
