# Instruments On The Gantry

Mounted instruments now live in the gantry machine YAML under the top-level
`instruments` key. The runtime `Board` object still represents the mounted
tools plus the gantry for motion planning, but there is no separate board
YAML file in the active config set.

## Config

Representative gantry YAML excerpt:

```yaml
instruments:
  asmi:
    type: asmi
    vendor: vernier
    offset_x: 0.0
    offset_y: 0.0
    depth: 0.0
    measurement_height: 0.0
    force_threshold: -50
    sensor_channels: [1]
```

Edit the gantry machine file when:

- a different instrument is mounted
- offsets or reach depths change
- instrument-specific connection settings change

## Schema

The top-level YAML key is `instruments`. Each instrument entry requires:

- `type` - instrument type key from the registry
- `vendor` - allowed vendor for that type

Common optional fields are:

- `offset_x` and `offset_y` - XY offset from the gantry head reference point
- `depth` - positive tool depth below the gantry head reference point; in the +Z-up deck frame, gantry Z is computed as target/tool Z plus `depth`
- `measurement_height` - labware-relative offset (mm above
  `labware.height_mm`; negative = below) used as the action plane when the
  protocol command does not supply one. The XOR rule requires exactly one
  of (instrument config, protocol command) to set it per measure/scan.

`safe_approach_height` is no longer an instrument field. `Board.move_to_labware`
travels XY at the gantry-level `safe_z` (an absolute deck-frame Z set on the
gantry yaml's `cnc.safe_z`).

Driver-specific fields, such as serial ports, DLL paths, pipette models, or sensor channels, are passed through to the instrument driver constructor. Unknown gantry-root keys are rejected.

## Supported Instruments

The machine setup flow validates each `type` and `vendor` against the instrument registry, then instantiates the matching driver. Offline validation can pass `mock_mode=True`, which creates the configured drivers with `offline=True`.

| Instrument | Type Key | Vendor | Description |
|------------|----------|--------|-------------|
| Thorlabs CCS UV-Vis Spectrometer | `uvvis_ccs` | thorlabs | UV-Vis spectroscopy |
| Opentrons Pipette | `pipette` | opentrons | Liquid handling |
| ASMI Force Sensor | `asmi` | vernier | Force measurement |
| Filmetrics | `filmetrics` | kla | Thin-film thickness measurement |
| Excelitas OmniCure | `uv_curing` | excelitas | UV curing |

### UV-Vis Spectrometer (`uvvis_ccs`)

Thorlabs CCS compact spectrometer. Communicates via the TLCCS DLL.

| Method | Description |
|--------|-------------|
| `measure()` | Take a spectrum reading. Returns wavelengths and intensities. |
| `set_integration_time(seconds)` | Set the CCD integration time. |
| `get_integration_time()` | Get the current integration time. |
| `get_device_info()` | Return device identification strings. |

### Pipette (`pipette`)

Opentrons pipette controlled via Arduino serial (Pawduino firmware).

| Method | Description |
|--------|-------------|
| `aspirate(volume_ul, speed)` | Draw liquid into the tip. |
| `dispense(volume_ul, speed)` | Push liquid out of the tip. |
| `blowout(speed)` | Blow out remaining liquid. |
| `mix(volume_ul, repetitions, speed)` | Aspirate and dispense repeatedly. |
| `pick_up_tip(speed)` | Pick up a tip from a tiprack. |
| `drop_tip(speed)` | Drop the current tip. |
| `get_status()` | Return current pipette state. |

### ASMI Force Sensor (`asmi`)

Vernier GoDirect force sensor for indentation measurements.

| Method | Description |
|--------|-------------|
| `measure(n_samples)` | Take force readings. |
| `indentation(gantry, indentation_limit, step_size, force_limit, measurement_height, baseline_samples, measure_with_return=False)` | Step-by-step indentation. ``indentation_limit`` is a sign-agnostic *magnitude* — the descent distance below the action plane (``measurement_height``). Descend in Z steps, reading force at each step until force limit or magnitude is reached. Pass `measure_with_return=True` to also record upward return samples; every measurement carries a `direction` tag (`"down"` or `"up"`). |
| `get_force_reading()` | Single instantaneous force reading. |
| `get_baseline_force(samples)` | Average force over N samples (returns mean and std). |
| `get_status()` | Return sensor state. |

### Filmetrics (`filmetrics`)

KLA Filmetrics thin-film measurement system. Communicates with a C# console app via stdin/stdout.

| Method | Description |
|--------|-------------|
| `measure()` | Take a thickness measurement. Returns thickness in nm and goodness of fit. |

### UV Curing (`uv_curing`)

Excelitas OmniCure S1500 PRO UV light source controlled via RS-232 serial.

| Method | Description |
|--------|-------------|
| `cure(intensity, duration_s)` | Run UV curing at a given intensity for a duration. |
| `measure()` | Alias for cure — returns a CureResult. |
| `get_status()` | Return lamp state. |
