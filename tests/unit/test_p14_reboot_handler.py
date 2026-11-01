"""Property 14: Reboot handler decision.

For any combination of ``raspi_config_allow_reboot`` and check mode, the ``Reboot``
handler runs if and only if ``allow_reboot`` is true and check mode is off. The
pending-reboot message handler runs in every other combination, says ``would need``
in check mode and ``needs`` otherwise, and names ``raspi_config_allow_reboot``.

The timeout failure handler is tested against what ``handlers/main.yml`` does. The
``Reboot`` handler has ``failed_when: false``, which resets the ``failed`` key of the
registered result, so the design's ``is failed`` can never be true. The file instead
fails when the result is defined, not skipped, and carries a ``msg``. A reboot that
succeeds returns no ``msg``; one that times out returns one.

``handlers/main.yml`` is not parsed by ``taskparser`` (it reads ``tasks/``), so the
handlers are loaded with ``harness.load_yaml``.

**Validates: Requirements 2.10, 7.2, 7.3, 7.6, 7.7**
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, strategies as st

import harness

HANDLERS: list[dict] = harness.load_yaml(harness.ROLE_ROOT / "handlers" / "main.yml", default=[])


def _handler(name: str) -> dict:
    matches = [h for h in HANDLERS if h.get("name") == name]
    assert len(matches) == 1, f"expected exactly one handler named {name!r}"
    return matches[0]


REBOOT = _handler("Reboot")
FAIL = _handler("Fail when the host did not come back after the reboot")
REPORT = _handler("Report pending reboot")

#: Values a user can give for ``raspi_config_allow_reboot``; ``| bool`` accepts them all.
ALLOW_REBOOT = st.sampled_from([True, False, "true", "false", "yes", "no", "1", "0", "True", "False"])
TRUTHY = {True, "true", "yes", "1", "True"}

#: Registered results of the ``Reboot`` handler as the play sees them.
#: ``None`` stands for a variable that is not defined.
SKIPPED_RESULT = {"changed": False, "skipped": True, "skip_reason": "Conditional result was False"}
SUCCESS_RESULT = {"changed": True, "elapsed": 42, "rebooted": True, "failed": False}
TIMEOUT_RESULT = {
    "changed": False,
    "elapsed": 600,
    "rebooted": False,
    "failed": False,  # reset by failed_when: false
    "msg": "Timed out waiting for last boot time check (timeout=600)",
}
REBOOT_RESULTS = st.sampled_from([None, SKIPPED_RESULT, SUCCESS_RESULT, TIMEOUT_RESULT])


def _inputs(allow_reboot, check_mode: bool, result=None) -> dict:
    inputs = {"raspi_config_allow_reboot": allow_reboot, "ansible_check_mode": check_mode}
    if result is not None:
        inputs["raspi_config__reboot_result"] = result
    return inputs


# --------------------------------------------------------------------------
# Handler structure
# --------------------------------------------------------------------------


def test_the_three_handlers_respond_to_the_reboot_notification() -> None:
    assert "listen" not in REBOOT  # notified by its name
    assert FAIL["listen"] == "Reboot"
    assert REPORT["listen"] == "Reboot"


def test_handlers_run_in_the_order_reboot_failure_report() -> None:
    names = [h["name"] for h in HANDLERS]
    assert names.index(REBOOT["name"]) < names.index(FAIL["name"]) < names.index(REPORT["name"])


def test_reboot_handler_uses_the_reboot_module_with_a_600_second_timeout() -> None:
    assert REBOOT["ansible.builtin.reboot"]["reboot_timeout"] == 600
    assert REBOOT["register"] == "raspi_config__reboot_result"
    assert REBOOT["failed_when"] is False


# --------------------------------------------------------------------------
# Reboot handler (Requirements 2.10, 7.2, 7.3)
# --------------------------------------------------------------------------


@given(allow_reboot=ALLOW_REBOOT, check_mode=st.booleans())
def test_reboot_runs_iff_allowed_and_not_in_check_mode(render_when, allow_reboot, check_mode) -> None:
    runs = render_when(REBOOT["when"], _inputs(allow_reboot, check_mode))
    assert runs is (allow_reboot in TRUTHY and not check_mode)


# --------------------------------------------------------------------------
# Pending-reboot message handler (Requirements 7.2, 7.3, 7.6)
# --------------------------------------------------------------------------


@given(allow_reboot=ALLOW_REBOOT, check_mode=st.booleans())
def test_message_runs_exactly_when_the_reboot_does_not(render_when, allow_reboot, check_mode) -> None:
    inputs = _inputs(allow_reboot, check_mode)
    reboot_runs = render_when(REBOOT["when"], inputs)
    message_runs = render_when(REPORT["when"], inputs)
    assert message_runs is (not reboot_runs)


@given(allow_reboot=ALLOW_REBOOT, check_mode=st.booleans(), hostname=st.from_regex(r"[a-z][a-z0-9-]{0,14}", fullmatch=True))
def test_message_wording_depends_on_check_mode_and_names_the_variable(
    render_text, allow_reboot, check_mode, hostname
) -> None:
    inputs = _inputs(allow_reboot, check_mode) | {"inventory_hostname": hostname}
    message = render_text(REPORT["ansible.builtin.debug"]["msg"], inputs)
    assert message.startswith(hostname + " ")
    if check_mode:
        assert "would need a reboot" in message
    else:
        assert re.search(r"\bneeds a reboot\b", message)
        assert "would need" not in message
    assert "raspi_config_allow_reboot" in message
    assert "\n" not in message


# --------------------------------------------------------------------------
# Timeout failure handler (Requirements 7.6, 7.7), as implemented in the file
# --------------------------------------------------------------------------


@given(result=REBOOT_RESULTS)
def test_failure_runs_iff_the_result_is_defined_not_skipped_and_has_a_message(render_when, result) -> None:
    runs = render_when(FAIL["when"], _inputs(True, False, result))
    assert runs is (result is TIMEOUT_RESULT)


@given(allow_reboot=ALLOW_REBOOT, check_mode=st.booleans(), result=REBOOT_RESULTS)
def test_failure_never_runs_when_the_reboot_handler_was_skipped(render_when, allow_reboot, check_mode, result) -> None:
    """Whatever the registered result, a skipped Reboot handler cannot fail the host.

    When the ``Reboot`` handler's ``when`` is false the play registers the skipped
    result, so the failure handler sees that result and must not run.
    """
    if render_when(REBOOT["when"], _inputs(allow_reboot, check_mode)):
        registered = result
    else:
        registered = SKIPPED_RESULT
    runs = render_when(FAIL["when"], _inputs(allow_reboot, check_mode, registered))
    if not render_when(REBOOT["when"], _inputs(allow_reboot, check_mode)):
        assert runs is False
    else:
        assert runs is (registered is TIMEOUT_RESULT)


@given(hostname=st.from_regex(r"[a-z][a-z0-9-]{0,14}", fullmatch=True))
def test_failure_message_names_the_host_and_the_timeout(render_text, hostname) -> None:
    message = render_text(FAIL["ansible.builtin.fail"]["msg"], {"inventory_hostname": hostname})
    assert message.startswith(hostname + " ")
    assert "600 seconds" in message


def test_failure_condition_does_not_depend_on_the_failed_key() -> None:
    """``failed_when: false`` makes ``is failed`` always false, so the file must not use it."""
    conditions = " ".join(FAIL["when"])
    assert "is failed" not in conditions
    assert ".failed" not in conditions
