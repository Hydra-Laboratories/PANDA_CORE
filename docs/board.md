# Board

The board defines which instruments are mounted on the gantry head, their type, and their XYZ offsets from the head reference point.

## Config

Representative example:

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

Use this file when:

- a different instrument is mounted
- offsets or reach depths change
- instrument-specific connection settings change

## Schema

The top-level YAML key is `instruments`. Each instrument entry requires:

- `type` - instrument type key from the registry
- `vendor` - allowed vendor for that type

Common optional fields are:

- `offset_x` and `offset_y` - XY offset from the gantry head reference point
- `depth` - Z offset from the gantry head reference point
- `measurement_height` - instrument-specific height offset used by measurement commands

Driver-specific fields, such as serial ports, DLL paths, pipette models, or sensor channels, are passed through to the instrument driver constructor. Unknown top-level keys are rejected.

## Supported Instruments

The board loader validates each `type` and `vendor` against the instrument registry, then instantiates the matching driver. Offline validation can pass `mock_mode=True`, which creates the configured drivers with `offline=True`.

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
| `indentation(gantry, indentation_limit, step_size, force_limit, measurement_height, baseline_samples, measure_with_return=False)` | Step-by-step indentation: descend in Z steps, reading force at each step until force limit or indentation limit. Pass `measure_with_return=True` to also record upward return samples; every measurement carries a `direction` tag (`"down"` or `"up"`). |
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
