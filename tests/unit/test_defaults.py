"""Unit tests for ``defaults/main.yml`` and the data tables in ``vars/main.yml``.

Only the data tables are read from ``vars/main.yml`` (by name), so the tests do not
depend on the predicates that other tasks add to the same file.

**Validates: Requirements 4.3, 4.6, 6.1, 7.4, 8.6, 9.9**
"""

from __future__ import annotations

import fnmatch
import re

import pytest

import harness

DEFAULTS_FILE = harness.ROLE_ROOT / "defaults" / "main.yml"

GROUP_ORDER = ["system", "display", "interface", "performance", "localization", "advanced"]
GROUP_PREFIX = {
    "system": "S",
    "display": "D",
    "interface": "I",
    "performance": "P",
    "localization": "L",
    "advanced": "A",
}
NON_OPTION_VARIABLES = ["raspi_config_user", "raspi_config_allow_reboot"]

# Requirement 4.3
UNMANAGED_BY_DEFAULT = [
    "raspi_config_wifi_ssid",
    "raspi_config_wifi_password",
    "raspi_config_password",
    "raspi_config_browser",
    "raspi_config_onscreen_keyboard_output",
    "raspi_config_http_proxy",
    "raspi_config_https_proxy",
    "raspi_config_ftp_proxy",
    "raspi_config_rsync_proxy",
    "raspi_config_no_proxy",
]

# Requirement 8.6
DEPRECATED_VARIABLES = {
    "raspi_config_enable_legacy_camera",
    "raspi_config_enable_remote_gpio",
    "raspi_config_gpu_memory",
    "raspi_config_wait_on_network",
    "raspi_config_enable_xcompmgr",
    "raspi_config_enable_glamor",
}
RENAMED_VARIABLES = {"raspi_config_enable_serial_port", "raspi_config_enable_wayland"}

PI_MODELS = [0, 1, 2, 3, 4, 5]

# Requirement 6.1: Option key in raspi_config__option_models -> (menu id, Role_Variables).
MENU_GATES = {
    "overclock": ("P1", ["raspi_config_overclock_settings"]),
    "fan": (
        "P3",
        ["raspi_config_enable_gpio_fan", "raspi_config_gpio_fan_pin", "raspi_config_gpio_fan_temp"],
    ),
    "hdmi_4kp60": ("D5", ["raspi_config_enable_hdmi_4kp60"]),
    "usb_current": ("P4", ["raspi_config_enable_usb_current_limit"]),
    "pcie_speed": ("A8", ["raspi_config_enable_pcie_gen3"]),
}
# The gates named in Requirement 6.1.
REQUIRED_GATES = {
    "overclock": [1, 2],
    "fan": [4],
    "hdmi_4kp60": [4],
    "usb_current": [5],
    "pcie_speed": [5],
}
# Not a menu gate in the Upstream_Script: HDMI-2 exists on the Pi 4 and Pi 5 only.
HDMI2_GATE = ("underscan_hdmi2", [4, 5])

MENU_FUNCTIONS = {
    "S": "do_system_menu",
    "D": "do_display_menu",
    "I": "do_interface_menu",
    "P": "do_performance_menu",
    "A": "do_advanced_menu",
}


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def parse_defaults_layout(text: str) -> list[dict]:
    """Return one dict per variable in file order.

    Keys: ``name``, ``group`` (``None`` before the first ``### group`` line),
    ``menu`` (``"S1"`` or ``None``), ``comment`` (the comment lines directly above
    the variable, joined by spaces).
    """
    entries: list[dict] = []
    group = None
    comment: list[str] = []
    for line in text.splitlines():
        header = re.match(r"^### (\w+)\s*$", line)
        if header:
            group = header.group(1)
            comment = []
        elif line.startswith("#"):
            comment.append(line.lstrip("#").strip())
        else:
            var = re.match(r"^(raspi_config_\w+):", line)
            if var:
                joined = " ".join(comment)
                menu = re.match(r"([SDILPA]\d+)\b", joined)
                entries.append(
                    {
                        "name": var.group(1),
                        "group": group,
                        "menu": menu.group(1) if menu else None,
                        "comment": joined,
                    }
                )
            comment = []
    return entries


def menu_number(menu_id: str) -> int:
    return int(menu_id[1:])


def _function_body(script: str, name: str) -> list[str]:
    lines = script.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf"^{re.escape(name)}\(\)\s*\{{", line))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return lines[start + 1 : end]


_ENTRY = re.compile(r'^\s+"([A-Z]\d+) [^"]*"')


def _predicate(condition: str, model: int, wayland: bool) -> bool:
    if condition == "is_pi":
        return True  # every Pi_Model 0..5 is a Pi
    if condition == "is_wayland":
        return wayland
    if condition == "is_pifour":
        return model == 4
    if condition == "is_pifive":
        return model == 5
    if condition == "is_live":
        return False
    raise AssertionError(f"unhandled menu condition in the Upstream_Script: {condition!r}")


def _entry_conditions(body: list[str]) -> dict[str, list[list[list[str | None]]]]:
    """Map menu id -> list of if/elif/else chains (outermost first) around each entry."""
    result: dict[str, list] = {}
    stack: list[list[str | None]] = []
    for line in body:
        if m := re.match(r"^\s*if (.+?)\s*;\s*then\s*$", line):
            stack.append([m.group(1)])
        elif m := re.match(r"^\s*elif (.+?)\s*;\s*then\s*$", line):
            stack[-1].append(m.group(1))
        elif re.match(r"^\s*else\s*$", line):
            stack[-1].append(None)
        elif re.match(r"^\s*fi\s*$", line):
            stack.pop()
        elif m := _ENTRY.match(line):
            result.setdefault(m.group(1), []).append([list(chain) for chain in stack])
    return result


def _chain_holds(chain: list[str | None], model: int, wayland: bool) -> bool:
    *earlier, current = chain
    if any(_predicate(c, model, wayland) for c in earlier):
        return False
    return current is None or _predicate(current, model, wayland)


def _case_branches(body: list[str]) -> list[tuple[str, list[str]]]:
    """Branches of the ``case "$(get_pi_type)"`` menu: (pattern, menu ids)."""
    branches: list[tuple[str, list[str]]] = []
    for line in body:
        if m := re.match(r"^\s+(\S+)\) FUN=", line):
            branches.append((m.group(1), []))
        elif (m := _ENTRY.match(line)) and branches:
            branches[-1][1].append(m.group(1))
    return branches


def menu_models(script: str, menu_id: str) -> list[int]:
    """Pi_Model values for which the Upstream_Script menu offers ``menu_id``."""
    function = MENU_FUNCTIONS[menu_id[0]]
    body = _function_body(script, function)
    if function == "do_performance_menu":
        branches = _case_branches(body)
        available = []
        for model in PI_MODELS:
            pattern = next(p for p, _ in branches if fnmatch.fnmatchcase(str(model), p))
            ids = dict(branches)[pattern]
            if menu_id in ids:
                available.append(model)
        return available
    chains_per_entry = _entry_conditions(body).get(menu_id, [])
    return [
        model
        for model in PI_MODELS
        if any(
            all(_chain_holds(chain, model, wayland) for chain in chains)
            for chains in chains_per_entry
            for wayland in (True, False)
        )
    ]


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def layout() -> list[dict]:
    return parse_defaults_layout(DEFAULTS_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def option_models(role_vars) -> dict:
    return role_vars["raspi_config__option_models"]


# --------------------------------------------------------------------------
# fresh-install defaults map
# --------------------------------------------------------------------------


def test_fresh_install_defaults_equal_defaults_file(role_defaults, role_vars):
    """raspi_config__fresh_install_defaults equals defaults/main.yml (design, vars table)."""
    fresh = role_vars["raspi_config__fresh_install_defaults"]
    assert fresh == role_defaults
    # equality of dicts ignores type differences between 0/False and 1/True only
    # through ==; compare the types too so a bool never stands in for an int.
    for name, value in role_defaults.items():
        assert type(fresh[name]) is type(value), name


# --------------------------------------------------------------------------
# Requirement 4.6: group and menu order
# --------------------------------------------------------------------------


def test_non_option_variables_come_first(layout):
    names = [e["name"] for e in layout]
    assert names[: len(NON_OPTION_VARIABLES)] == NON_OPTION_VARIABLES
    assert [e["group"] for e in layout[: len(NON_OPTION_VARIABLES)]] == [None] * len(NON_OPTION_VARIABLES)
    assert all(e["group"] is not None for e in layout[len(NON_OPTION_VARIABLES) :])


def test_groups_appear_in_submenu_order(layout):
    groups: list[str] = []
    for entry in layout:
        if entry["group"] is not None and (not groups or groups[-1] != entry["group"]):
            groups.append(entry["group"])
    assert groups == GROUP_ORDER


def test_variables_follow_menu_order_within_each_group(layout):
    for group in GROUP_ORDER:
        members = [e for e in layout if e["group"] == group]
        assert members, f"group {group} is empty"
        for entry in members:
            assert entry["menu"], f"{entry['name']} has no menu number in its comment"
            assert entry["menu"][0] == GROUP_PREFIX[group], (entry["name"], entry["menu"], group)
        numbers = [menu_number(e["menu"]) for e in members]
        assert numbers == sorted(numbers), f"{group}: {[e['menu'] for e in members]}"


def test_defaults_file_variables_match_fresh_install_map(layout, role_defaults):
    names = [e["name"] for e in layout]
    assert len(names) == len(set(names)), "a variable is defined twice in defaults/main.yml"
    assert set(names) == set(role_defaults)


def test_option_table_agrees_with_defaults_layout(layout, role_vars):
    """Menu id and submenu of every raspi_config__options entry match the defaults file."""
    by_name = {e["name"]: e for e in layout}
    for key, option in role_vars["raspi_config__options"].items():
        entry = by_name[option["variable"]]
        assert entry["group"] == option["submenu"], key
        assert entry["menu"] == re.match(r"[A-Z]\d+", option["menu"]).group(0), key


# --------------------------------------------------------------------------
# Requirements 4.3, 7.4, 9.9, 8.6
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", UNMANAGED_BY_DEFAULT)
def test_unmanaged_value_defaults(role_defaults, name):
    """Requirement 4.3 (and 9.9 for raspi_config_password)."""
    assert role_defaults[name] == ""


def test_password_default_is_unmanaged(role_defaults):
    """Requirement 9.9."""
    assert role_defaults["raspi_config_password"] == ""


def test_allow_reboot_defaults_to_false(role_defaults):
    """Requirement 7.4: the boolean false, not a string."""
    assert role_defaults["raspi_config_allow_reboot"] is False


def test_deprecated_variable_list_is_exactly_the_six_names(role_vars):
    """Requirement 8.6."""
    entries = role_vars["raspi_config__deprecated_variables"]
    names = [e["name"] for e in entries]
    assert len(names) == 6
    assert set(names) == DEPRECATED_VARIABLES
    assert all(e["option"] for e in entries)


def test_deprecated_and_renamed_variables_are_not_defined(role_defaults, role_vars):
    """Requirements 8.6 and 4.7: the names appear only as list data."""
    assert not (DEPRECATED_VARIABLES | RENAMED_VARIABLES) & set(role_defaults)
    assert not (DEPRECATED_VARIABLES | RENAMED_VARIABLES) & set(role_vars)
    assert {e["name"] for e in role_vars["raspi_config__renamed_variables"]} == RENAMED_VARIABLES


# --------------------------------------------------------------------------
# Requirement 6.1: model gates
# --------------------------------------------------------------------------


def test_required_gates_are_present(option_models):
    for key, models in REQUIRED_GATES.items():
        assert option_models[key] == models


def test_gate_table_has_no_unexpected_entries(option_models):
    assert set(option_models) == set(MENU_GATES) | {HDMI2_GATE[0]}
    for models in option_models.values():
        assert models == sorted(set(models))
        assert set(models) <= set(PI_MODELS)


def test_all_models_list(role_vars):
    assert role_vars["raspi_config__all_models"] == PI_MODELS


@pytest.mark.parametrize("key", sorted(MENU_GATES))
def test_gates_match_upstream_menus(upstream_script, option_models, key):
    """Each gate lists exactly the Pi_Model values whose trixie menu offers the Option."""
    menu_id, _ = MENU_GATES[key]
    from_script = menu_models(upstream_script, menu_id)
    assert from_script, f"{menu_id} not found in the Upstream_Script menus"
    assert option_models[key] == from_script


def test_hdmi2_gate(option_models):
    """Not a menu gate upstream: the second HDMI output exists on the Pi 4 and Pi 5."""
    assert option_models[HDMI2_GATE[0]] == HDMI2_GATE[1]


def test_options_without_a_gate_are_offered_on_every_model(upstream_script, role_vars, option_models):
    """Options missing from raspi_config__option_models apply to all models in the menus."""
    for key, option in role_vars["raspi_config__options"].items():
        if key in option_models:
            continue
        menu_id = re.match(r"[A-Z]\d+", option["menu"]).group(0)
        assert menu_models(upstream_script, menu_id) == PI_MODELS, (key, menu_id)


@pytest.mark.parametrize("key", sorted(MENU_GATES))
def test_gate_models_are_documented_in_defaults(layout, option_models, key):
    """Requirement 6.1: the defaults comments list the same Pi_Model values as the gate."""
    by_name = {e["name"]: e for e in layout}
    _, variables = MENU_GATES[key]
    for name in variables:
        match = re.search(r"Models:\s*(\d+(?:,\s*\d+)*)", by_name[name]["comment"])
        assert match, f"{name}: no 'Models:' list in its comment"
        assert [int(n) for n in re.split(r",\s*", match.group(1))] == option_models[key], name


def test_hdmi2_models_are_documented_in_defaults(layout, option_models):
    by_name = {e["name"]: e for e in layout}
    match = re.search(r"HDMI-2:\s*(\d+(?:,\s*\d+)*)", by_name["raspi_config_underscan_outputs"]["comment"])
    assert match
    assert [int(n) for n in re.split(r",\s*", match.group(1))] == option_models[HDMI2_GATE[0]]


def test_ungated_variables_document_models_all(layout):
    gated = {name for _, names in MENU_GATES.values() for name in names}
    for entry in layout:
        if entry["menu"] is None or entry["name"] in gated:
            continue
        assert re.search(r"Models:\s*all\b", entry["comment"]), entry["name"]
