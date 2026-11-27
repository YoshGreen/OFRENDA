"""
backend/bitacora.py — RunLogger: registra corridas de entrenamiento en bitacora/.

Esqueleto de Fase 0 (manifiesto + CSV mínimos).
La versión completa se implementa en Fase 2.

Estructura de salida:
    bitacora/runs/<run_id>/
        manifest.json   — metadatos de la corrida
        metricas.csv    — recompensa por episodio (cabecera + filas)
        (Fase 2 agrega: eval.csv, summary.json, chart_specs.json)
    bitacora/index.json — índice de todas las corridas
"""
from __future__ import annotations

import csv
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

RAIZ_BITACORA = Path(__file__).resolve().parent.parent / "bitacora" / "runs"


class RunLogger:
    """
    Registra una corrida de entrenamiento.

    Uso mínimo (Fase 0):
        logger = RunLogger(nombre="prueba", algoritmo="q_learning", config_hash="abc123")
        logger.iniciar()
        logger.registrar_episodio(ep=1, recompensa=-42.0, pasos=120)
        logger.finalizar()
    """

    def __init__(
        self,
        nombre: str,
        algoritmo: str,
        config_hash: str,
        notas: str = "",
        dificultad: str = "normal",
        hiperparametros: dict[str, Any] | None = None,
    ) -> None:
        self.run_id: str = f"{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        self.nombre = nombre
        self.algoritmo = algoritmo
        self.config_hash = config_hash
        self.notas = notas
        self.dificultad = dificultad
        self.hiperparametros: dict[str, Any] = hiperparametros or {}

        self._ruta: Path = RAIZ_BITACORA / self.run_id
        self._t_inicio: float = 0.0
        self._episodios: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        """Crea el directorio y escribe el manifiesto inicial."""
        self._ruta.mkdir(parents=True, exist_ok=True)
        self._t_inicio = time.monotonic()
        self._escribir_manifiesto(estado="en_progreso", duracion_s=None)
        # Cabecera del CSV
        with self._csv_path().open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["episodio", "recompensa_total", "pasos", "escapados", "atrapados"])
        self._actualizar_indice()

    def registrar_episodio(
        self,
        ep: int,
        recompensa: float,
        pasos: int,
        escapados: int = 0,
        atrapados: int = 0,
    ) -> None:
        """Añade una fila al CSV de métricas."""
        self._episodios.append({
            "ep": ep,
            "recompensa": recompensa,
            "pasos": pasos,
            "escapados": escapados,
            "atrapados": atrapados,
        })
        with self._csv_path().open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([ep, recompensa, pasos, escapados, atrapados])

    def finalizar(self, mejor_recompensa: float | None = None) -> None:
        """Cierra la corrida y actualiza el manifiesto con duración real."""
        duracion = time.monotonic() - self._t_inicio
        self._escribir_manifiesto(
            estado="completado",
            duracion_s=round(duracion, 2),
            mejor_recompensa=mejor_recompensa,
        )
        self._actualizar_indice()

    # ------------------------------------------------------------------
    # Propiedades de ruta
    # ------------------------------------------------------------------

    def ruta(self) -> Path:
        """Ruta al directorio de la corrida."""
        return self._ruta

    def _csv_path(self) -> Path:
        return self._ruta / "metricas.csv"

    # ------------------------------------------------------------------
    # Escritura interna
    # ------------------------------------------------------------------

    def _escribir_manifiesto(
        self,
        estado: str,
        duracion_s: float | None,
        mejor_recompensa: float | None = None,
    ) -> None:
        manifiesto: dict[str, Any] = {
            "run_id": self.run_id,
            "nombre": self.nombre,
            "algoritmo": self.algoritmo,
            "config_hash": self.config_hash,
            "dificultad": self.dificultad,
            "notas": self.notas,
            "hiperparametros": self.hiperparametros,
            "fecha_inicio": datetime.now().isoformat(),
            "estado": estado,
            "duracion_s": duracion_s,
            "n_episodios_registrados": len(self._episodios),
            "mejor_recompensa": mejor_recompensa,
        }
        ruta_manifest = self._ruta / "manifest.json"
        ruta_manifest.write_text(
            json.dumps(manifiesto, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _actualizar_indice(self) -> None:
        """Actualiza bitacora/index.json con esta corrida."""
        indice_path = RAIZ_BITACORA.parent / "index.json"
        indice: list[dict[str, Any]] = []
        if indice_path.exists():
            try:
                indice = json.loads(indice_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                indice = []

        # Actualizar o insertar
        entrada = {
            "run_id": self.run_id,
            "nombre": self.nombre,
            "algoritmo": self.algoritmo,
            "config_hash": self.config_hash,
            "dificultad": self.dificultad,
        }
        ids_existentes = {e["run_id"] for e in indice}
        if self.run_id not in ids_existentes:
            indice.append(entrada)
        else:
            for e in indice:
                if e["run_id"] == self.run_id:
                    e.update(entrada)

        RAIZ_BITACORA.parent.mkdir(parents=True, exist_ok=True)
        indice_path.write_text(
            json.dumps(indice, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
