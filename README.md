# fly-by-keystep

Use an Arturia Keystep MIDI controller to control Microsoft Flight Simulator.

## System Architecture

- **Keystep MIDI Controller** → Mac (via USB/MIDI)
- **Mac Python Scripts** → Windows PC running MSFS (via HTTP to MSFS Mobile Companion App)
- **MSFS Mobile Companion App** → Microsoft Flight Simulator (via SimConnect)

The Keystep's knobs and keys are mapped to aviation radio frequencies, autopilot settings, and other aircraft controls. The Mac receives MIDI input and translates it to HTTP requests sent to the MSFS Mobile Companion App server (default: `http://10.0.0.15:4000`) running on the Windows machine.
