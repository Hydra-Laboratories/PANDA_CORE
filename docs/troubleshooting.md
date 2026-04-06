# Troubleshooting

This page is a starting template. The categories below are derived from the codebase, but the actual operator procedures still need to be written by people who run the hardware.

## Common Failure Categories

### Config Validation Fails

Likely areas:

- malformed YAML
- missing required fields
- unexpected extra fields
- impossible working-volume bounds
- deck positions outside the gantry envelope
- board offsets that make instrument targets unreachable

First check:

- validate the correct four YAML files
- compare recent calibration changes
- confirm you did not edit board or deck data when the experiment change only required protocol edits

### Gantry Connection Fails

Likely areas:

- wrong serial port
- device unavailable or powered off
- GRBL controller not responding
- unexpected controller settings

### Instrument Connection Fails

Likely areas:

- missing vendor executable or DLL
- wrong serial number or device identifier
- disconnected hardware
- timeouts during connect or measurement

### Protocol Runtime Fails

Likely areas:

- command argument mismatch
- instrument not present on the board
- unresolved deck target
- movement or measurement exception mid-run

### Persistence Fails

Likely areas:

- database path issues
- schema drift
- unexpected measurement payload shape

## TODO(manual)

- Add exact operator responses for each failure category
- Add a GRBL alarm/error quick-reference section tailored to this machine
- Add screenshots or sample logs for common failure modes
- Document what should be retried, what should be paused, and what should be escalated immediately
