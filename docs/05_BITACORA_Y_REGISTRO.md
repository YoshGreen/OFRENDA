# 05 — Bitácora y Registro de Experimentos

## 1. Propósito
Todo lo que se hace y se mide en el proyecto queda registrado en `bitacora/`, **fuera del juego**, para alimentar otro dashboard y para documentar el proceso académico. El frontend del juego nunca importa, sirve ni muestra estos archivos.

Hay tres tipos de registro:
1. **Corridas de entrenamiento** (automático, lo escribe `RunLogger`).
2. **Diario de desarrollo** (pasos del proyecto, lo escriben los agentes y tú).
3. **Decisiones** (por qué se eligió algo).

## 2. Estructura
```text
bitacora/
├── index.jsonl                  # catálogo append-only: una línea por corrida
├── DIARIO_DESARROLLO.md         # bitácora cronológica de trabajo
├── DECISIONES.md                # registro de decisiones (ADR corto)
├── schemas/                     # JSON Schema de manifest, métricas, charts
└── runs/
    └── <run_id>/                # p. ej. 20261127T153012_qlearning_g095_a010_s42
        ├── run_manifest.json
        ├── metrics_episodes.csv
        ├── metrics_summary.json
        ├── eval_results.json
        ├── charts_manifest.json
        ├── chart_specs/         # *.vl.json (Vega-Lite v5)
        ├── sample_episodes/     # replays: first, best, worst, last (.jsonl)
        └── notes.md             # notas humanas (plantilla autogenerada)
```
El cerebro entrenado se guarda aparte en `backend/models/<brain_id>/` y se enlaza por `run_id`. Archivos grandes (`sample_episodes` extensos) pueden ir a `.gitignore`; el resto se versiona.

## 3. `run_id`
`<YYYYMMDDTHHMMSS>_<algoritmo>_g<gamma sin punto>_a<alpha sin punto>_s<seed>` (hora local).

## 4. `run_manifest.json`
```json
{
  "schema_version": 1,
  "run_id": "20261127T153012_qlearning_g095_a010_s42",
  "name": "audaz",
  "created_at": "2026-11-27T15:30:12-04:00",
  "algorithm": "q_learning",
  "hyperparameters": {"alpha": 0.1, "gamma": 0.95, "epsilon_start": 1.0, "epsilon_min": 0.05, "decay_fraction": 0.6, "episodes": 5000, "num_miners": 3},
  "environment": {"map": "MAPA_BASE", "map_seed": null, "difficulty": "normal", "max_steps": 300, "reward_table": {"...": "copia completa de las recompensas"}},
  "config_hash": "sha256:…",
  "seed": 42,
  "state_space": 5184,
  "action_space": 7,
  "runtime": {"python": "3.11.x", "numpy": "x.y.z", "os": "…", "cpu": "…", "git_commit": "abc1234", "git_dirty": false},
  "duration_seconds": 0.0,
  "steps_total": 0,
  "checkpoints": ["q_ep0.npy", "q_ep100.npy", "q_ep500.npy", "q_ep1500.npy", "q_ep5000.npy"],
  "brain_dir": "backend/models/audaz",
  "notes": "texto libre pasado por --notes",
  "command": "python -m backend.train ..."
}
```

## 5. `metrics_episodes.csv`
Una fila por episodio de entrenamiento:

| Columna | Descripción |
| :--- | :--- |
| `episode` | 0..N-1 |
| `epsilon` | Valor de `ε` usado |
| `steps` | Turnos del episodio |
| `reward_total` | Suma de recompensa RL de todos los mineros |
| `reward_mean_per_miner` | Promedio por minero |
| `mean_abs_td` | Media de `|δ|` en el episodio |
| `escapes` / `escape_rate` | Mineros que escaparon / proporción |
| `deaths_capture` / `deaths_battery` / `deaths_greed` | Bajas por causa (*greed* = atrapado con `nivel_carga ≥ 2`) |
| `timeouts` | Mineros que seguían en la mina al truncar |
| `bs_total` | Puntuación total en Bs |
| `gold_delivered` / `silver_delivered` | Unidades entregadas |
| `offerings` | Ofrendas realizadas |
| `invalid_actions` | Acciones inválidas |
| `tio_aggressiveness` | Multiplicador aleatorizado del episodio |
| `wall_ms` | Tiempo de pared del episodio |

## 6. `eval_results.json`
Lista de evaluaciones (cada `eval_every`): `{ "episode", "mode": "greedy|eps0.1", "n_episodes", "seed_range", "escape_rate", "bs_mean", "bs_std", "offerings_mean", "deaths_by_cause", "gold_mean" }`. Los intervalos de confianza se calculan por *bootstrap* y se guardan (`ci95_low`, `ci95_high`).

## 7. `metrics_summary.json`
Resumen final: mejor evaluación, medias de los últimos 500 episodios, episodio de primera tasa de escape ≥ 50 % y ≥ 80 %, tiempo total, pasos/segundo, tamaño de la Tabla Q, estados visitados (% de `5184`), pares `(s,a)` actualizados.

## 8. Parámetros de gráficas (`chart_specs/`)
No se dibuja nada en el juego. Cada gráfica se **describe** como JSON **Vega-Lite v5** para que tu otro dashboard (o cualquier visor) la renderice. Los datos se referencian por ruta relativa.

`charts_manifest.json`:
```json
{
  "run_id": "…",
  "palette": {"politica_exito": "#00FF88", "valor_info": "#4DB8FF", "peligro": "#FF3B3B", "oro": "#FFD700", "plata": "#C8D6E5"},
  "charts": [
    {"id": "recompensa", "titulo": "Recompensa promedio por minero", "archivo": "chart_specs/recompensa.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "escape", "titulo": "Tasa de escape", "archivo": "chart_specs/escape.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "td", "titulo": "Error TD medio |δ|", "archivo": "chart_specs/td.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "epsilon", "titulo": "Exploración ε", "archivo": "chart_specs/epsilon.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "muertes", "titulo": "Bajas por causa", "archivo": "chart_specs/muertes.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "ofrendas", "titulo": "Ofrendas por episodio", "archivo": "chart_specs/ofrendas.vl.json", "fuente": "metrics_episodes.csv"},
    {"id": "evaluacion", "titulo": "Evaluación (greedy vs ε=0,1)", "archivo": "chart_specs/evaluacion.vl.json", "fuente": "eval_results.json"}
  ]
}
```
Ejemplo `chart_specs/escape.vl.json`:
```json
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "title": "Tasa de escape (media móvil de 100 episodios)",
  "data": {"url": "../metrics_episodes.csv"},
  "transform": [{"window": [{"op": "mean", "field": "escape_rate", "as": "escape_ma"}], "frame": [-99, 0]}],
  "mark": {"type": "line", "color": "#00FF88"},
  "encoding": {
    "x": {"field": "episode", "type": "quantitative", "title": "Episodio"},
    "y": {"field": "escape_ma", "type": "quantitative", "title": "Tasa de escape", "scale": {"domain": [0, 1]}}
  },
  "usermeta": {"run_id": "…", "ventana_suavizado": 100, "descripcion": "…", "generado_por": "bitacora.py"}
}
```
Además existen specs **comparativos** (varias corridas) generados por `tools/experimentos.py` en `bitacora/comparativas/<id>/` (Q-Learning vs SARSA, `γ=0,2` vs `0,95`, con/sin altares, generalización a mapas no vistos).

## 9. `index.jsonl`
Una línea por corrida: `{"run_id", "created_at", "name", "algorithm", "gamma", "alpha", "episodes", "seed", "final_escape_rate", "best_eval_escape_rate", "duration_seconds", "path"}`. Se escribe con *append* atómico (`fsync`).

## 10. `RunLogger` (`backend/bitacora.py`)
```python
logger = RunLogger(config, name, notes)     # crea carpeta, manifiesto inicial, hash de config
logger.log_episode(dict)                    # fila CSV (buffer + flush periódico)
logger.log_eval(dict)
logger.save_sample_episode(tag, frames)     # first | best | worst | last
logger.finish(summary)                      # resumen, chart_specs, charts_manifest, index.jsonl, notes.md
```
Requisitos: no debe ralentizar el entrenamiento más de un 3 %; si el proceso se interrumpe, el manifiesto indica `status: "interrumpida"` y conserva lo escrito (`try/finally`, `atexit`).

## 11. Diario de desarrollo (`bitacora/DIARIO_DESARROLLO.md`)
Se agrega con `python tools/diario.py add ...`. Formato de cada entrada:
```markdown
## 2026-11-27 16:40 — Fase 2: Agentes RL tabulares
- **Agente/herramienta:** Claude Code
- **Qué se hizo:** …
- **Decisiones:** … (ver DECISIONES.md #004)
- **Comandos y resultados:** `pytest -v` → 31 passed; entrenamiento 5.000 ep en 47 s
- **Corridas relacionadas:** run_id …
- **Problemas / bloqueos:** …
- **Pendiente / traspaso:** …
```
Todo agente **debe** leer las últimas 3 entradas al empezar y añadir una al terminar.

## 12. Decisiones (`bitacora/DECISIONES.md`)
Entradas numeradas: contexto, opciones, decisión, consecuencias. Obligatorio registrar: umbrales de pruebas, valores de recompensa cambiados, resolución de ambigüedades de la documentación.

## 13. Herramientas
- `tools/diario.py add|list|last`.
- `tools/experimentos.py`: lotes reproducibles (ablaciones: `γ`, con/sin ofrenda, Q vs SARSA, shaping on/off, 5 semillas cada una), escribe corridas y comparativas.
- `tools/exportar_corrida.py <run_id>`: crea `bitacora/export/<run_id>.zip` con manifiesto, métricas, specs y replays para el dashboard externo.

## 14. Criterios de aceptación
- [ ] Una corrida de 200 episodios crea todos los archivos de §2 y valida contra `schemas/`.
- [ ] Las specs Vega-Lite abren sin errores en el editor online de Vega-Lite.
- [ ] El manifiesto permite **reproducir** la corrida exactamente con su `command` y `seed`.
- [ ] `grep` no encuentra referencias a `bitacora/` en `frontend/`.
