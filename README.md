# Ansible role: raspi_config

An Ansible role that duplicates functionality of the raspi-config utility.

## TODO

Tasks to implement:

- [x] Change password for `pi` user
- [ ] Network options
  - [x] Update hostname
  - [x] Configure wifi
  - [x] Predictable network interface names
  - [ ] Network proxy settings
- [ ] Boot options
  - [x] Boot to desktop or cli
  - [x] Wait for network connection before boot
  - [ ] Splash screen or text boot
- [ ] Localization
  - [x] Change locale
  - [x] Change time zone
  - [ ] Change keyboard layout
  - [ ] Change Wifi country
- [ ] Interfacing
  - [x] Camera
  - [x] SSH
  - [x] VNC
  - [ ] SPI
  - [ ] I2C
  - [ ] Serial
  - [ ] 1-wire
  - [ ] Remote GPIO
- [ ] Overclock
- [ ] Advanced
  - [ ] Expand filesystem
  - [ ] Overscan
  - [ ] Memory split
  - [ ] Audio
  - [ ] Resolution
  - [ ] Screen blanking
  - [ ] Pixel doubling
  - [ ] GL driver
  - [ ] Compositor
  - [ ] Pi4 video output
  - [ ] Overlay FS

## Notes for docs later

### Structure

The tasks in this Ansible role are laid out to mirror those of the raspi-config menu.

### Tags

This playbook uses tags extensively.
