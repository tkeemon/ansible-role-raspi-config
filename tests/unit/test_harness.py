"""Self-tests for the harness: parser, rendering, strategies, pinned fixture."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings

import harness
import strategies as strat
import taskparser

SYNTHETIC_MAIN = """\
---
- name: Preflight
  ansible.builtin.import_tasks: preflight.yml
  tags: [always]
- name: Run System tasks
  ansible.builtin.import_tasks: system.yml
  tags: [raspi_config, "raspi_config:system"]
"""

SYNTHETIC_SYSTEM = """\
---
- name: S4 Hostname
  when: raspi_config_hostname != ""
  tags: ["raspi_config:system:hostname"]
  environment: "{{ raspi_config__user_env }}"
  block:
    - name: Read hostname
      ansible.builtin.command:
        argv: [raspi-config, nonint, get_hostname]
      changed_when: false
      check_mode: false
      tags: ["raspi_config:system:hostname:enable"]
    - name: Set hostname
      ansible.builtin.command:
        argv: "{{ ansible_check_mode | ternary(raspi_config__noop_argv, ['raspi-config', 'nonint', 'do_hostname', raspi_config_hostname]) }}"
      changed_when: true
      notify: Reboot
      no_log: true
      when:
        - raspi_config_hostname | length > 0
  rescue:
    - name: Report failure
      ansible.builtin.fail:
        msg: "Option S4 failed: {{ raspi_config_hostname }}"
"""

SYNTHETIC_PREFLIGHT = """\
---
- name: Find raspi-config
  ansible.builtin.command: sh -c 'command -v raspi-config'
  changed_when: false
"""


def _write_role(root: Path) -> None:
    (root / "tasks").mkdir()
    (root / "tasks" / "main.yml").write_text(SYNTHETIC_MAIN)
    (root / "tasks" / "system.yml").write_text(SYNTHETIC_SYSTEM)
    (root / "tasks" / "preflight.yml").write_text(SYNTHETIC_PREFLIGHT)


def test_pinned_upstream_script_has_commit_hash_and_functions(upstream_script, upstream_functions):
    header = "\n".join(upstream_script.splitlines()[:10])
    assert "Upstream commit:" in header
    assert any(len(w) == 40 and set(w) <= set("0123456789abcdef") for w in header.split())
    assert {"get_pi_type", "do_ssh", "get_ssh", "do_hostname"} <= upstream_functions


def test_hypothesis_profile_minimum_examples():
    assert settings().max_examples >= 100
    assert harness.pbt_settings.max_examples >= 100
    assert harness.pbt_settings_large.max_examples >= 200


def test_parser_flattens_tasks_with_effective_tags(tmp_path):
    _write_role(tmp_path)
    role = taskparser.parse_role(tmp_path)
    assert set(role.files()) == {"main.yml", "system.yml", "preflight.yml"}
    assert role.import_tags["preflight.yml"] == {"always"}

    find = role.by_file("preflight.yml")[0]
    assert "always" in find.effective_tags and find.module == "ansible.builtin.command"

    read, set_host, report = role.by_file("system.yml")
    assert read.effective_tags == {
        "raspi_config", "raspi_config:system", "raspi_config:system:hostname",
        "raspi_config:system:hostname:enable",
    }
    assert read.check_mode is False and read.block is not None and read.section == "block"
    assert set_host.notify == ("Reboot",) and set_host.no_log is True
    assert set_host.environment == "{{ raspi_config__user_env }}"  # inherited from the block
    assert set_host.effective_when[0] == 'raspi_config_hostname != ""' and len(set_host.effective_when) == 2
    assert report.section == "rescue" and report.block is set_host.block
    assert "always" not in set_host.effective_tags
    assert {t.name for t in role.select("raspi_config:system:hostname:enable")} >= {"Read hostname", "Find raspi-config"}


def test_parser_tolerates_missing_tasks_dir(tmp_path):
    role = taskparser.parse_role(tmp_path)
    assert role.tasks == [] and role.blocks == []


def test_templar_renders_expressions_when_argv_and_text(tmp_path):
    _write_role(tmp_path)
    task = taskparser.parse_role(tmp_path).by_file("system.yml")[1]
    variables = harness.build_variables(
        {"raspi_config_hostname": "pi5", "ansible_check_mode": False},
        defaults={},
        role_vars={
            "raspi_config__noop_argv": ["/bin/true"],
            "raspi_config__valid_hostname": "{{ raspi_config_hostname is match('^[a-z0-9]+$') }}",
        },
    )
    t = harness.make_templar(variables)
    assert harness.render_expression(t, "raspi_config__valid_hostname") is True
    assert harness.render_when(t, task.effective_when) is True
    assert harness.render_argv(t, task) == ["raspi-config", "nonint", "do_hostname", "pi5"]
    check = harness.make_templar({**variables, "ansible_check_mode": True})
    assert harness.render_argv(check, task) == ["/bin/true"]
    assert harness.render_text(t, "host {{ raspi_config_hostname }}") == "host pi5"
    assert harness.render_when(harness.make_templar({**variables, "raspi_config_hostname": ""}), task.effective_when) is False


@given(strat.hostnames())
def test_hostnames_strategy_produces_strings(value):
    assert isinstance(value, str)


@given(strat.yaml_values())
def test_yaml_values_strategy_runs(value):
    assert value is None or isinstance(value, (str, int, float, bool, list))


@given(strat.ssids(), strat.psks(), strat.proxy_values())
def test_text_strategies_produce_strings(ssid, psk, proxy):
    assert all(isinstance(v, str) for v in (ssid, psk, proxy))


@given(strat.tab_files())
def test_tab_files_members_have_tab_rows(ref):
    for code in ref.members:
        assert any(line.startswith(code + "\t") and not line.startswith("#") for line in ref.content.splitlines())
    assert not (ref.members & ref.lookalikes)


@given(strat.supported_files())
def test_supported_files_members_are_first_fields(ref):
    firsts = {line.split()[0] for line in ref.content.splitlines() if line.strip() and not line.startswith("#")}
    assert ref.members == firsts - {None}


@given(strat.base_lst())
def test_base_lst_members_come_from_layout_section(ref):
    section, layout = None, set()
    for line in ref.content.splitlines():
        if line.startswith("!"):
            section = line[1:].strip()
        elif line.strip() and section == "layout":
            layout.add(line.split()[0])
    assert ref.members == layout


@given(strat.kv_files("LANG"))
def test_kv_files_expected_is_last_assignment(f):
    last = None
    for line in f.content.splitlines():
        if line.startswith("LANG="):
            last = line.split("=", 1)[1].strip('"')
    assert f.expected == last


@given(strat.check_results(), strat.pi_models(), strat.board_types(), strat.deprecated_subsets())
def test_remaining_strategies_run(result, model, board, deprecated):
    assert -1 <= result.rc <= 255 and isinstance(result.stdout, str)
    assert model in strat.PI_MODELS and isinstance(board, int)
    assert set(deprecated) <= set(strat.deprecated_names())


@given(strat.enum_values(accepted=["console", "desktop"]))
def test_enum_values_strategy_runs(value):
    assert isinstance(value, str)


def test_enum_values_builds_with_or_without_role_data():
    # Must not raise whether or not vars/main.yml defines raspi_config__enums yet.
    assert strat.enum_values("raspi_config_boot_behavior") is not None
    assert strat.enum_values("no_such_variable") is not None
