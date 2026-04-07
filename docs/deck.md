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

## Labware Types

- **Well plates** — defined by rows, columns, and two-point calibration. Positions are referenced by well ID (e.g. `plate.A1`).
- **Vials** — defined by a single `location` point. Referenced by labware key (e.g. `vial_1`).
