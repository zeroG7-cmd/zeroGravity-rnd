# Component: Raspberry Pi 3 Model B

## Category
- Compute / Single-board computer

## Overview
General-purpose embedded computer used as the main high-level processing unit for the system.

## Specifications

### Compute
- CPU: Quad-core ARM Cortex-A53 (1.2GHz)
- RAM: 1GB
- GPU: VideoCore IV

### Connectivity
- USB: 4x USB 2.0
- Ethernet: 10/100 Mbps
- Wi-Fi: 802.11n
- Bluetooth: 4.1

### Interfaces
- GPIO: 40-pin header
- CSI: Camera interface
- DSI: Display interface
- UART / I2C / SPI supported

## Electrical
- Input Voltage: 5V
- Typical Current: ~700mA – 2.5A (depending on load)
- Power Input: Micro USB

## Physical
- Mass: ~50g
- Dimensions: 85 x 56 x 17 mm

## System Role
- Runs ROS
- Processes LiDAR and sensor data
- Handles SLAM and high-level decision making

## Integration
- Mounted as base for Navio 2 (GPIO stacking)
- Connected to sensors (LiDAR, camera)
- Communicates with flight controller layer

## Dependencies
- Requires stable 5V power supply
- Requires OS (e.g. Ubuntu / Raspberry Pi OS)

## URDF Notes
- Represent as a box (approx dimensions)
- Combined with Navio 2 as single physical unit in simulation
