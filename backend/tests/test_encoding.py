"""
tests/test_encoding.py — Prueba codificación de estado (docs/02 §2.1).

Verifica:
- encode_state/decode_state ida y vuelta.
- Rango [0, 5183].
- Todos los índices son únicos.
"""
import pytest
from backend.mina_env import decode_state, encode_state
from backend.config import STATE_DIMS, N_ESTADOS


def _todos_los_estados():
    """Genera todos los 5184 estados posibles."""
    dims = STATE_DIMS  # (4,3,2,4,3,2,3,3)
    dist_tio_vals       = range(dims[0])
    tio_lado_vals       = range(dims[1])
    ofrenda_vals        = range(dims[2])
    nivel_carga_vals    = range(dims[3])
    bateria_vals        = range(dims[4])
    altar_vals          = range(dims[5])
    dist_boc_vals       = range(dims[6])
    botin_vals          = range(dims[7])

    estados = []
    for dt in dist_tio_vals:
        for tl in tio_lado_vals:
            for oa in ofrenda_vals:
                for nc in nivel_carga_vals:
                    for b in bateria_vals:
                        for ac in altar_vals:
                            for db in dist_boc_vals:
                                for bd in botin_vals:
                                    estados.append((dt, tl, oa, nc, b, ac, db, bd))
    return estados


class TestEncode:
    def test_n_estados_total(self):
        """El producto de dimensiones debe ser 5184."""
        assert N_ESTADOS == 5184

    def test_rango_completo(self):
        """Todos los índices están en [0, 5183]."""
        estados = _todos_los_estados()
        indices = set()
        for args in estados:
            idx = encode_state(*args)
            assert 0 <= idx <= 5183, f"Índice fuera de rango: {idx} para {args}"
            indices.add(idx)
        assert len(indices) == 5184, f"Solo {len(indices)} índices únicos"

    def test_ida_vuelta(self):
        """encode ∘ decode y decode ∘ encode son identidades."""
        estados = _todos_los_estados()
        for args in estados:
            idx = encode_state(*args)
            dec = decode_state(idx)
            assert dec == args, (
                f"Fallo ida-vuelta: encode({args}) = {idx}, decode({idx}) = {dec}"
            )

    def test_casos_borde(self):
        """El estado (0,0,0,0,0,0,0,0) → 0 y el máximo → 5183."""
        idx_min = encode_state(0, 0, 0, 0, 0, 0, 0, 0)
        assert idx_min == 0
        idx_max = encode_state(3, 2, 1, 3, 2, 1, 2, 2)
        assert idx_max == 5183

    def test_decode_rango_completo(self):
        """Todos los índices 0..5183 son decodificables sin excepción."""
        for idx in range(N_ESTADOS):
            vals = decode_state(idx)
            assert len(vals) == 8
            dims = STATE_DIMS
            for v, d in zip(vals, dims):
                assert 0 <= v < d, f"Valor {v} fuera de rango dim {d} para idx {idx}"
