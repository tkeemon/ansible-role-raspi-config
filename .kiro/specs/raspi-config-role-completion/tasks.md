# Implementation Plan: raspi-config-role-completion

## Overview

The plan completes `tkeemon.raspi_config` against the trixie Upstream_Script in the phases set by the requirements Introduction. Implementation is Ansible YAML (tasks, vars, defaults, handlers, GitHub Actions) plus Python (pytest + Hypothesis) for the controller-side tests in `tests/unit/`.

- **Phase 1 (tasks 1 to 12):** shared foundations (metadata, data tables, defaults, preflight, validation, deprecations, handlers, first-boot removal, `tasks/main.yml`), removal of obsolete Options and placeholder tasks, and conversion of every Option the Role already implements to the check-then-change pattern. Phase 1 converts all existing Options, not only the visibly broken ones: the old `command` tasks report `skipped` in check mode (breaks Requirement 2.6), and several read Role_Variables that Phase 1 renames or whose defaults it changes. Converting them all keeps the structural tests in task 11 green from Phase 1 onward.
- **Phases 2 to 7 (tasks 13 to 25):** the Options the Role does not implement yet, one submenu per phase: System, Display, Interface, Performance, Localisation, Advanced.
- **Phase 8 (tasks 26 and 27):** README, CI, and the hardware Test_Playbook.

Clarifications C1 to C13 follow the design's recommended resolutions. C5 (Raspberry Pi Connect `remote_shell`) is left open by the design, so task 17 is a decision checkpoint before I2. The other Interface Options are converted in Phase 1 and do not wait on that decision.

Every Option uses the pattern from the design: a `block` carrying the base tag `raspi_config:SUBMENU:TASK`, one Check_Task, one Change_Task per direction using `raspi_config__noop_argv` in check mode, a Verify_Task, a `rescue` that fails the host with the Option, rc, stdout, and stderr, and a gate or skip message task where the design lists one. Boolean Options add the `:enable` and `:disable` suffix tags on inner tasks only. All code must pass `ansible-lint --profile production`.

## Tasks

- [ ] 1. Phase 1: Set up role metadata, dependencies, and the controller-side test harness
  - [-] 1.1 Update `meta/main.yml` and `requirements.txt`
    - In `meta/main.yml`, set `min_ansible_version: "2.18"` and list Debian as the only platform with `trixie` as the only version
    - In `requirements.txt`, pin `ansible-core` (>= 2.18), `ansible-lint`, `yamllint`, `passlib`, `pytest`, and `hypothesis`; choose an `ansible-lint` version whose `schema[meta]` accepts `trixie`
    - _Requirements: 1.1, 1.2, 20.6_

  - [-] 1.2 Create the pytest and Hypothesis harness in `tests/unit/`
    - `tests/unit/conftest.py`: fixtures that load `defaults/main.yml` and `vars/main.yml`, build an ansible-core `Templar` with those variables plus generated inputs, and render named expressions, `when` lists, `argv` templates, and `fail_msg` strings read from the parsed task files
    - A task-file parser helper that flattens every file under `tasks/` into tasks with their effective tags (import tags from `tasks/main.yml`, block tags, task tags, `always`), `notify`, `no_log`, `environment`, and enclosing block
    - `tests/unit/strategies.py` with the strategies from the design's Testing Strategy table (`yaml_values`, `enum_values`, `hostnames`, `ssids`, `psks`, reference-file generators, `proxy_values`, `check_results`, `pi_models`, `board_types`, `kv_files`, `deprecated_subsets`)
    - A Hypothesis settings profile with `max_examples=100` as the minimum
    - `tests/unit/fixtures/raspi-config-trixie`: pinned copy of the Upstream_Script with the upstream commit hash in a header comment
    - _Requirements: 8.2, 20.6_

  - [~] 1.3 Write example tests for role metadata
    - `tests/unit/test_meta.py`: platforms list is exactly Debian/`trixie`; `min_ansible_version` is `"2.18"`
    - _Requirements: 1.1, 1.2_

- [ ] 2. Phase 1: Create internal data tables and restructure the defaults
  - [~] 2.1 Create the data tables in `vars/main.yml`
    - Add `raspi_config__noop_argv`, `raspi_config__all_models`, `raspi_config__option_models`, `raspi_config__board_exclusions`, `raspi_config__options` (menu, submenu, variable, `true_output`, `reboot`), `raspi_config__enums`, `raspi_config__overclock_profiles`, `raspi_config__log_storage_codes`, `raspi_config__squeekboard_codes` with its reverse map, `raspi_config__fresh_install_defaults`, `raspi_config__deprecated_variables` (six entries), and `raspi_config__renamed_variables` (two entries)
    - Set `true_output` `'1'` for P4, A12 (C1), and A13 (C2), and `'0'` for the other boolean Options listed in the design
    - Set `reboot` flags from the design's reboot list; P4 stays `false` (C3)
    - Define no Deprecated_Variable or Renamed_Variable as a variable (names appear only as list data)
    - _Requirements: 4.1, 4.7, 5.7, 6.1, 7.1, 7.8, 8.6_

  - [~] 2.2 Rewrite `defaults/main.yml`
    - Non-Option variables first (`raspi_config_user: ""`, `raspi_config_allow_reboot: false`), then the six submenu groups in menu order, with the values from the design's Data Models table (Lite image baseline, C8; `raspi_config_enable_ssh: true`, C7)
    - Comment lines directly above each variable: menu number, accepted values or reference file, whether `""` is accepted, and Pi_Model values or `all`
    - Remove the six Deprecated_Variables, `raspi_config_enable_serial_port`, `raspi_config_enable_wayland`, the `raspberry` password default, and the `*_autologin` boot values; add `raspi_config_enable_serial_console`, `raspi_config_enable_serial_hardware`, `raspi_config_desktop_backend`, the two auto login booleans, and every new Option variable
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 4.7, 7.4, 8.6, 9.9, 10.1, 12.1_

  - [~] 2.3 Write unit tests for defaults and data tables
    - `tests/unit/test_defaults.py`: `raspi_config__fresh_install_defaults` equals `defaults/main.yml`; group and menu order; the Unmanaged_Value defaults of 4.3; `raspi_config_allow_reboot` is `false`; the deprecated list is exactly the six names; `raspi_config__option_models` matches the trixie menu gates in the pinned Upstream_Script
    - _Requirements: 4.3, 4.6, 6.1, 7.4, 8.6, 9.9_

  - [~] 2.4 Write property test for value maps
    - `tests/unit/test_p21_value_maps.py`
    - **Property 21: Value maps round-trip**
    - **Validates: Requirements 12.6, 14.1, 16.6**

- [ ] 3. Phase 1: Implement preflight checks
  - [~] 3.1 Create `tasks/preflight.yml`
    - The eight tasks in the design's preflight table, in order: minimal fact gathering when facts are missing, release assertion (`Debian` or `Raspbian`, C10, release `trixie`), `command -v raspi-config`, `get_pi_type` with the -1 / unknown / rc≠0 messages, Pi_Model fact, board type from `/proc/cpuinfo`, user resolution through `getent` (UID 1000 fallback) with `raspi_config__user_env` and `raspi_config__user_home`, and `package_facts`
    - Every `command` task is read-only with `changed_when: false` and `check_mode: false`
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 6.5_

  - [~] 3.2 Write property test for preflight classification
    - `tests/unit/test_p01_preflight.py`
    - **Property 1: Preflight classification**
    - **Validates: Requirements 1.3, 1.6, 1.7, 6.5**

  - [~] 3.3 Write unit tests for preflight order and read-only behaviour
    - `tests/unit/test_preflight_examples.py`: release check before `raspi-config` presence before Pi_Model; no preflight task writes to the host
    - _Requirements: 1.8, 1.9, 6.5_

- [ ] 4. Phase 1: Implement input validation
  - [~] 4.1 Add the validation predicates to `vars/main.yml`
    - Lazily evaluated `raspi_config__valid_*` expressions for: renamed variables, removed `boot_behavior` values, booleans (`is boolean`, no coercion), enumerations, fan ranges, overclock per Pi_Model, hostname, SSID byte length (urlencode expression), passphrase length, SSID-requires-country, composite/4Kp60 exclusivity (C12), underscan list, proxy values, onscreen keyboard output name, and the reference-file predicates (iso3166.tab, SUPPORTED, base.lst, time zone path without `..`)
    - Do not add the serial console/hardware rule (C4)
    - _Requirements: 4.8, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 9.3, 9.10, 9.11, 10.1, 10.6, 12.1, 14.6, 15.6, 16.9_

  - [~] 4.2 Create `tasks/validate.yml`
    - `ansible.builtin.assert` tasks with `quiet: true` and explicit `fail_msg`, ordered as in the design (renamed variables and removed values before the generic enum checks)
    - Host-side reads only when the matching variable is not `""`: `slurp` of `iso3166.tab`, `SUPPORTED`, and `base.lst`; `stat` of `/usr/share/zoneinfo/<value>`; `find` of `/sys/class/drm/card*-<value>`; missing or unreadable file fails with the file path and variable name
    - User existence check against the passwd table from preflight
    - `no_log: true` on Wi-Fi passphrase, password, and proxy tasks; messages name the variable and rule only
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 9.2, 9.3, 9.10, 9.11, 9.12, 10.6, 11.7, 12.7, 14.6, 15.6, 16.9_

  - [~] 4.3 Write property test for enumeration, boolean, range, and per-model validation
    - `tests/unit/test_p07_validation.py`
    - **Property 7: Enumeration, boolean, range, and per-model validation**
    - **Validates: Requirements 4.8, 5.2, 5.3, 5.8, 10.1, 10.6, 14.6**

  - [~] 4.4 Write property test for hostname validation
    - `tests/unit/test_p08_hostname.py`
    - **Property 8: Hostname validation**
    - **Validates: Requirements 9.11**

  - [~] 4.5 Write property test for Wireless LAN validation
    - `tests/unit/test_p09_wlan_validation.py`
    - **Property 9: Wireless LAN validation**
    - **Validates: Requirements 9.2, 9.3, 9.10**

  - [~] 4.6 Write property test for reference-file validation
    - `tests/unit/test_p10_reference_files.py`
    - **Property 10: Reference-file validation**
    - **Validates: Requirements 5.4, 5.5, 5.6, 5.9, 15.6**

  - [~] 4.7 Write property test for proxy validation
    - `tests/unit/test_p11_proxy_validation.py`
    - **Property 11: Proxy validation hides the value**
    - **Validates: Requirements 16.9**

  - [~] 4.8 Write property test for renamed variables
    - `tests/unit/test_p12_renamed.py`
    - **Property 12: Renamed variables always fail**
    - **Validates: Requirements 5.7**

- [ ] 5. Phase 1: Implement deprecation warnings
  - [~] 5.1 Create `tasks/deprecations.yml`
    - One `ansible.builtin.debug` task looping over `raspi_config__deprecated_variables`, detecting each name with `lookup('ansible.builtin.vars', item.name, default='__raspi_config_undefined__')` and printing the `[DEPRECATED]` message; undefined items are skipped and no value is read
    - _Requirements: 8.4, 8.6, 8.7_

  - [~] 5.2 Write property test for deprecation warnings
    - `tests/unit/test_p13_deprecations.py`
    - **Property 13: Deprecation warnings match defined variables**
    - **Validates: Requirements 8.4, 8.6, 8.7**

- [ ] 6. Phase 1: Implement the reboot handler chain and first-boot prompt removal
  - [~] 6.1 Rewrite `handlers/main.yml`
    - Remove the debug placeholder and the `Restart wpa_supplicant` handler
    - Add the `Reboot` handler (`ansible.builtin.reboot`, `reboot_timeout: 600`, `failed_when: false`, only when `raspi_config_allow_reboot` and not check mode), the timeout failure handler, and the pending-reboot message handler (`would need` / `needs`), all listening to `Reboot`, plus `Reload systemd`
    - _Requirements: 2.10, 7.2, 7.3, 7.5, 7.6, 7.7_

  - [~] 6.2 Create `tasks/first_boot.yml`
    - Two `ansible.builtin.file: state: absent` tasks for `/etc/profile.d/raspi-config.sh` and `/etc/systemd/system/getty@tty1.service.d/raspi-config-override.conf`; only the second notifies `Reload systemd`
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [~] 6.3 Write property test for the reboot handler decision
    - `tests/unit/test_p14_reboot_handler.py`
    - **Property 14: Reboot handler decision**
    - **Validates: Requirements 2.10, 7.2, 7.3, 7.6, 7.7**

  - [~] 6.4 Write unit tests for first-boot removal
    - `tests/unit/test_first_boot.py`: exactly the two paths, `state: absent`, only the override file notifies `Reload systemd`, the directory is not removed
    - _Requirements: 18.1, 18.2, 18.3_

- [ ] 7. Phase 1: Rewire `tasks/main.yml`, remove obsolete Options, and add the reference Option
  - [~] 7.1 Rewrite `tasks/main.yml`
    - Orchestration only: `import_tasks` of `preflight.yml`, `validate.yml`, and `deprecations.yml` (tag `always`), the six Submenu_Files (tags `raspi_config` and `raspi_config:SUBMENU`), and `first_boot.yml` (tag `always`)
    - Remove the inline `get_pi_type` and first-boot tasks
    - _Requirements: 1.9, 3.4, 3.5, 3.6, 3.7_

  - [~] 7.2 Remove obsolete Options, placeholder tasks, and stale comments from the six Submenu_Files
    - `interface.yml`: Legacy Camera, Remote GPIO; `display.yml`: Pixel Doubling, Resolution and Underscan placeholders; `performance.yml`: GPU memory split; `system.yml`: Network at Boot, Audio placeholder; `advanced.yml`: xcompmgr, Glamor, and the commented-out GL driver, proxy, boot ROM, and network-config blocks; `localization.yml`: keyboard placeholder
    - Remove every `fail` + `ignore_errors: true` task and every `TODO` or commented-out block for in-scope Options
    - _Requirements: 8.1, 8.2, 8.3, 8.5_

  - [~] 7.3 Implement I1 SSH as the reference check-then-change Option in `tasks/interface.yml`
    - Follow the design's I1 example: block with base tag, Check_Task with `failed_when` on rc and output map, enable/disable Change_Tasks with `raspi_config__noop_argv` in check mode and `when` driven by `raspi_config__options.ssh.true_output`, Verify_Task, rescue
    - Write the `when` and `failed_when` expressions so the harness from 1.2 can render them; later Options copy this shape
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.8, 2.9, 3.1, 3.2, 3.3, 13.1_

- [ ] 8. Phase 1: Convert the existing System Options
  - [~] 8.1 Convert S1 Wireless LAN in `tasks/system.yml`
    - Replace the `wpa_cli` check with the NetworkManager Check_Task (`nmcli`, SSID and passphrase passed through `environment`, prints `0` or `1`); fail with a message when NetworkManager is inactive
    - Change_Task `do_wifi_ssid_passphrase` with SSID and passphrase as separate `argv` elements; `no_log: true` on every task; block skipped when the SSID is `""`
    - _Requirements: 2.1, 4.4, 9.1, 9.2_

  - [~] 8.2 Convert S3 Password in `tasks/system.yml`
    - Check with `getent shadow` and `perl` `crypt()` on the host (`no_log`); Change_Task `ansible.builtin.user` passing the stored hash when it verifies, otherwise a SHA-512 hash with the stable per-host salt (C11)
    - Skip when `raspi_config_password` is `""`; fail without creating the user when it does not exist
    - _Requirements: 2.1, 4.4, 9.2, 9.6, 9.7, 9.12_

  - [~] 8.3 Convert S4 Hostname in `tasks/system.yml`
    - `get_hostname` → `do_hostname`, Change_Task only when the values differ, notify `Reboot`
    - _Requirements: 7.1, 9.8_

  - [~] 8.4 Split S5 Boot and S6 Auto Login in `tasks/system.yml`
    - `lightdm` install task (`ansible.builtin.apt`) when desktop boot or desktop auto login is requested, tagged with the boot and auto login base tags; failure stops the host before S5 and S6
    - S5 `boot_behavior` (`get_boot_cli`, `do_boot_target B1`/`B2`), S6a `console_autologin` and S6b `desktop_autologin` (`get_autologin_cli`, `get_autologin_desktop`, `do_autologin` with the design's code formulas, `environment: raspi_config__user_env`); S6b skipped when `false` and `lightdm` is absent; all notify `Reboot`
    - _Requirements: 3.1, 3.2, 7.1, 10.2, 10.3, 10.4, 10.5, 10.7, 10.8_

  - [~] 8.5 Convert S7 Splash Screen in `tasks/system.yml`
    - Fix the enable condition; `stat` of `/usr/share/plymouth/themes/pix/pix.script`; message and skip when enabling without the theme
    - _Requirements: 11.1, 11.2_

  - [~] 8.6 Convert S8 Power LED in `tasks/system.yml`
    - `get_leds` with output map `0`, `1`, `-1`; `-1` prints the not-supported message (`ok`) and skips the Change_Tasks
    - _Requirements: 6.4, 11.3_

  - [~] 8.7 Write property test for Wi-Fi and password input handling
    - `tests/unit/test_p31_inputs.py`
    - **Property 31: Wi-Fi and password inputs are passed safely**
    - **Validates: Requirements 9.1, 9.7**

  - [~] 8.8 Write property test for auto login codes
    - `tests/unit/test_p22_autologin.py`
    - **Property 22: Auto login codes change only their own part**
    - **Validates: Requirements 10.4, 10.5**

- [ ] 9. Phase 1: Convert the existing Display and Interface Options
  - [~] 9.1 Convert D2 Screen Blanking in `tasks/display.yml`
    - `get_blanking` / `do_blanking` with `environment: raspi_config__user_env`; notify `Reboot`
    - _Requirements: 7.1, 12.2, 12.10_

  - [~] 9.2 Convert D3 VNC Resolution in `tasks/display.yml`
    - Skip when `""`; `get_vnc_resolution` / `do_vnc_resolution`; notify `Reboot`
    - _Requirements: 4.4, 12.3, 12.10_

  - [~] 9.3 Convert D4 Composite in `tasks/display.yml`
    - Board exclusion (Pi 400, Pi 500, CM5) from `raspi_config__board_exclusions` with a gate message task; `get_composite` / `do_composite`; notify `Reboot`
    - _Requirements: 6.2, 6.3, 12.4, 12.10_

  - [~] 9.4 Convert I3 VNC, I4 SPI, I5 I2C, and I7 1-Wire in `tasks/interface.yml`
    - Same shape as I1; I7 notifies `Reboot`
    - _Requirements: 13.1, 13.2, 13.9_

  - [~] 9.5 Replace the broken serial tasks with I6a `serial_console` and I6b `serial_hardware` in `tasks/interface.yml`
    - `get_serial_cons` / `do_serial_cons` and `get_serial_hw` / `do_serial_hw`; both notify `Reboot`; no `get_serial` or `do_serial` call; values applied independently (C4)
    - _Requirements: 8.2, 13.4, 13.5, 13.9_

- [ ] 10. Phase 1: Convert the existing Performance, Localisation, and Advanced Options
  - [~] 10.1 Convert P1 Overclock in `tasks/performance.yml`
    - Model gate (1, 2) with gate message; Check_Task `get_config_var arm_freq /boot/firmware/config.txt` mapped through `raspi_config__overclock_profiles`; unknown `arm_freq` fails; `do_overclock <profile>`; notify `Reboot`; remove the templated task name
    - _Requirements: 2.7, 6.2, 6.3, 14.1_

  - [~] 10.2 Convert P2 Overlay File System in `tasks/performance.yml`
    - One `batch get_overlay_conf get_bootro_conf get_overlay_now` Check_Task; the design's composite state rule (C6); `do_overlayfs 0`/`1`; Verify_Task catches the 256 MB refusal; notify `Reboot`
    - _Requirements: 2.1, 14.2_

  - [~] 10.3 Convert P3 Fan in `tasks/performance.yml`
    - Model gate (4) and Pi 400 board exclusion with gate message; `batch get_fan get_fan_gpio get_fan_temp`; enable when disabled or pin/temp differ, disable when enabled; notify `Reboot`
    - _Requirements: 2.1, 6.2, 6.3, 14.3, 14.5_

  - [~] 10.4 Fix L1 Locale in `tasks/localization.yml`
    - Read `LANG` from `/etc/default/locale` with `slurp` and the design regex, not from the connection environment; `do_change_locale`; skip when `""`
    - _Requirements: 4.4, 15.1, 15.5_

  - [~] 10.5 Convert L2 Time zone in `tasks/localization.yml`
    - `stat` of `/etc/localtime` (`follow: false`), zone from the symlink target, fallback to `/etc/timezone` (C9); `do_change_timezone`; skip when `""`; remove the old existence check (now in validation)
    - _Requirements: 4.4, 15.2, 15.5_

  - [~] 10.6 Convert L4 WLAN Country in `tasks/localization.yml`
    - `get_wifi_country` with rc 1 and empty output accepted as "unset" (C9b); `do_wifi_country`; skip when `""`
    - _Requirements: 2.8, 4.4, 15.4, 15.5_

  - [~] 10.7 Convert A1 Expand Filesystem in `tasks/advanced.yml`
    - Shell Check_Task with `set -o pipefail` printing `get_can_expand` and free bytes from `parted`; Change_Task only when the variable is `true`, output is `0`, and free space ≥ 1 MiB; no disabling task; notify `Reboot`
    - _Requirements: 3.3, 16.1_

  - [~] 10.8 Convert A2 Network Interface Names in `tasks/advanced.yml`
    - `get_net_names` / `do_net_names`; notify `Reboot`
    - _Requirements: 16.2_

  - [~] 10.9 Replace the Wayland tasks with A7 `desktop_backend` in `tasks/advanced.yml`
    - Skip with message when `/etc/lightdm/lightdm.conf` is absent; read `user-session`; expected session name from file presence (`rpd-*` or `LXDE-pi-*`); `do_wayland W1`/`W2` with `environment: raspi_config__user_env`; notify `Reboot`
    - _Requirements: 16.5, 16.10_

  - [~] 10.10 Write property test for the overlay file system state rule
    - `tests/unit/test_p27_overlayfs.py`
    - **Property 27: Overlay file system state rule**
    - **Validates: Requirements 14.2**

  - [~] 10.11 Write property test for the fan decision
    - `tests/unit/test_p28_fan.py`
    - **Property 28: Fan decision**
    - **Validates: Requirements 14.3, 14.5**

  - [~] 10.12 Write property test for the expand file system decision
    - `tests/unit/test_p29_expand.py`
    - **Property 29: Expand file system decision**
    - **Validates: Requirements 16.1**

  - [~] 10.13 Write property test for desktop backend session names
    - `tests/unit/test_p30_desktop_backend.py`
    - **Property 30: Desktop backend session names**
    - **Validates: Requirements 16.5**

  - [~] 10.14 Write property test for model gates and gate messages
    - `tests/unit/test_p06_model_gates.py`; iterate over every gated Option found in the parsed task files so later gated Options are covered automatically
    - **Property 6: Model gates and gate messages**
    - **Validates: Requirements 6.2, 6.3, 12.4, 12.5, 14.1, 14.3, 14.4, 17.3**

- [ ] 11. Phase 1: Write the cross-cutting structural and decision tests
  - [~] 11.1 Write property test for check output classification
    - `tests/unit/test_p02_check_output.py`
    - **Property 2: Check output classification**
    - **Validates: Requirements 2.7, 2.8, 6.4, 15.4, 17.4**

  - [~] 11.2 Write property test for boolean change decisions
    - `tests/unit/test_p03_boolean_change.py`
    - **Property 3: Change decision for boolean Options**
    - **Validates: Requirements 2.3, 2.4, 11.3, 11.5, 12.2, 12.4, 12.5, 13.1, 13.4, 13.5, 14.4, 16.2, 16.4, 16.7, 16.8, 17.1, 17.2**

  - [~] 11.3 Write property test for value change decisions
    - `tests/unit/test_p04_value_change.py`
    - **Property 4: Change decision for value Options**
    - **Validates: Requirements 2.3, 2.4, 9.8, 10.3, 11.4, 12.3, 12.6, 12.7, 15.1, 15.2, 15.3, 15.4, 16.5, 16.6**

  - [~] 11.4 Write property test for reboot notification
    - `tests/unit/test_p15_reboot_notify.py`
    - **Property 15: Reboot notification matches the reboot list**
    - **Validates: Requirements 7.1, 7.8, 13.2**

  - [~] 11.5 Write property test for tag structure
    - `tests/unit/test_p16_tags.py`
    - **Property 16: Tag structure**
    - **Validates: Requirements 1.9, 3.1, 3.2, 3.3, 3.4, 3.5, 3.8**

  - [~] 11.6 Write property test for tag selection
    - `tests/unit/test_p17_tag_selection.py`; cross-check a sample of tags against `ansible-playbook --list-tasks --tags T`
    - **Property 17: Tag selection**
    - **Validates: Requirements 3.6, 3.7, 21.3**

  - [~] 11.7 Write property test for read-only Check_Tasks and inert Change_Tasks
    - `tests/unit/test_p18_check_mode.py`
    - **Property 18: Check_Tasks are read-only and Change_Tasks are inert in check mode**
    - **Validates: Requirements 1.9, 2.1, 2.2, 2.6**

  - [~] 11.8 Write property test for upstream function names
    - `tests/unit/test_p19_upstream_functions.py`; compare against `tests/unit/fixtures/raspi-config-trixie`
    - **Property 19: Only upstream functions are called**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [~] 11.9 Write property test for secret handling
    - `tests/unit/test_p20_secrets.py`
    - **Property 20: Secrets stay hidden**
    - **Validates: Requirements 9.2, 16.3**

- [~] 12. Checkpoint - Phase 1 complete
  - Run `yamllint -c .yamllint .`, `ansible-lint --profile production`, `ansible-playbook -i tests/inventory tests/test.yml --syntax-check` (with the role resolvable as `tkeemon.raspi_config`), and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. Phase 2: Implement the missing System Options
  - [~] 13.1 Implement S2 Audio in `tasks/system.yml`
    - Shell Check_Task (with `environment: raspi_config__user_env`) printing `server=<0|1> outputs=<list> current=<n|none>`; sound server running → message and skip; requested output not listed → fail with the value and the available outputs; `do_audio <n>`; skip when `""`
    - _Requirements: 4.4, 9.4, 9.5_

  - [~] 13.2 Implement S9 Browser in `tasks/system.yml`
    - Skip when `""`; fail before `do_browser` when `/usr/bin/<name>` is absent; `get_browser` / `do_browser <name> <user>` with the user environment
    - _Requirements: 4.4, 11.4, 11.6, 11.7_

  - [~] 13.3 Implement S10 Admin Password in `tasks/system.yml`
    - `get_sudo_pass` / `do_sudo_pass` with the user environment; `0` maps to `true`
    - _Requirements: 11.5, 11.7_

  - [~] 13.4 Write property test for the audio output decision
    - `tests/unit/test_p24_audio.py`
    - **Property 24: Audio output decision**
    - **Validates: Requirements 9.4, 9.5**

  - [~] 13.5 Write unit tests for per-user environment
    - `tests/unit/test_user_env.py`: every task that calls a per-user function listed in the design sets `environment` to `raspi_config__user_env`
    - _Requirements: 10.4, 10.5, 11.4, 11.5_

- [~] 14. Checkpoint - Phase 2 (System) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Phase 3: Implement the missing Display Options
  - [~] 15.1 Implement D1 Underscan in `tasks/display.yml`
    - One `batch` Check_Task for `get_overscan_kms 1` and, on Pi_Model 4 and 5, `get_overscan_kms 2`; one Change_Task per output (`do_overscan_kms <n> 0`/`1`); HDMI-2 message and skip on other models
    - _Requirements: 12.1, 12.9, 12.10_

  - [~] 15.2 Implement D5 4Kp60 HDMI in `tasks/display.yml`
    - Model gate (4) with gate message; `get_pi4video` / `do_pi4video`; notify `Reboot`
    - _Requirements: 6.2, 6.3, 12.5, 12.10_

  - [~] 15.3 Implement D6 Onscreen Keyboard and D7 Keyboard Output in `tasks/display.yml`
    - Both skipped with a message when the `squeekboard` package is absent; D6 `get_squeekboard` / `do_squeekboard S1|S2|S3` through `raspi_config__squeekboard_codes`; D7 skipped when `""`, `get_squeek_output` / `do_squeek_output`; both with the user environment
    - _Requirements: 4.4, 12.6, 12.7, 12.8, 12.10_

  - [~] 15.4 Write property test for the underscan per-output decision
    - `tests/unit/test_p25_underscan.py`
    - **Property 25: Underscan per-output decision**
    - **Validates: Requirements 12.1, 12.9**

- [~] 16. Checkpoint - Phase 3 (Display) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [~] 17. Checkpoint - Decide how I2 Raspberry Pi Connect handles `remote_shell` (C5)
  - Ask the user to choose design option (a), keep `raspi_config_rpi_connect` (`off`, `remote_shell`, `screen_sharing`) and call `rpi-connect on` directly for `remote_shell` as a documented exception, or option (b), replace it with the boolean `raspi_config_enable_rpi_connect` and let the installed package decide.
  - If the user picks (b), update requirements.md 13.3 and the design's I2 rows before task 18.
  - The other Interface Options were converted in task 9 and do not depend on this decision.

- [ ] 18. Phase 4: Implement I2 Raspberry Pi Connect
  - [~] 18.1 Implement I2 in `tasks/interface.yml` following the decision from task 17
    - Check `get_rpi_connect` with the user environment plus package facts; skip with message under the package rules; fail with a `loginctl enable-linger` hint when `/run/user/<uid>` is absent and the Desired_State is not off
    - Option (a): `off` → `do_rpi_connect 1`, `screen_sharing` → `do_rpi_connect 0` only with `rpi-connect` installed, `remote_shell` → `rpi-connect on` (2.0+) or `systemctl --user enable --now rpi-connect.service`
    - Option (b): boolean Option with `:enable` / `:disable` tags; also update `defaults/main.yml`, `vars/main.yml` (`raspi_config__options`, enums, fresh-install defaults), and `tasks/validate.yml`
    - _Requirements: 13.3, 13.7, 13.8, 13.9_

  - [~] 18.2 Write property test for the Raspberry Pi Connect decision
    - `tests/unit/test_p26_rpi_connect.py`; adapt the state table to the option chosen in task 17
    - **Property 26: Raspberry Pi Connect decision**
    - **Validates: Requirements 13.3, 13.7, 13.8**

- [~] 19. Checkpoint - Phase 4 (Interface) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 20. Phase 5: Implement the missing Performance Option
  - [~] 20.1 Implement P4 USB Current in `tasks/performance.yml`
    - Model gate (5) with gate message; `get_usb_current` with `true_output` `'1'`; `do_usb_current 1` for `true`, `0` for `false`; no `Reboot` notification while C3 is unapproved (if approved, flip the `reboot` flag in `vars/main.yml` and add `notify`)
    - _Requirements: 6.2, 6.3, 7.8, 14.4_

- [~] 21. Checkpoint - Phase 5 (Performance) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 22. Phase 6: Implement the missing Localisation Option
  - [~] 22.1 Implement L3 Keyboard in `tasks/localization.yml`
    - Skip when `""`; `slurp` of `/etc/default/keyboard`, `XKBLAYOUT` with quotes removed, missing line counts as a difference; `do_configure_keyboard <layout>`
    - _Requirements: 4.4, 15.3, 15.5_

- [~] 23. Checkpoint - Phase 6 (Localisation) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 24. Phase 7: Implement the missing Advanced Options
  - [~] 24.1 Implement A3 Network Proxy in `tasks/advanced.yml`
    - Looped `get_proxy <scheme>` Check_Task with all five `*_proxy` variables cleared in `environment`; looped `do_proxy <scheme> <value>` only for schemes whose variable is not `""` and differs; `no_log: true`; notify `Reboot`
    - _Requirements: 4.4, 16.3, 16.9_

  - [~] 24.2 Implement A6 Beta Access in `tasks/advanced.yml`
    - `stat` of `/etc/apt/sources.list.d/beta.list`; `do_beta_mode B1`/`B2`; notify `Reboot`
    - _Requirements: 16.4_

  - [~] 24.3 Implement A8 PCIe Speed in `tasks/advanced.yml`
    - Model gate (5) with gate message when the variable is `true`; `get_pci` with output map `0`, `1`; `do_pci 0`/`1`; notify `Reboot`
    - _Requirements: 6.3, 17.1, 17.2, 17.3, 17.4_

  - [~] 24.4 Implement A11 Logging in `tasks/advanced.yml`
    - `slurp` of the journald drop-in (missing file or key → `default`); `do_journald_storage <1..5>` from `raspi_config__log_storage_codes`
    - _Requirements: 16.6_

  - [~] 24.5 Implement A12 WLAN Power Save in `tasks/advanced.yml`
    - Skip with message when no `/sys/class/net/*/wireless` exists; `get_wifi_power_save` with `true_output` `'1'` (C1); `do_wifi_power_save 0` to enable, `1` to disable
    - _Requirements: 16.7, 16.11_

  - [~] 24.6 Implement A13 Link-local Fallback in `tasks/advanced.yml`
    - `get_link_local_fallback` with `true_output` `'1'` (C2); `do_link_local_fallback 0` to enable, `1` to disable; notify `Reboot`
    - _Requirements: 16.8_

  - [~] 24.7 Write property test for unmanaged Options and per-scheme proxy decisions
    - `tests/unit/test_p05_unmanaged.py`
    - **Property 5: Unmanaged Options are skipped**
    - **Validates: Requirements 4.4, 16.3**

  - [~] 24.8 Write property test for configuration file parsers
    - `tests/unit/test_p23_parsers.py`; covers the L1, L2, L3, and A11 parsers
    - **Property 23: Configuration file parsers round-trip**
    - **Validates: Requirements 15.1, 15.2, 15.3, 16.6**

- [~] 25. Checkpoint - Phase 7 (Advanced) complete
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 26. Phase 8: Write the README, CI pipeline, and hardware Test_Playbook
  - [~] 26.1 Rewrite `README.md`
    - Variable table (menu, accepted values, default, Pi_Model values or "all"), Unmanaged_Value section, trixie-only support and `min_ansible_version` 2.18, example playbook with `become: true`, breaking-changes section, deprecated variables, Tag_Convention with every base, `:enable`, and `:disable` tag, reboot section with the reboot list
    - Also document: SSH default and the `false` warning (C7), Lite baseline and a Desktop variable set (C8), Zero 2 W reports Pi_Model 3, `--skip-tags always` unsupported, `force_handlers: true` after failed runs, SHA-512 passwords (C11), two-run overlay disable (C6), serial console needs hardware (C4), and how to run the Test_Playbook and per-tag isolation runs manually
    - Remove the "work in progress" warning
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7, 19.8, 19.9_

  - [~] 26.2 Rewrite `.github/workflows/ci.yml`
    - Triggers on pull request (opened, reopened, synchronize) and push to `master`; checkout into `tkeemon.raspi_config`; latest major versions of `actions/checkout` and `actions/setup-python` (check at change time); install from `requirements.txt`; steps for yamllint, `ansible-lint --profile production`, syntax check with `ANSIBLE_ROLES_PATH`, and `pytest tests/unit`
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6_

  - [~] 26.3 Create the Test_Inventory and desired-state vars
    - `tests/inventory` in YAML with groups `pi5`, `pi4`, `pi3`, `pizero`, each with `raspi_config_test_expected_pi_model` (5, 4, 3, and a maintainer-set value for `pizero`); hosts addressed by IP
    - `tests/vars/desired_<group>.yml` setting every Option whose gate includes the group's Pi_Model to a non-default value, with the design's exceptions (SSH `true`, fan pin 18, Unmanaged-default Options and S10 only through extra variables)
    - _Requirements: 21.5, 21.6_

  - [~] 26.4 Rewrite `tests/test.yml`
    - Play 0: group-membership and Pi_Model check; Play 1: role with desired vars and `raspi_config_allow_reboot: true`; Play 2: second application and assertion that no `raspi_config__change_*` is changed; Play 3: P2 restore with two reboot cycles; Play 4: role with defaults (SSH kept `true`); Play 5: check-mode run with defaults and assertion naming Option, Check_Task output, and expected default
    - S10 handling with `raspi_config_test_become_password` (C13)
    - Optional plays enabled by extra variables for Property 35 (fresh image, defaults change nothing) and Property 36 (check-mode `changed` set equals the following normal run's set, Check_Task snapshot unchanged)
    - Hardware Properties 33 to 36 are checked by the maintainer running this playbook on Pi 5, Pi 4, Pi 3, and Pi Zero / Zero 2 W; that run is a manual step
    - _Requirements: 2.5, 2.6, 4.9, 8.8, 21.1, 21.2, 21.3, 21.4, 21.7, 21.8, 21.9, 21.10_

  - [~] 26.5 Write property test for role data, defaults, README, and test data consistency
    - `tests/unit/test_p32_consistency.py`
    - **Property 32: Role data, defaults, README, and test data stay consistent**
    - **Validates: Requirements 4.1, 4.5, 4.7, 19.1, 19.8, 19.9, 21.6, 21.7, 21.9**

  - [~] 26.6 Write unit tests for README sections, inventory shape, and leftover TODOs
    - `tests/unit/test_docs_examples.py`: README sections of 19.2 to 19.7, exactly four inventory groups with expected Pi_Model variables, no `TODO` outside the out-of-scope Options
    - _Requirements: 8.5, 19.2, 19.3, 19.4, 19.5, 19.6, 19.7, 21.5_

- [~] 27. Final checkpoint - Ensure all tests pass
  - Run yamllint, ansible-lint (production profile), the syntax check, and `pytest tests/unit`.
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP. Core implementation tasks are never optional.
- Each task references requirement clauses for traceability. Clarifications C1 to C13 follow the design's recommended resolutions; the recommended requirement text changes in the design are not yet applied to requirements.md.
- The structural and decision tests (tasks 10.14 and 11.x) iterate over the Options found in the parsed task files, so they cover the Options added in Phases 2 to 7 without edits.
- Property tests use Hypothesis with at least 100 examples (200 for Properties 7 to 11, 23, and 31) and carry a `# Feature: raspi-config-role-completion, Property N: <title>` comment.
- Hardware Properties 33 to 36 are not agent tasks. The maintainer runs `tests/test.yml` on physical hardware before each release, along with the manual checks listed in the design (S1, S2, S7, D1, D4 to D7, I2, S10, P1, A1, A7, and per-tag isolation).

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "2.1", "2.2", "6.1", "6.2"] },
    { "id": 1, "tasks": ["1.3", "2.3", "2.4", "3.1", "4.1", "5.1", "7.2"] },
    { "id": 2, "tasks": ["3.2", "3.3", "4.2", "5.2", "6.3", "6.4", "7.1", "7.3"] },
    { "id": 3, "tasks": ["4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "8.1", "9.1", "9.4", "10.1", "10.4", "10.7"] },
    { "id": 4, "tasks": ["8.2", "9.2", "9.5", "10.2", "10.5", "10.8"] },
    { "id": 5, "tasks": ["8.3", "9.3", "10.3", "10.6", "10.9", "10.10", "10.12"] },
    { "id": 6, "tasks": ["8.4", "8.7", "10.11", "10.13", "10.14"] },
    { "id": 7, "tasks": ["8.5", "8.8"] },
    { "id": 8, "tasks": ["8.6"] },
    { "id": 9, "tasks": ["11.1", "11.2", "11.3", "11.4", "11.5", "11.6", "11.7", "11.8", "11.9"] },
    { "id": 10, "tasks": ["13.1"] },
    { "id": 11, "tasks": ["13.2", "13.4"] },
    { "id": 12, "tasks": ["13.3"] },
    { "id": 13, "tasks": ["13.5"] },
    { "id": 14, "tasks": ["15.1"] },
    { "id": 15, "tasks": ["15.2", "15.4"] },
    { "id": 16, "tasks": ["15.3"] },
    { "id": 17, "tasks": ["18.1"] },
    { "id": 18, "tasks": ["18.2"] },
    { "id": 19, "tasks": ["20.1"] },
    { "id": 20, "tasks": ["22.1"] },
    { "id": 21, "tasks": ["24.1"] },
    { "id": 22, "tasks": ["24.2", "24.7"] },
    { "id": 23, "tasks": ["24.3"] },
    { "id": 24, "tasks": ["24.4"] },
    { "id": 25, "tasks": ["24.5", "24.8"] },
    { "id": 26, "tasks": ["24.6"] },
    { "id": 27, "tasks": ["26.1", "26.2", "26.3"] },
    { "id": 28, "tasks": ["26.4", "26.6"] },
    { "id": 29, "tasks": ["26.5"] }
  ]
}
```
