# Deck

The deck defines what labware is physically present and where it is positioned. Well plates use two-point calibration (A1 + A2, must be axis-aligned). Single-location labware such as vials stores a direct position.

## Config

Representative example:

```yaml
labware:
  plate:
    type: well_plate
    name: asmi_96_well
    model_name: asmi_96_well
    rows: 8
    columns: 12
    calibration:
      a1: { x: -49.7, y: -236.8, z: -50.0 }
      a2: { x: -58.7, y: -236.8, z: -50.0 }
    x_offset_mm: -9.0
    y_offset_mm: 9.0
```

Use this file when:

- labware is moved or re-calibrated
- the physical deck arrangement changes
- a different plate or vial layout is installed

## Z Coordinates

Labware positions can define Z in either of two ways:

- Provide explicit `z` values on calibration or location points.
- Provide `height` on the labware entry and load the deck with the gantry `total_z_height`; CubOS computes Z as `total_z_height - height`.

If `height` is used, `total_z_height` must be available from the gantry config. If `height` is not used, explicit Z coordinates are required.

## Well Plate Calibration

For well plates, `calibration.a1` is the A1 well center and `calibration.a2` must be one adjacent column step from A1. A2 must share either the same X or the same Y as A1, and its delta must match either `x_offset_mm` or `y_offset_mm` depending on the plate orientation. Diagonal calibration is rejected.

Top-level `a1` is still accepted for backward compatibility, but new deck files should use `calibration.a1`.

## Labware Types

- **Well plates** — defined by rows, columns, and two-point calibration. Positions are referenced by well ID (e.g. `plate.A1`).
- **Vials** — defined by a single `location` point. Referenced by labware key (e.g. `vial_1`).
