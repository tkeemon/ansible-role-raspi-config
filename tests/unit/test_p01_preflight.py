"""Property 1: Preflight classification.

For any pair (distribution, release) of strings, the release assertion passes if
and only if the distribution is ``Debian`` (or the alias ``Raspbian``, C10) and
the release is ``trixie``; when it fails, the message contains the given
distribution, the given release, and ``trixie``. For any ``get_pi_type`` result
(rc, stdout), the Pi_Model classifier returns the model when rc is 0 and the
trimmed stdout is one of ``0`` to ``5``. It returns "not a Raspberry Pi" when rc
is 0 and the trimmed stdout is ``-1``. For every other result it returns an error
whose message contains the stdout and the rc.

The classifier here is not a re-implementation: it renders the ``that``
conditions and ``fail_msg`` templates of the assert tasks in
``tasks/preflight.yml`` and the ``set_fact`` task that stores the Pi_Model, with
ansible-core's Templar, and reads the outcome from the first failing assert.

**Validates: Requirements 1.3, 1.6, 1.7, 6.5**
"""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

import harness
import strategies as strat

MODEL_STDOUTS = ["0", "1", "2", "3", "4", "5"]
PI_TYPE_KEYS = ["-1", *MODEL_STDOUTS]

RELEASE_TASK = "Assert that the Target_Host runs Debian trixie"
NOT_A_PI_TASK = "Assert that the Target_Host is a Raspberry Pi"
KNOWN_MODEL_TASK = "Assert that the Pi_Model is known"
MODEL_FACT_TASK = "Set the Pi_Model fact"

# Text strategy for distribution and release: accepted values, near misses, free text.
_NEAR_DISTRIBUTIONS = ["Debian", "Raspbian", "debian", "DEBIAN", "Ubuntu", "Debian ", " Debian", "Debian\n", ""]
_NEAR_RELEASES = ["trixie", "Trixie", "bookworm", "bullseye", "trixie ", " trixie", "trixie/sid", "sid", ""]

distributions = st.one_of(st.sampled_from(_NEAR_DISTRIBUTIONS), st.text(max_size=20))
releases = st.one_of(st.sampled_from(_NEAR_RELEASES), st.text(max_size=20))


@pytest.fixture(scope="module")
def preflight(parsed_role):
    """Preflight tasks by name."""
    by_name = {t.name: t for t in parsed_role.by_file("preflight.yml")}
    for name in (RELEASE_TASK, NOT_A_PI_TASK, KNOWN_MODEL_TASK, MODEL_FACT_TASK):
        assert name in by_name, f"tasks/preflight.yml has no task named {name!r}"
    return by_name


def _assert_outcome(templar, task):
    """Evaluate an ``ansible.builtin.assert`` task: ``(passed, rendered fail_msg)``."""
    assert task.short_module == "assert", task.label()
    passed = harness.render_when(templar, task.args["that"])
    message = None if passed else harness.render_text(templar, task.args["fail_msg"])
    return passed, message


# --------------------------------------------------------------------------
# Release assertion
# --------------------------------------------------------------------------


@given(distribution=distributions, release=releases)
def test_release_assertion_passes_only_for_debian_or_raspbian_trixie(
    distribution: str, release: str, preflight, make_templar
) -> None:
    templar = make_templar(
        ansible_facts={"distribution": distribution, "distribution_release": release},
    )
    passed, message = _assert_outcome(templar, preflight[RELEASE_TASK])

    assert passed == (distribution in ("Debian", "Raspbian") and release == "trixie")
    if not passed:
        assert distribution in message
        assert release in message
        assert "trixie" in message


@pytest.mark.parametrize("distribution", ["Debian", "Raspbian"])
def test_release_assertion_accepts_trixie(distribution: str, preflight, make_templar) -> None:
    templar = make_templar(ansible_facts={"distribution": distribution, "distribution_release": "trixie"})
    assert _assert_outcome(templar, preflight[RELEASE_TASK]) == (True, None)


def test_release_assertion_fails_with_unknown_when_facts_are_missing(preflight, make_templar) -> None:
    passed, message = _assert_outcome(make_templar(ansible_facts={}), preflight[RELEASE_TASK])
    assert not passed
    assert "unknown" in message and "trixie" in message


# --------------------------------------------------------------------------
# Pi_Model classification
# --------------------------------------------------------------------------


def classify(preflight, make_templar, rc: int, stdout: str, stderr: str):
    """Run the Pi_Model assertions in file order.

    Returns ``("model", n)``, ``("not_a_pi", message)`` or ``("error", message)``.
    """
    templar = make_templar(
        raspi_config__pi_type={"rc": rc, "stdout": stdout, "stderr": stderr},
        inventory_hostname="pi-host",
    )
    for name, kind in ((NOT_A_PI_TASK, "not_a_pi"), (KNOWN_MODEL_TASK, "error")):
        passed, message = _assert_outcome(templar, preflight[name])
        if not passed:
            return kind, message

    # The set_fact task loops over a one-item list so the fact stays an integer.
    fact = preflight[MODEL_FACT_TASK]
    items = harness.render(templar, fact.raw["loop"])
    assert isinstance(items, list) and len(items) == 1
    item_templar = make_templar(
        raspi_config__pi_type={"rc": rc, "stdout": stdout, "stderr": stderr},
        item=items[0],
    )
    model = harness.render(item_templar, fact.args["raspi_config__pi_model"])
    return "model", model


pi_type_results = strat.check_results(PI_TYPE_KEYS)


@given(result=pi_type_results)
def test_pi_type_results_are_classified(result, preflight, make_templar) -> None:
    kind, value = classify(preflight, make_templar, result.rc, result.stdout, result.stderr)
    trimmed = result.stdout.strip()

    if result.rc == 0 and trimmed in MODEL_STDOUTS:
        assert kind == "model"
        assert value == int(trimmed)
        assert isinstance(value, int) and not isinstance(value, bool)
    elif result.rc == 0 and trimmed == "-1":
        assert kind == "not_a_pi"
        assert "not a Raspberry Pi" in value
    else:
        assert kind == "error"
        assert trimmed in value
        assert str(result.rc) in value
        assert "not a Raspberry Pi" not in value


@given(rc=st.integers(1, 255), stdout=st.sampled_from(PI_TYPE_KEYS))
def test_nonzero_rc_is_always_an_error_even_for_valid_output(rc: int, stdout: str, preflight, make_templar) -> None:
    kind, message = classify(preflight, make_templar, rc, stdout, "")
    assert kind == "error"
    assert stdout in message and f"exit status {rc}" in message


@pytest.mark.parametrize("stdout", MODEL_STDOUTS)
def test_each_model_output_yields_that_integer(stdout: str, preflight, make_templar) -> None:
    assert classify(preflight, make_templar, 0, f" {stdout}\n", "") == ("model", int(stdout))


def test_error_message_includes_stderr(preflight, make_templar) -> None:
    kind, message = classify(preflight, make_templar, 127, "", "raspi-config: boom")
    assert kind == "error" and "raspi-config: boom" in message
