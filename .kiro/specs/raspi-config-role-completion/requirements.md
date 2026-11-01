# Requirements Document

## Introduction

The `tkeemon.raspi_config` Ansible role reproduces the options of the Raspberry Pi `raspi-config` utility as idempotent Ansible tasks. The role is partially complete and was written against Raspberry Pi OS bullseye. This feature completes the role against the `trixie` branch of the Upstream_Script (https://github.com/RPi-Distro/raspi-config/blob/trixie/raspi-config).

The work covers four areas:

1. Implement the menu options that the Upstream_Script offers on trixie and the Role does not yet manage.
2. Fix existing tasks that call Upstream_Script functions removed on trixie, or that misreport `changed`/`ok`.
3. Remove or deprecate options that the trixie Upstream_Script no longer offers.
4. Add documentation, validation, and automated checks so the Role can be released.

Delivery constraint: the work ships in phases. Phase 1 delivers the shared foundations (Requirements 1 to 8) and the fixes to existing tasks that are broken or misreport `changed`/`ok`. Later phases deliver one submenu at a time in this order: System, Display, Interface, Performance, Localisation, Advanced. The last phase delivers documentation and CI (Requirements 19 to 21). The order of the requirements below does not imply delivery order.

Inventory of the trixie Upstream_Script menus compared with the current Role (as of this document):

| Menu option (trixie) | Upstream function | Current Role status |
|---|---|---|
| S1 Wireless LAN | `do_wifi_ssid_passphrase` | Partial: change always runs, duplicate detection uses `wpa_cli` (trixie uses NetworkManager) |
| S2 Audio | `do_audio` | Missing (placeholder `fail` task) |
| S3 Password | `ansible.builtin.user` | Partial: reports `changed` on every run because of random salt; defaults to the insecure value `raspberry` |
| S4 Hostname | `get_hostname` / `do_hostname` | Implemented; change command runs on every play |
| S5 Boot | `get_boot_cli` / `do_boot_target` | Partial: combined with auto login, reports `changed` on every run |
| S6 Auto Login | `get_autologin_*` / `do_autologin` | Partial: combined with boot target |
| S7 Splash Screen | `get_boot_splash` / `do_boot_splash` | Implemented with a condition bug in the enable task |
| S8 Power LED | `get_leds` / `do_leds` | Implemented |
| S9 Browser | `get_browser` / `do_browser` | Missing |
| S10 Admin Password | `get_sudo_pass` / `do_sudo_pass` | Missing |
| D1 Underscan | `get_overscan_kms` / `do_overscan_kms` | Missing (placeholder `fail` task) |
| D2 Screen Blanking | `get_blanking` / `do_blanking` | Implemented |
| D3 VNC Resolution | `get_vnc_resolution` / `do_vnc_resolution` | Implemented |
| D4 Composite | `get_composite` / `do_composite` | Implemented, no model gate |
| D5 4Kp60 HDMI | `get_pi4video` / `do_pi4video` | Missing |
| D6 Onscreen Keyboard | `get_squeekboard` / `do_squeekboard` | Missing |
| D7 Keyboard Output | `get_squeek_output` / `do_squeek_output` | Missing |
| I1 SSH | `get_ssh` / `do_ssh` | Implemented |
| I2 RPi Connect | `get_rpi_connect` / `do_rpi_connect` | Missing |
| I3 VNC | `get_vnc` / `do_vnc` | Implemented |
| I4 SPI | `get_spi` / `do_spi` | Implemented |
| I5 I2C | `get_i2c` / `do_i2c` | Implemented |
| I6 Serial Port | `get_serial_cons`, `get_serial_hw`, `do_serial_cons`, `do_serial_hw` | Broken: calls `get_serial` (removed) and `do_serial` (interactive only) |
| I7 1-Wire | `get_onewire` / `do_onewire` | Implemented |
| P1 Overclock | `do_overclock` | Partial: reports `changed` on every run |
| P2 Overlay File System | `get_overlay_conf` / `do_overlayfs` | Implemented |
| P3 Fan | `get_fan`, `get_fan_gpio`, `get_fan_temp`, `do_fan` | Partial: reports `changed` on every run, no model gate |
| P4 USB Current | `get_usb_current` / `do_usb_current` | Missing |
| L1 Locale | `do_change_locale` | Broken: current-locale check reads the literal string `$LANG` |
| L2 Timezone | `do_change_timezone` | Partial: invalid time zone is not reported |
| L3 Keyboard | `do_configure_keyboard` | Missing (placeholder `fail` task) |
| L4 WLAN Country | `get_wifi_country` / `do_wifi_country` | Implemented |
| A1 Expand Filesystem | `get_can_expand` / `do_expand_rootfs` | Partial: reports `changed` on every run when enabled |
| A2 Network Interface Names | `get_net_names` / `do_net_names` | Implemented |
| A3 Network Proxy Settings | `get_proxy` / `do_proxy` | Missing |
| A4 Boot Order | `do_boot_order` | Missing; out of scope |
| A5 Bootloader Version | `do_boot_rom` | Missing; out of scope |
| A6 Beta Access | `do_beta_mode` | Missing |
| A7 Wayland | `do_wayland` | Partial: detection checks an obsolete `LXDE-pi-wayland` session name |
| A8 PCIe Speed | `get_pci` / `do_pci` | Missing |
| A9 Network Install UI | `do_network_install_ui` | Missing; out of scope |
| A10 Shutdown Behaviour | `do_power_off_on_halt` | Missing; out of scope |
| A11 Logging | `do_journald_storage` | Missing |
| A12 WLAN Power Save | `get_wifi_power_save` / `do_wifi_power_save` | Missing |
| A13 Link-local Fallback | `get_link_local_fallback` / `do_link_local_fallback` | Missing |
| A14 AB Firmware | `get_ab_firmware` / `do_ab_firmware` | Missing; out of scope |

Options the Role implements today that the trixie Upstream_Script no longer offers in its menus: Legacy Camera, Remote GPIO (`do_rgpio` removed), Pixel Doubling (`do_pixdub` removed), GPU Memory (`do_memory_split` removed), Network at Boot (`do_boot_wait` removed), xcompmgr Compositor, and Glamor.

Out of scope: the Upstream_Script "8 Update" and "9 About raspi-config" menu entries; the hidden `do_resolution`, `do_gldriver`, and `do_camera` functions; the bootloader and EEPROM Options A4 Boot Order, A5 Bootloader Version, A9 Network Install UI, A10 Shutdown Behaviour, and A14 AB Firmware (deferred to a later feature); and Raspberry Pi OS releases older than trixie.

Decisions (confirmed by the maintainer):

- The Role calls `raspi-config nonint get_*` and `raspi-config nonint do_*` for checks and changes, as the existing tasks do. Where a native Ansible module gives the same result with better idempotence (for example `ansible.builtin.user` for the password), the Role uses that module.
- The Role supports Raspberry Pi OS trixie only. The Role removes the tasks for Options that the trixie Upstream_Script no longer offers and prints a deprecation warning when their Role_Variables are set.
- Breaking Role_Variable changes are accepted. `raspi_config_boot_behavior` accepts only `console` and `desktop`, with separate console and desktop auto login booleans. `raspi_config_enable_serial_port` is split into `raspi_config_enable_serial_console` and `raspi_config_enable_serial_hardware`. `raspi_config_enable_wayland` is replaced by `raspi_config_desktop_backend` (`x11` or `labwc`). The Role fails validation with a pointer to the new names when the old names or values are used, and the README documents the breaking changes.
- `raspi_config_password` defaults to the Unmanaged_Value. The previous default `raspberry` is removed.
- Testing is done with `yamllint`, `ansible-lint`, and `ansible-playbook --syntax-check` in the CI_Pipeline, plus a Test_Playbook that the maintainer runs manually against physical Raspberry Pi hosts (Pi 5, Pi 4, Pi 3, and Pi Zero / Zero 2 W). The Role uses no Molecule scenarios, because Molecule containers cannot run most `raspi-config` functions: those functions depend on `/boot/firmware/config.txt`, `vcgencmd`, and device-tree files.
- To be confirmed during design: the Pi_Model value that `get_pi_type` reports on the Pi Zero 2 W. The Zero 2 W may report 3 rather than 0. Until the value is confirmed, the Test_Inventory records the expected Pi_Model of the Zero host group as a group variable (Requirement 21, criterion 5).

## Glossary

- **Role**: The `tkeemon.raspi_config` Ansible role in this repository.
- **Upstream_Script**: The `raspi-config` shell script on the `trixie` branch of `RPi-Distro/raspi-config`.
- **Target_Host**: A Raspberry Pi running Raspberry Pi OS trixie that the Role configures.
- **Option**: A single entry in an Upstream_Script submenu, for example "I1 SSH".
- **Submenu_File**: The task file under `tasks/` that holds all Options of one Upstream_Script submenu (`system.yml`, `display.yml`, `interface.yml`, `performance.yml`, `localization.yml`, `advanced.yml`).
- **Role_Variable**: A variable defined in `defaults/main.yml` with the `raspi_config_` prefix that sets the desired state of one Option.
- **Desired_State**: The state of an Option as expressed by the Role_Variable values.
- **Current_State**: The state of an Option on the Target_Host before the Role changes the Option.
- **Check_Task**: A task that reads the Current_State of an Option without modifying the Target_Host.
- **Change_Task**: A task that moves an Option from the Current_State to the Desired_State.
- **Unmanaged_Value**: The empty string `""`. A Role_Variable set to the Unmanaged_Value tells the Role to leave the Option untouched.
- **Fresh_Install_Default**: The value an Option has on a freshly flashed Raspberry Pi OS trixie image before any user configuration.
- **Pi_Model**: The model number returned by `raspi-config nonint get_pi_type` (0 = Zero, 1, 2, 3, 4, 5, -1 = not a Raspberry Pi).
- **Model_Gate**: A condition that limits an Option to the Pi_Model values for which the Upstream_Script offers the Option.
- **Reboot_Handler**: The handler named `Reboot` in `handlers/main.yml`.
- **Validation_Task**: A task that checks Role_Variable values before any Change_Task runs.
- **Deprecated_Variable**: A Role_Variable that controlled an Option the trixie Upstream_Script no longer offers.
- **Renamed_Variable**: A Role_Variable from the previous Role release that this feature replaces with new Role_Variables: `raspi_config_enable_serial_port` (replaced by `raspi_config_enable_serial_console` and `raspi_config_enable_serial_hardware`) and `raspi_config_enable_wayland` (replaced by `raspi_config_desktop_backend`).
- **Tag_Convention**: Task tags of the form `raspi_config:SUBMENU_NAME:TASK_NAME`, with `:enable` and `:disable` suffixes on Change_Tasks for boolean Options.
- **README**: The `README.md` file in the repository root.
- **CI_Pipeline**: The GitHub Actions workflow in `.github/workflows/ci.yml`.
- **Test_Playbook**: The playbook in `tests/` used to run the Role against a Target_Host.
- **Test_Inventory**: The inventory file `tests/inventory` that lists the Target_Hosts for the Test_Playbook.

## Requirements

### Requirement 1: Target platform and role metadata

**User Story:** As a role user, I want the role to declare which OS release and Ansible version it supports, so that I know whether the role will work on my Raspberry Pi.

#### Acceptance Criteria

1. THE Role SHALL list Debian as the only platform in the `platforms` section of `meta/main.yml`, with `trixie` as the only version of that platform.
2. THE Role SHALL set `min_ansible_version` in `meta/main.yml` to a version that is equal to or newer than the version in which each module, module option, and playbook keyword used by the Role's tasks was added.
3. IF the Debian release codename of the Target_Host is not `trixie`, or the distribution of the Target_Host is not Debian, THEN THE Role SHALL fail on that Target_Host before any Check_Task or Change_Task runs, with a message that names the detected distribution, the detected release, and the supported release `trixie`.
4. THE Role SHALL read the distribution and release used by criterion 3 from the Target_Host, including in plays that set `gather_facts: false`.
5. IF the `raspi-config` command is not found in the command search path of the privileged user on the Target_Host, THEN THE Role SHALL fail on that Target_Host before the Pi_Model detection task and before any Check_Task or Change_Task runs, with a message that names the missing `raspi-config` command.
6. IF `raspi-config nonint get_pi_type` returns -1, THEN THE Role SHALL fail on that Target_Host before any Check_Task or Change_Task runs, with a message stating that the Target_Host is not a Raspberry Pi.
7. IF `raspi-config nonint get_pi_type` exits with a non-zero status or returns a value other than 0, 1, 2, 3, 4, 5, or -1, THEN THE Role SHALL fail on that Target_Host before any Check_Task or Change_Task runs, with a message that includes the returned output and exit status.
8. IF any check in criteria 3 to 7 fails on a Target_Host, THEN THE Role SHALL run the checks in the order release (criterion 3), `raspi-config` presence (criterion 5), and Pi_Model (criteria 6 and 7), stop at the first failing check for that Target_Host, leave that Target_Host unmodified, and continue the play on the other Target_Hosts.
9. THE Role SHALL run the checks in criteria 3 to 7 on every play, including plays limited with `--tags` or `--skip-tags` and plays run in check mode, and THE Role SHALL make no change to the Target_Host while running those checks.

### Requirement 2: Idempotent check-then-change pattern

**User Story:** As a role user, I want every option to report `changed` only when the role actually changes my Pi, so that repeated runs are safe and the play recap is accurate.

#### Acceptance Criteria

1. THE Role SHALL run, for each Option that has a Change_Task calling `raspi-config nonint do_*`, a Check_Task that reads the Current_State of that Option in the same play before any Change_Task of that Option runs, with one Check_Task shared by the enabling and disabling Change_Tasks of a boolean Option. For a Change_Task that uses a native Ansible module that compares the Current_State itself (for example `ansible.builtin.user`), the Role SHALL rely on that module and SHALL NOT add a separate Check_Task.
2. THE Role SHALL mark every Check_Task as `changed_when: false` and SHALL limit every Check_Task to read-only operations that leave every file, service, and setting on the Target_Host unmodified.
3. WHEN the Current_State equals the Desired_State, THE Role SHALL skip every Change_Task of that Option, so that each Change_Task that calls `raspi-config nonint do_*` reports `skipped` and each native-module Change_Task reports `ok`, and SHALL NOT notify the Reboot_Handler for that Option.
4. WHEN the Current_State differs from the Desired_State, THE Role SHALL run exactly one Change_Task for that Option (the enabling or the disabling Change_Task for a boolean Option) and report that Change_Task as `changed`.
5. WHEN the Role runs a second time against the same Target_Host with the same Role_Variable values, after a first run that finished with zero `failed` tasks and with a reboot of the Target_Host between the runs if the first run notified the Reboot_Handler, THE Role SHALL report zero tasks with `changed` status in the play recap for the second run and SHALL NOT notify the Reboot_Handler.
6. WHILE Ansible runs in check mode, THE Role SHALL execute every Check_Task against the Target_Host and report as `changed` each Change_Task whose Option has a Current_State different from the Desired_State, while leaving every file, service, package, and setting on the Target_Host unmodified.
7. IF a Check_Task exits with code 0 but its output, after leading and trailing whitespace is removed, is not one of the values that the Role maps to a state of that Option (for boolean Options, `0` or `1`), THEN THE Role SHALL fail the Target_Host before any Change_Task of that Option runs, with a message that names the Option and includes the Check_Task output.
8. IF a Check_Task exits with a non-zero exit code, THEN THE Role SHALL fail the Target_Host before any Change_Task of that Option runs, with a message that names the Option and includes the exit code and the error output of the Check_Task.
9. IF a Change_Task exits with a non-zero exit code, THEN THE Role SHALL report that Change_Task as `failed` with a message that names the Option and includes the error output, SHALL NOT notify the Reboot_Handler from that Change_Task, and SHALL leave the Options changed earlier in the play in their changed state.
10. WHILE Ansible runs in check mode, THE Reboot_Handler SHALL NOT reboot the Target_Host.

### Requirement 3: Tag conventions

**User Story:** As a role user, I want consistent tags on every task, so that I can run a single option or a single submenu.

#### Acceptance Criteria

1. THE Role SHALL tag every task that belongs to an Option with the base tag `raspi_config:SUBMENU_NAME:TASK_NAME`. This covers Check_Tasks, Change_Tasks, package installation tasks that come before a Change_Task, and tasks that print Model_Gate or skip messages. SUBMENU_NAME SHALL equal the base name of the Submenu_File that contains the task (`system`, `display`, `interface`, `performance`, `localization`, or `advanced`). TASK_NAME SHALL consist only of lowercase letters, digits, and underscores, SHALL be identical for all tasks of one Option, and SHALL be unique among the Options of that Submenu_File.
2. WHERE an Option is a boolean enable/disable Option (an Option whose Role_Variable accepts only `true` or `false`), THE Role SHALL tag the enabling Change_Task with the base tag and `raspi_config:SUBMENU_NAME:TASK_NAME:enable` and no `:disable` tag, and SHALL tag the disabling Change_Task with the base tag and `raspi_config:SUBMENU_NAME:TASK_NAME:disable` and no `:enable` tag.
3. WHERE an Option is a boolean enable/disable Option, THE Role SHALL tag the Check_Task of that Option with the base tag, the `:enable` tag, and the `:disable` tag of that Option.
4. THE Role SHALL tag each of the six `import_tasks` entries in `tasks/main.yml` with `raspi_config` and `raspi_config:SUBMENU_NAME`, where SUBMENU_NAME matches the base name of the imported Submenu_File.
5. THE Role SHALL tag the Pi_Model detection task, the Validation_Tasks, and the Deprecated_Variable warning tasks with `always`.
6. WHEN the Role runs with `--tags raspi_config:SUBMENU_NAME:TASK_NAME` for one Option, THE Role SHALL run the tasks tagged `always` and the tasks of that Option, and SHALL skip every task of every other Option.
7. WHEN the Role runs with `--tags raspi_config:SUBMENU_NAME`, THE Role SHALL run the tasks tagged `always` and all tasks of that Submenu_File, and SHALL skip every task in the other Submenu_Files.
8. WHERE an Option is not a boolean enable/disable Option, THE Role SHALL tag the tasks of that Option with the base tag only, without `:enable` or `:disable` suffixes.

### Requirement 4: Role variable conventions and defaults

**User Story:** As a role user, I want the default variables to describe a fresh Raspberry Pi OS install, so that running the role with defaults leaves a fresh Pi in its original state.

#### Acceptance Criteria

1. THE Role SHALL prefix every Role_Variable, and every other variable defined in `defaults/main.yml` or `vars/main.yml` (for example `raspi_config_user` and `raspi_config_allow_reboot`), with `raspi_config_`.
2. THE Role SHALL set every Role_Variable in `defaults/main.yml` to the Fresh_Install_Default of its Option, except for the Role_Variables listed in criterion 3. Where an Option has no value on a freshly flashed Raspberry Pi OS trixie image, the Role SHALL use the Unmanaged_Value as the default.
3. THE Role SHALL set the following Role_Variables to the Unmanaged_Value in `defaults/main.yml`: `raspi_config_wifi_ssid`, `raspi_config_wifi_password`, `raspi_config_password`, `raspi_config_browser`, `raspi_config_onscreen_keyboard_output`, and the network proxy Role_Variable for each of the `http`, `https`, `ftp`, `rsync`, and `no` schemes.
4. WHERE a Role_Variable that controls an Option is set to the Unmanaged_Value, THE Role SHALL skip the Check_Tasks and Change_Tasks of that Option and report those tasks as `skipped`. For the network proxy Option, this rule applies separately to each scheme, so a scheme whose Role_Variable is the Unmanaged_Value is skipped while the other schemes are still managed.
5. THE Role SHALL document each Role_Variable in `defaults/main.yml` with YAML comment lines placed directly above the variable, with no blank line between them. The comment lines SHALL state: the Upstream_Script menu number (for example `S1` or `I6`); the accepted values, given as an explicit list, as a numeric range, or as a reference to the Target_Host file that defines the list (`/usr/share/i18n/SUPPORTED`, `/usr/share/zoneinfo/iso3166.tab`, or `/usr/share/zoneinfo/`); whether the Unmanaged_Value is accepted; and the Pi_Model values to which the Option applies, or `all` if the Option has no Model_Gate.
6. THE Role SHALL group Role_Variables in `defaults/main.yml` by Submenu_File in the order `system`, `display`, `interface`, `performance`, `localization`, `advanced`. Within each group, variables SHALL appear in ascending numeric Upstream_Script menu order (for example S9 before S10). Variables that control no Option, such as `raspi_config_user` and `raspi_config_allow_reboot`, SHALL appear before the first group.
7. THE Role SHALL define no Deprecated_Variable and no Renamed_Variable in `defaults/main.yml` or `vars/main.yml`.
8. IF a Role_Variable that accepts the Unmanaged_Value is set to the Unmanaged_Value, THEN THE Validation_Task SHALL pass that Role_Variable's accepted-value check without failing the play.
9. WHEN the Role runs with every Role_Variable at its `defaults/main.yml` value against a Target_Host whose Options are all at their Fresh_Install_Default, THE Role SHALL report zero `changed` tasks, excluding the first-boot `raspi-config` prompt removal task of Requirement 18.

### Requirement 5: Input validation

**User Story:** As a role user, I want the role to reject invalid variable values before it touches my Pi, so that a typo does not leave the Pi half-configured.

#### Acceptance Criteria

1. WHEN the Role starts, THE Validation_Task SHALL check every enumerated Role_Variable (a Role_Variable whose accepted values are a fixed list documented in `defaults/main.yml`) against that list before any Change_Task runs. The check SHALL also run in check mode, when the play is limited with Tag_Convention tags, and when a Model_Gate excludes the Option on the Target_Host.
2. IF an enumerated Role_Variable holds a value that is not in its accepted values, compared case-sensitively, and the value is not an Unmanaged_Value that the Option accepts under Requirement 4 criterion 3, THEN THE Validation_Task SHALL fail the play for that Target_Host before any Change_Task runs, with a message naming the Role_Variable, the given value, and the accepted values, and the Target_Host SHALL remain unmodified.
3. IF `raspi_config_gpio_fan_temp` is not an integer from 60 to 120 inclusive, or `raspi_config_gpio_fan_pin` is not an integer from 2 to 27 inclusive, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the Role_Variable, the given value, and the accepted range.
4. IF `raspi_config_wifi_country` is not the Unmanaged_Value and does not exactly match, case-sensitively, a two-letter uppercase code in the first column of `/usr/share/zoneinfo/iso3166.tab` on the Target_Host, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming `raspi_config_wifi_country` and the given value.
5. IF `raspi_config_time_zone` is not the Unmanaged_Value and either contains a `..` path component or does not name a regular file (or a symbolic link to a regular file) at `/usr/share/zoneinfo/<value>` on the Target_Host, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming `raspi_config_time_zone` and the given value.
6. IF `raspi_config_locale` is not the Unmanaged_Value and does not exactly match the first whitespace-separated field of any line in `/usr/share/i18n/SUPPORTED` on the Target_Host, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming `raspi_config_locale` and the given value.
7. IF a Renamed_Variable is defined in the play with any value, including the Unmanaged_Value, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the Renamed_Variable and the Role_Variables that replace it.
8. IF a boolean Role_Variable (a Role_Variable whose accepted values are `true` and `false`) holds a value that is not of boolean type, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the Role_Variable, the given value, and the accepted values `true` and `false`.
9. IF `/usr/share/zoneinfo/iso3166.tab`, `/usr/share/zoneinfo/`, or `/usr/share/i18n/SUPPORTED` is absent or unreadable on the Target_Host while the matching Role_Variable is not the Unmanaged_Value, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the missing reference file and the Role_Variable that needs it.

### Requirement 6: Model gating

**User Story:** As a role user, I want options that do not apply to my Pi model to be skipped, so that one playbook works across a mixed fleet.

#### Acceptance Criteria

1. THE Role SHALL apply a Model_Gate to each Option that the trixie Upstream_Script menus limit to specific Pi_Model values. Each Model_Gate SHALL use the same Pi_Model values as the Upstream_Script menus and the same Pi_Model values documented for that Option in `defaults/main.yml`. The gated Options SHALL include at least Overclock (Pi_Model 1 or 2), Fan (Pi_Model 4), 4Kp60 HDMI (Pi_Model 4), USB Current (Pi_Model 5), and PCIe Speed (Pi_Model 5).
2. IF a Model_Gate excludes an Option on the Target_Host and the Role_Variable of that Option is neither the Unmanaged_Value nor the Fresh_Install_Default, THEN THE Role SHALL print one message for that Option on that Target_Host, report the message task as `ok`, and continue the play without failing. The message SHALL name the Option, the detected Pi_Model, and the Pi_Model values to which the Option applies.
3. IF a Model_Gate excludes an Option on the Target_Host, THEN THE Role SHALL report every Check_Task and Change_Task of that Option as `skipped`, leave that Option unmodified on the Target_Host, and continue the play without failing. This SHALL also apply when the play runs with only that Option's Tag_Convention tags selected.
4. IF the Power LED Check_Task (`get_leds`) returns -1, THEN THE Role SHALL report the Power LED Change_Tasks as `skipped`, print a message stating that the Power LED behaviour cannot be changed on the Target_Host, report the message task as `ok`, and continue the play without failing.
5. WHEN the Role starts on a Target_Host, THE Role SHALL read the Pi_Model with `raspi-config nonint get_pi_type` once, before any Check_Task of a gated Option runs, and SHALL handle invalid `get_pi_type` output as defined in Requirement 1, criteria 6 and 7.

### Requirement 7: Reboot handling

**User Story:** As a role user, I want to control whether the role reboots my Pi, so that changes that need a reboot take effect without surprising me.

#### Acceptance Criteria

1. WHEN a Change_Task reports `changed` and the Upstream_Script sets `ASK_TO_REBOOT=1` in the `do_*` function of that Change_Task's Option, THE Role SHALL notify the Reboot_Handler from that Change_Task.
2. WHERE `raspi_config_allow_reboot` is `true`, THE Reboot_Handler SHALL reboot the Target_Host with `ansible.builtin.reboot` and wait up to 600 seconds for the Target_Host to accept a new connection before the play continues.
3. WHERE `raspi_config_allow_reboot` is `false`, THE Reboot_Handler SHALL print one message per Target_Host. The message SHALL state that the Target_Host needs a reboot for the changes to take effect and SHALL name `raspi_config_allow_reboot` as the Role_Variable that enables automatic reboots. THE Reboot_Handler SHALL not reboot the Target_Host.
4. THE Role SHALL set `raspi_config_allow_reboot`, which accepts `true` or `false`, to `false` in `defaults/main.yml`.
5. WHEN one or more Change_Tasks notify the Reboot_Handler during one play on a Target_Host, THE Reboot_Handler SHALL run exactly once for that Target_Host, after all Change_Tasks of the Role on that Target_Host have run.
6. IF the Target_Host does not accept a new connection within 600 seconds of the reboot command, THEN THE Reboot_Handler SHALL fail the play for that Target_Host with a message stating that the Target_Host did not come back after the reboot.
7. WHILE Ansible runs in check mode, THE Reboot_Handler SHALL leave the Target_Host running without a reboot, whatever the value of `raspi_config_allow_reboot`, and SHALL print a message stating that the Target_Host would need a reboot.
8. THE Role SHALL notify the Reboot_Handler from no Check_Task, and from no Change_Task whose Option's Upstream_Script `do_*` function does not set `ASK_TO_REBOOT=1`.

### Requirement 8: Removal of placeholder tasks and obsolete options

**User Story:** As a role maintainer, I want the role to contain only options that exist in trixie, so that the role does not call removed functions or print fake failures.

#### Acceptance Criteria

1. THE Role SHALL contain no task in any file under `tasks/` that combines `ansible.builtin.fail` with `ignore_errors: true`.
2. THE Role SHALL pass to `raspi-config nonint` only function names that are defined as shell functions in the Upstream_Script, so that no task under `tasks/` calls `do_rgpio`, `do_pixdub`, `do_memory_split`, `do_boot_wait`, or `get_serial`.
3. THE Role SHALL contain no Check_Task, Change_Task, or task tag for Legacy Camera and Remote GPIO in `interface.yml`, Pixel Doubling in `display.yml`, GPU Memory in `performance.yml`, Network at Boot in `system.yml`, or xcompmgr Compositor and Glamor in `advanced.yml`, so that `ansible-playbook --list-tasks` and `ansible-playbook --list-tags` on the Test_Playbook list no task and no tag for these seven Options.
4. IF one or more Deprecated_Variables are defined from any variable source (inventory, play vars, role parameters, or extra vars), THEN THE Role SHALL print, before any Change_Task runs, one warning per defined Deprecated_Variable per Target_Host that names the Deprecated_Variable and the Option it controlled, and states that the trixie Upstream_Script no longer offers the Option.
5. THE Role SHALL contain, in the files under `tasks/` and in `defaults/main.yml`, no `TODO` comment and no commented-out task or variable block that refers to an Option implemented, removed, or deprecated by this feature; `TODO` comments are permitted only for the Options listed as out of scope in the Introduction (A4 Boot Order, A5 Bootloader Version, A9 Network Install UI, A10 Shutdown Behaviour, A14 AB Firmware).
6. THE Role SHALL treat exactly `raspi_config_enable_legacy_camera`, `raspi_config_enable_remote_gpio`, `raspi_config_gpu_memory`, `raspi_config_wait_on_network`, `raspi_config_enable_xcompmgr`, and `raspi_config_enable_glamor` as the Deprecated_Variables, and SHALL define none of them in `defaults/main.yml`.
7. IF a Deprecated_Variable is defined, THEN THE Role SHALL continue the play without failing and SHALL make no change to the Target_Host based on the value of the Deprecated_Variable.
8. WHEN the Role runs against a Target_Host with the values in `defaults/main.yml` and no Deprecated_Variable defined, THE Role SHALL report zero `failed` tasks, zero `ignored` tasks, and zero deprecation warnings in the play recap.

### Requirement 9: System Options - Wireless LAN, Audio, Password, Hostname

**User Story:** As a role user, I want to set Wi-Fi credentials, audio output, the user password, and the hostname, so that my Pi joins my network with the right identity.

#### Acceptance Criteria

1. WHEN `raspi_config_wifi_ssid` is not the Unmanaged_Value and no NetworkManager connection exists on the Target_Host whose SSID and passphrase both equal `raspi_config_wifi_ssid` and `raspi_config_wifi_password`, THE Role SHALL add the SSID and passphrase with `do_wifi_ssid_passphrase`, passing both values verbatim (including spaces and quote characters), and report the Change_Task as `changed`; WHEN such a connection already exists, THE Role SHALL skip the Change_Task and report no `changed` task for Wireless LAN.
2. THE Role SHALL mark every task that handles `raspi_config_wifi_password` or `raspi_config_password` with `no_log: true`, including Check_Tasks, Change_Tasks, and Validation_Tasks, so that neither value appears in task output, failure messages, or verbose (`-vvv`) output.
3. IF `raspi_config_wifi_ssid` is not the Unmanaged_Value and `raspi_config_wifi_country` is the Unmanaged_Value, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message stating that a WLAN country is required for Wireless LAN.
4. WHERE `raspi_config_audio_output` is not the Unmanaged_Value, WHEN the Current_State of the audio output differs from `raspi_config_audio_output`, THE Role SHALL set the audio output with `do_audio`, where the accepted values are the integer output numbers (0 or greater) that the Upstream_Script audio menu lists on the Target_Host; IF `raspi_config_audio_output` is not one of the listed output numbers, THEN THE Role SHALL fail the Option without changing the audio output, with a message naming the given value and the output numbers available on the Target_Host.
5. WHERE `raspi_config_audio_output` is not the Unmanaged_Value, WHILE a PulseAudio or PipeWire process is running on the Target_Host at the time the audio Check_Task runs, THE Role SHALL skip the audio Change_Task without failing the play and print a message stating that audio is controlled by the desktop sound server.
6. WHEN `raspi_config_password` is not the Unmanaged_Value and the stored password hash of `raspi_config_user` does not verify against `raspi_config_password`, THE Role SHALL set the password of `raspi_config_user` and report the password task as `changed`.
7. WHEN the Role runs twice in a row against the same Target_Host with the same `raspi_config_user` and `raspi_config_password` values, THE Role SHALL report the password task as `ok` on the second run.
8. WHEN the output of `get_hostname` differs from `raspi_config_hostname`, THE Role SHALL set the hostname with `do_hostname`, report the Change_Task as `changed`, and notify the Reboot_Handler; WHEN the output of `get_hostname` equals `raspi_config_hostname`, THE Role SHALL skip the Change_Task and not notify the Reboot_Handler.
9. THE Role SHALL set `raspi_config_password` to the Unmanaged_Value in `defaults/main.yml`.
10. IF `raspi_config_wifi_ssid` is not the Unmanaged_Value and is longer than 32 bytes, or `raspi_config_wifi_password` is not the Unmanaged_Value and is shorter than 8 or longer than 63 characters, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the Role_Variable and the accepted length range, without including the passphrase value.
11. IF `raspi_config_hostname` is empty, longer than 63 characters, contains characters other than ASCII letters, digits, and hyphens, or starts or ends with a hyphen, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the given value and the hostname rules.
12. IF `raspi_config_password` is not the Unmanaged_Value and `raspi_config_user` does not exist on the Target_Host, THEN THE Role SHALL fail the password Option without creating the user, with a message naming `raspi_config_user`.

### Requirement 10: System Options - Boot target and Auto Login

**User Story:** As a role user, I want to choose console or desktop boot and auto login separately, so that the role matches the trixie S5 and S6 menu entries.

#### Acceptance Criteria

1. THE Role SHALL accept exactly `console` and `desktop` as values of `raspi_config_boot_behavior`, and exactly the booleans `true` and `false` as values of `raspi_config_enable_console_autologin` and `raspi_config_enable_desktop_autologin`, and THE Validation_Task SHALL reject any other value of these three Role_Variables as described in Requirement 5.
2. WHEN `raspi_config_boot_behavior` is `desktop` or `raspi_config_enable_desktop_autologin` is `true`, and the `lightdm` package is absent on the Target_Host, THE Role SHALL install `lightdm` before the boot target Change_Task and the desktop auto login Change_Task run, and SHALL report the install task as `ok` when `lightdm` is already installed.
3. WHEN the output of `get_boot_cli` (`0` for console, `1` for desktop) differs from the value that matches `raspi_config_boot_behavior`, THE Role SHALL set the boot target with `do_boot_target`, report the boot target Change_Task as `changed`, and notify the Reboot_Handler; when the output equals the matching value, THE Role SHALL skip the boot target Change_Task and not notify the Reboot_Handler.
4. WHEN the console auto login Current_State reported by `get_autologin_cli` differs from `raspi_config_enable_console_autologin`, THE Role SHALL set console auto login with `do_autologin`, report the console auto login Change_Task as `changed`, and notify the Reboot_Handler; when the Current_State equals `raspi_config_enable_console_autologin`, THE Role SHALL skip the console auto login Change_Task and not notify the Reboot_Handler.
5. WHEN the desktop auto login Current_State reported by `get_autologin_desktop` differs from `raspi_config_enable_desktop_autologin`, THE Role SHALL set desktop auto login with `do_autologin`, report the desktop auto login Change_Task as `changed`, and notify the Reboot_Handler; when the Current_State equals `raspi_config_enable_desktop_autologin`, THE Role SHALL skip the desktop auto login Change_Task and not notify the Reboot_Handler.
6. IF `raspi_config_boot_behavior` holds `console_autologin` or `desktop_autologin`, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message that names the given value and names `raspi_config_enable_console_autologin` and `raspi_config_enable_desktop_autologin` as the Role_Variables that replace it.
7. IF the `lightdm` installation fails, THEN THE Role SHALL fail the Target_Host before the boot target Change_Task and the desktop auto login Change_Task run, with a message indicating that `lightdm` could not be installed, and SHALL leave the boot target and auto login settings unchanged.
8. IF `raspi_config_enable_desktop_autologin` is `false` and the `lightdm` package is absent on the Target_Host, THEN THE Role SHALL skip the desktop auto login Check_Task and Change_Task and report both as skipped.

### Requirement 11: System Options - Splash Screen, Power LED, Browser, Admin Password

**User Story:** As a role user, I want to manage the splash screen, power LED, default browser, and sudo password, so that every System Options entry is covered.

#### Acceptance Criteria

1. WHEN the output of `get_boot_splash` differs from `raspi_config_enable_boot_splash_screen`, and either `raspi_config_enable_boot_splash_screen` is `false` or the splash screen theme file `/usr/share/plymouth/themes/pix/pix.script` is present on the Target_Host, THE Role SHALL set the splash screen with `do_boot_splash`. The Role SHALL treat a `get_boot_splash` output of 0 as enabled and 1 as disabled.
2. IF `raspi_config_enable_boot_splash_screen` is `true` and the splash screen theme file `/usr/share/plymouth/themes/pix/pix.script` is absent on the Target_Host, THEN THE Role SHALL skip the splash screen Change_Task without failing the play, print a message stating that the splash screen is not installed, and leave the boot command line unchanged.
3. WHEN the output of `get_leds` is 0 or 1 and differs from `raspi_config_power_led_flash_during_activity`, THE Role SHALL set the Power LED behaviour with `do_leds`. The Role SHALL treat a `get_leds` output of 0 as "flash during activity" (`true`) and 1 as "always on" (`false`). The Role SHALL handle an output of -1 as defined in Requirement 6, criterion 4.
4. WHERE `raspi_config_browser` is not the Unmanaged_Value, WHEN the output of `get_browser` for `raspi_config_user` differs from `raspi_config_browser`, THE Role SHALL set the default browser for `raspi_config_user` with `do_browser`. The accepted values of `raspi_config_browser` are `chromium` and `firefox`.
5. WHEN the output of `get_sudo_pass` differs from `raspi_config_enable_sudo_password`, THE Role SHALL set the sudo password requirement for `raspi_config_user` with `do_sudo_pass`. The Role SHALL treat a `get_sudo_pass` output of 0 as "password required" (`true`) and 1 as "no password required" (`false`).
6. IF `raspi_config_browser` is not the Unmanaged_Value and the browser it names is not installed on the Target_Host, THEN THE Role SHALL fail the browser Option before `do_browser` runs, with a message naming the requested browser, and leave the default browser of `raspi_config_user` unchanged.
7. IF `raspi_config_user` does not name an existing account on the Target_Host, THEN THE Role SHALL fail before the browser and sudo password Change_Tasks run, with a message naming `raspi_config_user` and the given value, and leave the browser and sudo settings unchanged.

### Requirement 12: Display Options

**User Story:** As a role user, I want to manage underscan, blanking, VNC resolution, composite output, 4Kp60, and the on-screen keyboard, so that every Display Options entry is covered.

#### Acceptance Criteria

1. WHEN the output of `get_overscan_kms` for an HDMI output that the Pi_Model provides (HDMI-1 on every Pi_Model, HDMI-2 on Pi_Model 4 and 5) differs from the Desired_State of that HDMI output, THE Role SHALL set overscan compensation for that HDMI output with `do_overscan_kms`, where `raspi_config_underscan_outputs` is a list of 0 to 2 unique entries from `HDMI-1` and `HDMI-2`, an HDMI output listed in `raspi_config_underscan_outputs` has the Desired_State "overscan compensation enabled", an HDMI output not listed has the Desired_State "overscan compensation disabled", and the default value is the empty list.
2. WHEN the output of `get_blanking` (0 = enabled, 1 = disabled) differs from `raspi_config_enable_screen_blanking`, THE Role SHALL set screen blanking with `do_blanking` and notify the Reboot_Handler.
3. WHEN the output of `get_vnc_resolution` differs from `raspi_config_vnc_resolution`, THE Role SHALL set the VNC resolution with `do_vnc_resolution` and notify the Reboot_Handler, where the accepted values are `640x480`, `720x480`, `800x600`, `1024x768`, `1280x720`, `1280x1024`, `1600x1200`, and `1920x1080`.
4. WHERE the Pi_Model is one of the Pi_Model values for which the Upstream_Script display menu offers the D4 Composite Option, WHEN the output of `get_composite` (0 = enabled, 1 = disabled) differs from `raspi_config_enable_composite_video`, THE Role SHALL set composite output with `do_composite` and notify the Reboot_Handler.
5. WHERE the Pi_Model is 4, WHEN the output of `get_pi4video` (0 = enabled, 1 = disabled) differs from `raspi_config_enable_hdmi_4kp60`, THE Role SHALL set 4Kp60 HDMI output with `do_pi4video` and notify the Reboot_Handler.
6. WHEN the on-screen keyboard mode reported by `get_squeekboard` differs from `raspi_config_onscreen_keyboard`, THE Role SHALL set the on-screen keyboard mode with `do_squeekboard`, where the accepted values are `always_on`, `autodetect`, and `always_off`.
7. WHERE `raspi_config_onscreen_keyboard_output` is not the Unmanaged_Value, WHEN the output of `get_squeek_output` differs from `raspi_config_onscreen_keyboard_output`, THE Role SHALL set the on-screen keyboard output with `do_squeek_output`, where the accepted value is the non-empty name of a display output on the Target_Host.
8. IF the `squeekboard` command is absent on the Target_Host, THEN THE Role SHALL skip the Check_Tasks and Change_Tasks of the Onscreen Keyboard (D6) and Keyboard Output (D7) Options and print a message stating that the on-screen keyboard is not installed on the Target_Host.
9. IF `raspi_config_underscan_outputs` contains `HDMI-2` and the Pi_Model is not 4 or 5, THEN THE Role SHALL skip the HDMI-2 overscan Check_Task and Change_Task and print a message naming `HDMI-2` and the detected Pi_Model.
10. IF a Display Options Change_Task exits with a non-zero return code, THEN THE Role SHALL fail that Option with a message that names the `do_*` function and includes the error output of the function, and SHALL NOT notify the Reboot_Handler from that Change_Task.

### Requirement 13: Interface Options

**User Story:** As a role user, I want to manage SSH, Raspberry Pi Connect, VNC, SPI, I2C, serial, and 1-Wire, so that every Interface Options entry is covered.

#### Acceptance Criteria

1. WHEN the output of `get_ssh`, `get_vnc`, `get_spi`, `get_i2c`, or `get_onewire` differs from the matching Role_Variable (`raspi_config_enable_ssh`, `raspi_config_enable_vnc`, `raspi_config_enable_spi`, `raspi_config_enable_i2c`, or `raspi_config_enable_one_wire`), THE Role SHALL set that interface with the matching `do_*` function, where a Check_Task output of `0` matches the Role_Variable value `true` and a Check_Task output of `1` matches the Role_Variable value `false`.
2. WHEN the Role runs the 1-Wire Change_Task, THE Role SHALL notify the Reboot_Handler.
3. WHEN the output of `get_rpi_connect` differs from the state that matches `raspi_config_rpi_connect`, THE Role SHALL set Raspberry Pi Connect for `raspi_config_user` with `do_rpi_connect`, where the accepted values are `off`, `remote_shell`, and `screen_sharing`.
4. WHEN the output of `get_serial_cons` differs from `raspi_config_enable_serial_console`, THE Role SHALL set the serial login console with `do_serial_cons` and notify the Reboot_Handler, where a Check_Task output of `0` matches `true` and a Check_Task output of `1` matches `false`.
5. WHEN the output of `get_serial_hw` differs from `raspi_config_enable_serial_hardware`, THE Role SHALL set the serial port hardware with `do_serial_hw` and notify the Reboot_Handler, where a Check_Task output of `0` matches `true` and a Check_Task output of `1` matches `false`.
6. IF `raspi_config_enable_serial_console` is `true` and `raspi_config_enable_serial_hardware` is `false`, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message stating that the serial console requires the serial hardware.
7. IF `raspi_config_rpi_connect` is `remote_shell` or `screen_sharing` and neither the `rpi-connect` package nor the `rpi-connect-lite` package is installed on the Target_Host, THEN THE Role SHALL skip the Raspberry Pi Connect Change_Task and print a message stating that Raspberry Pi Connect is not installed.
8. IF `raspi_config_rpi_connect` is `screen_sharing` and the `rpi-connect-lite` package is installed while the `rpi-connect` package is absent, THEN THE Role SHALL skip the Raspberry Pi Connect Change_Task and print a message stating that screen sharing requires the `rpi-connect` package.
9. IF an Interface Options Change_Task exits with a non-zero return code, THEN THE Role SHALL fail that Option on the Target_Host with a message that includes the return code and the error output of the `do_*` function, and SHALL NOT notify the Reboot_Handler from that Change_Task.

### Requirement 14: Performance Options

**User Story:** As a role user, I want to manage overclocking, the overlay file system, the case fan, and the USB current limit, so that every Performance Options entry is covered.

#### Acceptance Criteria

1. WHERE the Pi_Model is 1 or 2, WHEN the overclock profile whose `arm_freq` value matches the `arm_freq` value in `/boot/firmware/config.txt` on the Target_Host differs from `raspi_config_overclock_settings`, THE Role SHALL set the overclock profile with `do_overclock` and notify the Reboot_Handler, where a missing `arm_freq` entry counts as the profile `None` and the profile values are the `arm_freq` values that `do_overclock` writes for each profile.
2. WHEN the overlay file system state reported by `get_overlay_conf` (0 = enabled, 1 = disabled) differs from `raspi_config_enable_overlayfs` (`true` = enabled, `false` = disabled), THE Role SHALL set the overlay file system with `do_overlayfs` and notify the Reboot_Handler.
3. WHERE the Pi_Model is 4, WHEN `raspi_config_enable_gpio_fan` is `true` and at least one of these holds: `get_fan` reports the fan as disabled, the output of `get_fan_gpio` differs from `raspi_config_gpio_fan_pin`, or the output of `get_fan_temp` differs from `raspi_config_gpio_fan_temp` when both are compared as whole degrees Celsius, THE Role SHALL enable the fan with `do_fan` using `raspi_config_gpio_fan_pin` and `raspi_config_gpio_fan_temp` and notify the Reboot_Handler.
4. WHERE the Pi_Model is 5, WHEN the USB current limit state reported by `get_usb_current` differs from `raspi_config_enable_usb_current_limit`, THE Role SHALL set the USB current limit with `do_usb_current` and notify the Reboot_Handler, where `true` means the default USB current limit applies (the Fresh_Install_Default) and `false` means the limit is removed.
5. WHERE the Pi_Model is 4, WHEN `raspi_config_enable_gpio_fan` is `false` and `get_fan` reports the fan as enabled, THE Role SHALL disable the fan with `do_fan` and notify the Reboot_Handler, and THE Role SHALL ignore the outputs of `get_fan_gpio` and `get_fan_temp` when it decides whether to report `changed`.
6. IF `raspi_config_overclock_settings` is not accepted for the detected Pi_Model (Pi_Model 1: `None`, `Modest`, `Medium`, `High`, `Turbo`; Pi_Model 2: `None`, `High`), THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming `raspi_config_overclock_settings`, the given value, the detected Pi_Model, and the values accepted for that Pi_Model.

### Requirement 15: Localisation Options

**User Story:** As a role user, I want to manage locale, time zone, keyboard layout, and WLAN country, so that every Localisation Options entry is covered.

#### Acceptance Criteria

1. WHERE `raspi_config_locale` is not the Unmanaged_Value, WHEN the `LANG` value read from the contents of `/etc/default/locale` is absent or differs from `raspi_config_locale` (for example `en_GB.UTF-8`) by exact, case-sensitive string comparison, THE Role SHALL set the locale with `do_change_locale`, where the Check_Task reads the `LANG` value from the file and not from the `LANG` environment variable of the Ansible connection.
2. WHERE `raspi_config_time_zone` is not the Unmanaged_Value, WHEN `/etc/timezone` is absent or its first line, with leading and trailing whitespace removed, differs from `raspi_config_time_zone` (for example `Europe/London`) by exact, case-sensitive string comparison, THE Role SHALL set the time zone with `do_change_timezone`.
3. WHERE `raspi_config_keyboard_layout` is not the Unmanaged_Value, WHEN `/etc/default/keyboard` has no `XKBLAYOUT` line, or the `XKBLAYOUT` value with surrounding quotes removed differs from `raspi_config_keyboard_layout` (for example `gb`) by exact, case-sensitive string comparison, THE Role SHALL set the keyboard layout with `do_configure_keyboard`.
4. WHERE `raspi_config_wifi_country` is not the Unmanaged_Value, WHEN the output of `get_wifi_country`, with leading and trailing whitespace removed, is empty or differs from `raspi_config_wifi_country` (a two-letter uppercase code, for example `GB`), THE Role SHALL set the WLAN country with `do_wifi_country`.
5. IF `do_change_locale`, `do_change_timezone`, `do_configure_keyboard`, or `do_wifi_country` exits with a non-zero status, THEN THE Role SHALL fail the Target_Host with a message that names the Option and includes the command output, and SHALL run no further Change_Tasks on that Target_Host.
6. IF `raspi_config_keyboard_layout` is not the Unmanaged_Value and is not a layout code in the XKB layout list installed on the Target_Host, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message naming the given value.

### Requirement 16: Advanced Options - file system, network, and desktop

**User Story:** As a role user, I want to manage root file system expansion, interface names, proxies, beta access, the Wayland backend, logging, WLAN power save, and link-local fallback, so that the non-bootloader Advanced Options entries are covered.

#### Acceptance Criteria

1. WHERE `raspi_config_expand_filesystem` is `true`, WHEN `get_can_expand` returns 0 (the root partition can be expanded) and the boot device has at least 1 MiB of unallocated space after the root partition, THE Role SHALL expand the root file system with `do_expand_rootfs` and notify the Reboot_Handler.
2. WHEN the output of `get_net_names` differs from the value that matches `raspi_config_enable_predictable_net_names`, THE Role SHALL set predictable network interface names with `do_net_names` and notify the Reboot_Handler. The output 0 matches `true` (enabled) and 1 matches `false` (disabled), following the Upstream_Script convention.
3. WHERE a proxy Role_Variable for the `http`, `https`, `ftp`, `rsync`, or `no` scheme is not the Unmanaged_Value, WHEN the output of `get_proxy` for that scheme is not an exact string match for the Role_Variable value, THE Role SHALL set the proxy for that scheme with `do_proxy`. The proxy Check_Tasks and Change_Tasks SHALL be marked `no_log: true`.
4. WHEN the presence of `/etc/apt/sources.list.d/beta.list` differs from `raspi_config_enable_beta_access`, THE Role SHALL set beta access with `do_beta_mode` and notify the Reboot_Handler. A file that is present matches `true` and a file that is absent matches `false`.
5. WHILE `/etc/lightdm/lightdm.conf` exists on the Target_Host, WHEN the `user-session` value in that file differs from the session name that `do_wayland` writes for `raspi_config_desktop_backend`, THE Role SHALL set the desktop backend with `do_wayland` and notify the Reboot_Handler. The accepted values are `x11` and `labwc`, and a missing `user-session` key counts as a difference.
6. WHEN the `Storage` value in `/etc/systemd/journald.conf.d/80-raspi-config-journal-storage.conf` differs from `raspi_config_log_storage`, THE Role SHALL set the log storage location with `do_journald_storage`. The accepted values are `default`, `volatile`, `persistent`, `auto`, and `none`, and a missing file or a missing `Storage` key counts as `default`.
7. WHEN the Target_Host has at least one network interface that the kernel reports as wireless and the output of `get_wifi_power_save` differs from the value that matches `raspi_config_enable_wifi_power_save`, THE Role SHALL set WLAN power saving with `do_wifi_power_save`. The output 0 matches `true` (enabled) and 1 matches `false` (disabled).
8. WHEN the output of `get_link_local_fallback` differs from the value that matches `raspi_config_enable_link_local_fallback`, THE Role SHALL set link-local fallback with `do_link_local_fallback` and notify the Reboot_Handler. The output 0 matches `true` (enabled) and 1 matches `false` (disabled).
9. IF a proxy Role_Variable that is not the Unmanaged_Value contains a whitespace character or is longer than 2048 characters, THEN THE Validation_Task SHALL fail the play before any Change_Task runs, with a message that names the Role_Variable and does not print its value.
10. IF `/etc/lightdm/lightdm.conf` is absent on the Target_Host, THEN THE Role SHALL skip the desktop backend Check_Task and Change_Task and print a message stating that no LightDM desktop is installed on the Target_Host.
11. IF the Target_Host has no network interface that the kernel reports as wireless, THEN THE Role SHALL skip the WLAN power save Check_Task and Change_Task and print a message stating that the Target_Host has no WLAN interface.

### Requirement 17: Advanced Options - PCIe speed

**User Story:** As a Pi 5 user, I want to choose the PCIe speed, so that I can enable PCIe Gen 3 for an attached NVMe drive or HAT.

#### Acceptance Criteria

1. WHERE the Pi_Model is 5, WHEN `raspi_config_enable_pcie_gen3` is `true` and the output of `get_pci` is 1 (PCIe Gen 3 disabled), THE Role SHALL enable PCIe Gen 3 with `do_pci 0`, report the Change_Task as `changed`, and notify the Reboot_Handler.
2. WHERE the Pi_Model is 5, WHEN `raspi_config_enable_pcie_gen3` is `false` and the output of `get_pci` is 0 (PCIe Gen 3 enabled), THE Role SHALL disable PCIe Gen 3 with `do_pci 1`, report the Change_Task as `changed`, and notify the Reboot_Handler.
3. IF the Pi_Model is not 5, THEN THE Role SHALL skip the PCIe speed Check_Task and Change_Tasks, and, if `raspi_config_enable_pcie_gen3` is `true`, print a message naming the PCIe Speed Option and the detected Pi_Model.
4. IF the output of `get_pci` on a Target_Host with Pi_Model 5 is a value other than 0 or 1, THEN THE Role SHALL fail the PCIe Speed Option without running `do_pci`, with a message that includes the `get_pci` output.

### Requirement 18: Disable raspi-config at first boot

**User Story:** As a role user, I want the role to stop the interactive raspi-config prompt from appearing on the console, so that a configured Pi boots straight to the login prompt.

#### Acceptance Criteria

1. WHEN `/etc/profile.d/raspi-config.sh` or `/etc/systemd/system/getty@tty1.service.d/raspi-config-override.conf` exists on the Target_Host, THE Role SHALL delete each of the two files that exists, leave the `/etc/systemd/system/getty@tty1.service.d/` directory and every other file in that directory in place, and report the removal task as `changed`.
2. WHEN neither `/etc/profile.d/raspi-config.sh` nor `/etc/systemd/system/getty@tty1.service.d/raspi-config-override.conf` exists on the Target_Host, THE Role SHALL report the removal task as `ok`, leave the Target_Host unmodified, and skip the systemd reload in criterion 3.
3. WHEN the Role deletes `/etc/systemd/system/getty@tty1.service.d/raspi-config-override.conf`, THE Role SHALL reload the systemd manager configuration on the Target_Host before the play ends, so that `systemctl cat getty@tty1.service` no longer lists the deleted override file.
4. WHILE Ansible runs in check mode, THE Role SHALL report the removal task as `changed` if either file exists on the Target_Host, without deleting either file or reloading the systemd manager configuration.
5. IF the Role cannot delete an existing file (for example, because of insufficient privileges or a read-only file system), THEN THE Role SHALL fail the play for that Target_Host with a message that names the path of the file and the reason for the failure.

### Requirement 19: Documentation

**User Story:** As a role user, I want the README to list every variable and tag, so that I can configure the role without reading the task files.

#### Acceptance Criteria

1. THE README SHALL list every Role_Variable defined in `defaults/main.yml`, and no other variable names. For each Role_Variable, the README SHALL give the Upstream_Script menu number (for example `I1`), the accepted values or accepted range, a default value identical to the value in `defaults/main.yml`, and the Pi_Model values of the Option's Model_Gate. For Options without a Model_Gate, the README SHALL state that the Option applies to all Pi_Model values.
2. THE README SHALL list the Deprecated_Variable of each removed Option (Legacy Camera, Remote GPIO, Pixel Doubling, GPU Memory, Network at Boot, xcompmgr Compositor, and Glamor). For each one, the README SHALL state that the trixie Upstream_Script no longer offers the Option and that the Role prints a warning when the Deprecated_Variable is defined.
3. THE README SHALL state that the Unmanaged_Value is the empty string `""`, that the Role skips the Check_Tasks and Change_Tasks of any Option whose Role_Variable holds the Unmanaged_Value, and which Role_Variables default to the Unmanaged_Value.
4. THE README SHALL state that the Role supports Raspberry Pi OS trixie only. THE README SHALL name a minimum Ansible version identical to the version declared in `meta/main.yml`.
5. THE README SHALL contain an example playbook that applies the role `tkeemon.raspi_config` with `become: true` and sets at least one Role_Variable.
6. WHEN every Option in the trixie Upstream_Script menus is implemented, except the out-of-scope Options A4 Boot Order, A5 Bootloader Version, A9 Network Install UI, A10 Shutdown Behaviour, and A14 AB Firmware, THE README SHALL contain no "work in progress" warning.
7. THE README SHALL contain a breaking-changes section that lists each Renamed_Variable, each removed value of `raspi_config_boot_behavior` (`console_autologin` and `desktop_autologin`), each Deprecated_Variable, and the removed `raspi_config_password` default. Each entry SHALL name the Role_Variables or values that replace it.
8. THE README SHALL describe the Tag_Convention. It SHALL list the `raspi_config` tag, the `raspi_config:SUBMENU_NAME` tag for each of the six Submenu_Files, and the base tag `raspi_config:SUBMENU_NAME:TASK_NAME` of every Option. For every boolean enable/disable Option, it SHALL also list the `:enable` and `:disable` tags.
9. THE README SHALL state that `raspi_config_allow_reboot` defaults to `false`, that a value of `true` reboots the Target_Host and waits for it to reconnect, and that a value of `false` makes the Role print a message that a reboot is needed. THE README SHALL also list every Option whose Change_Task notifies the Reboot_Handler.

### Requirement 20: Linting and automated checks

**User Story:** As a role maintainer, I want CI to catch style errors and broken syntax, so that pull requests do not break the role.

#### Acceptance Criteria

1. WHEN a pull request is opened, reopened, or updated with new commits, or a commit is pushed to `master`, THE CI_Pipeline SHALL run `yamllint` with the repository `.yamllint` configuration and `ansible-lint` with the production profile against every YAML file in the repository checkout of the commit under test.
2. THE Role SHALL produce zero error-level problems when checked by `yamllint` with the repository `.yamllint` configuration and zero rule violations when checked by `ansible-lint` with the production profile.
3. WHEN a pull request is opened, reopened, or updated with new commits, or a commit is pushed to `master`, THE CI_Pipeline SHALL run `ansible-playbook --syntax-check` against the Test_Playbook with the Test_Inventory, resolving the Role from the repository checkout of the commit under test and without connecting to any Target_Host.
4. THE CI_Pipeline SHALL reference, for `actions/checkout` and `actions/setup-python`, the latest major version that each action has published at the time of the change, such that the workflow run log contains no deprecation warning for either action.
5. IF `yamllint` reports an error-level problem, `ansible-lint` reports a rule violation, or `ansible-playbook --syntax-check` exits with a non-zero status, THEN THE CI_Pipeline SHALL mark the workflow run as failed and show the name of the failed step in the pull request checks.
6. THE CI_Pipeline SHALL install `yamllint`, `ansible-lint`, and Ansible from the repository `requirements.txt`, so that a maintainer who installs the same file locally runs the checks with the same packages.

### Requirement 21: Hardware test playbook

**User Story:** As a role maintainer, I want a test playbook that proves idempotence on a real Pi, so that I can verify each option before a release.

#### Acceptance Criteria

1. THE Test_Playbook SHALL run the Role with `become: true` against every Target_Host listed in the Test_Inventory.
2. WHEN the maintainer runs the Test_Playbook, THE Test_Playbook SHALL apply the Role to each Target_Host twice in succession with identical Role_Variable values, and SHALL finish any Reboot_Handler run triggered by the first application before the second application starts.
3. WHEN the maintainer runs the Test_Playbook with `--tags` set to one Tag_Convention tag of the form `raspi_config:SUBMENU_NAME:TASK_NAME`, THE Role SHALL run only the Check_Tasks and Change_Tasks carrying that tag, plus the tasks tagged `always`.
4. WHEN the Test_Playbook has run with the non-default Desired_States from criterion 6 and then runs again with every Role_Variable set to its Fresh_Install_Default, THE Role SHALL leave every Option covered by criterion 6 with a Check_Task output that matches the Fresh_Install_Default (round-trip property). Root file system expansion is excluded because expanding a partition cannot be undone.
5. THE Test_Inventory SHALL define exactly four host groups, one per tested hardware model, each with an expected Pi_Model value: Pi 5 (Pi_Model 5), Pi 4 (Pi_Model 4), Pi 3 (Pi_Model 3), and Pi Zero / Zero 2 W (the value `get_pi_type` reports for the maintainer's Zero hardware, recorded in the Test_Inventory as a group variable).
6. WHEN the Test_Playbook runs against a host group, THE Test_Playbook SHALL set a Desired_State that differs from the Fresh_Install_Default for every Option whose Model_Gate includes the expected Pi_Model of that host group, with these exceptions: SSH stays enabled so that Ansible keeps its connection, and Options whose Role_Variable defaults to the Unmanaged_Value are tested only when the maintainer supplies values for them as extra variables.
7. IF the Pi_Model reported by a Target_Host does not equal the expected Pi_Model of its host group, or the Target_Host belongs to zero or more than one of the four host groups, THEN THE Test_Playbook SHALL fail that Target_Host before any Change_Task runs, with a message naming the Target_Host, the reported Pi_Model, and the expected Pi_Model.
8. THE Test_Playbook SHALL set `raspi_config_allow_reboot` to `true`, and SHALL fail any Target_Host that does not reconnect within 600 seconds after a reboot.
9. IF any task of the second Role application from criterion 2 reports `changed`, THEN THE Test_Playbook SHALL fail that Target_Host after the second application finishes.
10. IF the Check_Task output of any Option covered by criterion 4 does not match the Fresh_Install_Default after the restore run, THEN THE Test_Playbook SHALL fail that Target_Host with a message naming the Option, the Check_Task output, and the expected Fresh_Install_Default.
