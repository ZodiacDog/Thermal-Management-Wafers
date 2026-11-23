# Changelog

## Unreleased (audit fixes, 2026-11)

- Fixed the thermal solver. Off-wafer zero rows made the matrix singular
  and the committed `*_results.json` files were all NaN. The system is now
  assembled on on-wafer nodes only, with a Dirichlet edge at ambient.
- Replaced hardcoded `/home/claude/thermal_wafer_project/` paths with
  paths relative to the repository root. Restored `cad_models/`,
  `simulations/`, `documentation/`, and `manufacturing/` folders.
- Regenerated results at 120-point resolution with documented 1.0–1.15 mm
  thicknesses (2026-11-23, America/Chicago):
  - Space Solar: ΔT 4.550°C (250 W, 25–29.550°C)
  - AI Compute: ΔT 86.780°C (1000 W, 25–111.780°C)
  - Quantum: ΔT 0.518°C (15 W, −269–−268.482°C)
- Withdrew the earlier <5°C and <1 mK uniformity claims, which this model
  does not support. Clarified that the code is 2-D finite difference, not
  3-D FEA.
- Removed `pip install --break-system-packages` from the generator.
- Contact email updated; patent wording softened; tests and CI added.

Contributor: Korg (AI assistant, Grok Bot).
