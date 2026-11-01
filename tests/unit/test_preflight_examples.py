"""Example tests for tasks/preflight.yml: check order and read-only behaviour.

* The release assertion comes before the `raspi-config` presence check, which
  comes before every task that reads the Pi_Model (Requirement 1.8).
* A failing check stops the host: no preflight check task ignores errors,
  rescues, or turns its failure into a pass (Requirement 1.8).
* The preflight file is imported with the `always` tag (Requirement 1.9).
* No preflight task writes to the Target_Host: only read-only modules are used,
  every `command` task runs in check mode and reports `ok`, no task notifies a
  handler, and the only `raspi-config` call is `nonint get_pi_type`
  (Requirements 1.9, 6.5).

The tests parse the real `tasks/preflight.yml` with `taskparser`.

**Validates: Requirements 1.8, 1.9, 6.5**
"""

from __future__ import annotations

import pytest

RELEASE_TASK = "Assert that the Target_Host runs Debian trixie"
PRESENCE_FIND_TASK = "Find the raspi-config command"
PRESENCE_ASSERT_TASK = "Assert that the raspi-config command exists"
PI_TYPE_READ_TASK = "Read the Pi_Model"
PI_TYPE_ASSERT_TASKS = (
    "Assert that the Target_Host is a Raspberry Pi",
    "Assert that the Pi_Model is known",
)
PI_MODEL_FACT_TASK = "Set the Pi_Model fact"

# Modules that only read from the Target_Host or set facts on the controller.
READ_ONLY_MODULES = {
    "setup",
    "assert",
    "command",
    "set_fact",
    "slurp",
    "getent",
    "package_facts",
}


@pytest.fixture(scope="module")
def preflight(parsed_role):
    tasks = parsed_role.by_file("preflight.yml")
    assert tasks, "tasks/preflight.yml has no tasks"
    return tasks


@pytest.fixture(scope="module")
def by_name(preflight):
    return {t.name: t for t in preflight}


def _position(by_name, name):
    assert name in by_name, f"tasks/preflight.yml has no task named {name!r}"
    return by_name[name].index


def _is_raspi_config_call(task) -> bool:
    argv = task.argv
    return isinstance(argv, list) and bool(argv) and str(argv[0]) == "raspi-config"


# --------------------------------------------------------------------------
# Order (Requirement 1.8)
# --------------------------------------------------------------------------


def test_release_check_comes_before_raspi_config_presence(by_name):
    release = _position(by_name, RELEASE_TASK)
    assert release < _position(by_name, PRESENCE_FIND_TASK)
    assert release < _position(by_name, PRESENCE_ASSERT_TASK)


def test_raspi_config_presence_comes_before_pi_model(by_name):
    presence_assert = _position(by_name, PRESENCE_ASSERT_TASK)
    assert _position(by_name, PRESENCE_FIND_TASK) < presence_assert
    assert presence_assert < _position(by_name, PI_TYPE_READ_TASK)
    for name in (*PI_TYPE_ASSERT_TASKS, PI_MODEL_FACT_TASK):
        assert presence_assert < _position(by_name, name)


def test_pi_model_is_read_before_it_is_checked_and_stored(by_name):
    read = _position(by_name, PI_TYPE_READ_TASK)
    for name in (*PI_TYPE_ASSERT_TASKS, PI_MODEL_FACT_TASK):
        assert read < _position(by_name, name)


def test_no_raspi_config_call_runs_before_presence_check(preflight, by_name):
    presence_assert = _position(by_name, PRESENCE_ASSERT_TASK)
    early = [t.label() for t in preflight if _is_raspi_config_call(t) and t.index < presence_assert]
    assert early == []


def test_release_is_the_first_check(preflight, by_name):
    """Nothing but fact gathering may run before the release assertion."""
    release = _position(by_name, RELEASE_TASK)
    before = [t for t in preflight if t.index < release]
    assert all(t.short_module == "setup" for t in before), [t.label() for t in before]


def test_a_failing_check_stops_the_host(preflight):
    """Check tasks cannot swallow a failure, so the first failing check ends the host's run."""
    checks = [t for t in preflight if t.short_module == "assert"]
    assert len(checks) >= 4
    for task in checks:
        assert not task.ignore_errors, task.label()
        assert task.failed_when is None, task.label()
        assert task.section is None, f"{task.label()} sits in a block/rescue"
    assert all(t.section is None for t in preflight), "preflight tasks must not use block/rescue/always"


# --------------------------------------------------------------------------
# Always runs (Requirement 1.9)
# --------------------------------------------------------------------------


def test_preflight_is_imported_with_the_always_tag(parsed_role, preflight):
    assert "always" in parsed_role.import_tags["preflight.yml"]
    for task in preflight:
        assert "always" in task.effective_tags, task.label()


def test_preflight_tasks_have_no_when_that_skips_checks(by_name):
    """Only fact gathering is conditional; every check runs on every play."""
    for name, task in by_name.items():
        if task.short_module == "setup":
            continue
        assert not task.effective_when, f"{task.label()} is conditional: {task.effective_when}"


# --------------------------------------------------------------------------
# Read-only (Requirements 1.9, 6.5)
# --------------------------------------------------------------------------


def test_preflight_uses_only_read_only_modules(preflight):
    for task in preflight:
        assert task.short_module in READ_ONLY_MODULES, f"{task.label()} uses {task.module}"


def test_preflight_command_tasks_run_in_check_mode_and_report_ok(preflight):
    commands = [t for t in preflight if t.short_module == "command"]
    assert len(commands) == 2
    for task in commands:
        assert task.check_mode is False, task.label()
        assert task.changed_when is False, task.label()


def test_preflight_notifies_no_handler(preflight):
    for task in preflight:
        assert task.notify == (), task.label()


def test_preflight_does_not_become_another_user_or_set_environment(preflight):
    for task in preflight:
        assert "become" not in task.raw or task.raw["become"] in (True, "true", "yes"), task.label()
        assert not task.environment, task.label()


def test_only_raspi_config_call_is_get_pi_type(preflight):
    calls = [t for t in preflight if _is_raspi_config_call(t)]
    assert [list(map(str, t.argv)) for t in calls] == [["raspi-config", "nonint", "get_pi_type"]]


def test_presence_check_only_looks_up_the_command(by_name):
    argv = [str(a) for a in by_name[PRESENCE_FIND_TASK].argv]
    assert argv == ["sh", "-c", "command -v raspi-config"]


def test_getent_and_package_facts_only_read(preflight):
    for task in preflight:
        if task.short_module == "getent":
            assert task.args == {"database": "passwd"}
        if task.short_module == "slurp":
            assert set(task.args) == {"src"}
        if task.short_module == "package_facts":
            assert set(task.args) == {"manager"}
