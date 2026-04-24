# Deck

The deck defines what labware is physically present and where it is
positioned. Well plates and tip racks use two-point calibration (A1 + A2,
must be axis-aligned) and per-column/row offsets. Single-location labware
such as vials stores a direct position. Physical holders (vial holders,
well plate holders, tip disposals) use a bounding-box anchor and can nest
liquid-handling labware inside them.

## Config (explicit form)

Every field fully spelled out:

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

Use the deck YAML when:

- labware is moved or re-calibrated
- the physical deck arrangement changes
- a different plate, rack, or vial layout is installed

## Config (via labware definitions)

Common labware — standard SBS microplates, Ursa-specific 3D-printed
fixtures, standard tip racks — is pre-described under
`src/deck/labware/definitions/`. A deck YAML can pull in a definition by
name via `load_name:` and override only the fields that are deck-specific
(typically `calibration`, `location`, or the sign of `x_offset_mm` /
`y_offset_mm` to match the deck's orientation).

```yaml
labware:
  plate:
    load_name: sbs_96_wellplate
    name: asmi_96_well
    model_name: asmi_96_well
    calibration:
      a1: { x: -49.7, y: -236.8, z: -50.0 }
      a2: { x: -58.7, y: -236.8, z: -50.0 }
    x_offset_mm: -9.0   # ASMI deck walks columns in -x
```

The loader:

1. Looks up `sbs_96_wellplate` in the definitions registry
   (`src/deck/labware/definitions/registry.yaml`).
2. Loads its class-attribute template
   (`sbs_96_wellplate/SBS96WellPlate.yaml`): 8 × 12 grid, 127.76 × 85.47 ×
   14.35 mm footprint, 9 mm pitch, 200 µL default capacity.
3. **Shallow-merges** the user's fields on top of the template (user
   wins). Dict-valued fields like `calibration:` are replaced whole, not
   deep-merged — so always supply both `a1` and `a2`.
4. Defaults the labware `name` to the deck key if the user doesn't set it
   explicitly.
5. Hands the merged dict to the existing YAML schema for validation and
   class construction, so everything downstream stays unchanged.

Entries without `load_name:` are passed through untouched, so existing
deck YAMLs keep working unmodified.

### Available definitions

| `load_name:` | Python class | Notes |
| --- | --- | --- |
| `sbs_96_wellplate` | `WellPlate` | Generic ANSI SLAS 96-well microplate. Override `capacity_ul`/`height_mm` for vendor-specific variants. |
| `ursa_tip_rack` | `TipRack` | Ursa 2-column × 15-row pipette tip rack. |
| `ursa_vial_holder` | `VialHolder` | 9-position tight-fit 20 mL vial holder (Cub-XL). |
| `ursa_wellplate_holder` | `WellPlateHolder` | Tall wellplate holder (Cub). |
| `ursa_wellplate_holder_conductive` | `WellPlateHolder` | Conductive wellplate holder (Cub-XL). |

See each `definitions/<name>/README.md` for physical dimensions,
assembly notes, and 3D-printable STEP/STL files where applicable.

## Z Coordinates

Labware positions can define Z in either of two ways:

- Provide explicit `z` values on calibration or location points.
- Provide `height` on the labware entry. Under the CubOS deck-origin frame, `height` is used directly as the absolute deck-frame Z value.

If `height` is not used, explicit Z coordinates are required.

## Well Plate Calibration

For well plates, `calibration.a1` is the A1 well center and `calibration.a2` must be one adjacent column step from A1. A2 must share either the same X or the same Y as A1, and its delta must match either `x_offset_mm` or `y_offset_mm` depending on the plate orientation. Diagonal calibration is rejected.

Top-level `a1` is still accepted for backward compatibility, but new deck files should use `calibration.a1`.

## Labware Types

- **`well_plate`** — multi-well microplate defined by rows, columns, and
  two-point calibration. Positions are referenced by well ID
  (e.g. `plate.A1`).
- **`tip_rack`** — pipette tip rack. Same calibration pattern as
  `well_plate`; tip positions are derived from `a1`/`a2` + pitch offsets
  rather than listed explicitly. Tracks per-tip occupancy via
  `tip_present`.
- **`vial`** — single vial with a `location`. Referenced by labware key
  (e.g. `vial_1`).
- **`vial_holder`** — physical rack that seats multiple vials at fixed
  offsets. Holds nested `Vial` instances at the seat height above the
  holder anchor.
- **`well_plate_holder`** — physical fixture that seats a well plate at a
  fixed z above the holder anchor. Holds one nested `WellPlate`.
- **`tip_disposal`** — bounding-box fixture for used-tip disposal.

## Adding a new definition

1. Create a folder under `src/deck/labware/definitions/<new_name>/`.
2. Add a YAML file (any name) that lists the class fields directly
   (no top-level `labware:` wrapper).  Include `type:` matching the
   Python labware class's schema (`well_plate`, `tip_rack`,
   `vial_holder`, etc.).
3. Add an entry to `definitions/registry.yaml` pointing at the Python
   module, class name, and config path.
4. Add a short `README.md` in the new folder describing the physical
   part (dimensions, compatibility, printable files if any).

The registry is cached at module import time; a programmatic consumer
can inspect it via `deck.labware.definitions.registry`:

```python
from deck.labware.definitions.registry import (
    get_supported_definitions,
    get_labware_class,
    load_definition_config,
    build_labware,
)

print(get_supported_definitions())
# ['sbs_96_wellplate', 'ursa_tip_rack', 'ursa_vial_holder', ...]

# Build a labware instance directly from the registry.
from deck.labware import Coordinate3D
holder = build_labware(
    "ursa_vial_holder",
    location=Coordinate3D(x=17.1, y=132.9, z=164.0),
)
```
