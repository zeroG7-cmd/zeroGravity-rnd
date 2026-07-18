# Component: Navio 2

## Category
- Flight Controller / Autopilot HAT

## Overview
Autopilot expansion board for Raspberry Pi that enables real-time flight control, sensor fusion, and motor control.

## Specifications

### Sensors
- IMU: Gyroscope + Accelerometer
- Magnetometer (Compass)
- Barometer

### Navigation
- GNSS: GPS / GLONASS / Galileo support

### Interfaces
- PWM Outputs: Motor control signals (ESC)
- RC Input: Receiver support
- UART / I2C / SPI
- ADC inputs

## Electrical
- Input Voltage: via Raspberry Pi / power module
- Power Output: supports peripherals via Pi

## Physical
- Mass: ~23g
- Dimensions: 65 x 56 mm (matches Raspberry Pi footprint)

## System Role
- Stabilisation and control of drone
- Sensor fusion (IMU + GPS)
- Sends control signals to ESCs
- Runs ArduPilot

## Integration
- Directly mounted on Raspberry Pi via GPIO header
- Connected to ESCs (signal wires)
- Interfaces with receiver and telemetry

## Dependencies
- Requires Raspberry Pi
- Requires ArduPilot firmware

## URDF Notes
- Not modelled separately in early stages
- Included as part of Pi + Navio stack assembly
