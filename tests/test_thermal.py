import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from thermal_fea_simulator import ThermalFEA


def test_no_heat_is_ambient():
    fea = ThermalFEA(200.0, resolution=24, thickness_mm=1.0)
    fea.set_boundary_conditions(25.0, "convective")
    T = fea.solve_steady_state()
    on = T[fea.mask]
    assert np.isfinite(on).all()
    np.testing.assert_allclose(on, 25.0, atol=1e-8)


def test_heat_raises_temperature():
    fea = ThermalFEA(200.0, resolution=32, thickness_mm=1.0)
    fea.add_heat_source(0, 0, 20)
    fea.set_boundary_conditions(-10.0, "convective")
    T = fea.solve_steady_state()
    on = T[fea.mask]
    assert np.isfinite(on).all()
    assert on.min() >= -10.0 - 1e-8
    assert on.max() > on.min() + 0.1


def test_missing_boundary_raises():
    fea = ThermalFEA(100.0, resolution=16)
    try:
        fea.solve_steady_state()
    except RuntimeError as exc:
        assert "set_boundary_conditions" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_paths_are_relative():
    root = Path(__file__).resolve().parents[1]
    for name in ("thermal_fea_simulator.py", "fractal_pattern_generator.py"):
        src = (root / name).read_text(encoding="utf-8")
        assert "/home/claude" not in src
