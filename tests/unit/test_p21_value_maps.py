"""Property 21: Value maps round-trip.

For any D6 mode, mapping it to its ``do_squeekboard`` code and mapping the code's
``get_squeekboard`` output back returns the same mode. For any Pi_Model in {1, 2}
and any profile accepted for that model, mapping the profile to its ``arm_freq``
value and back through the P1 state rule returns the same profile, and an
``arm_freq`` value that matches no profile is classified as a failure. For any A11
value, the ``do_journald_storage`` code is in 1 to 5 and distinct values map to
distinct codes.

The tests read the maps from ``vars/main.yml``. The Upstream_Script fixture is the
independent oracle for the pairing of ``do_squeekboard`` codes with
``get_squeekboard`` outputs and for the ``do_journald_storage`` codes.

**Validates: Requirements 12.6, 14.1, 16.6**
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, strategies as st

import harness

ROLE_VARS = harness.load_role_vars()
SQUEEK_CODES: dict = ROLE_VARS["raspi_config__squeekboard_codes"]
SQUEEK_OUTPUTS: dict = ROLE_VARS["raspi_config__squeekboard_outputs"]
OVERCLOCK_PROFILES: dict = ROLE_VARS["raspi_config__overclock_profiles"]
LOG_CODES: dict = ROLE_VARS["raspi_config__log_storage_codes"]
LOG_ENUM: list = ROLE_VARS["raspi_config__enums"]["raspi_config_log_storage"]
SQUEEK_ENUM: list = ROLE_VARS["raspi_config__enums"]["raspi_config_onscreen_keyboard"]

# Upstream pairing of do_squeekboard argument -> get_squeekboard output, read from
# the menu and from get_squeekboard in the pinned script: S1 writes an autostart
# file without ``sbtest`` (output 0), S2 writes one with ``sbtest`` (output 1), S3
# removes the autostart file (output 2).
UPSTREAM_SQUEEK_OUTPUT = {"S1": "0", "S2": "1", "S3": "2"}

PI_MODELS_WITH_PROFILES = sorted(OVERCLOCK_PROFILES)


def profile_to_arm_freq(model: int, profile: str) -> str:
    """Value that ``get_config_var arm_freq`` prints after ``do_overclock <profile>``.

    ``None`` clears the overclock, so ``arm_freq`` is absent and the Upstream_Script
    prints ``0``.
    """
    if profile == "None":
        return "0"
    return str(OVERCLOCK_PROFILES[model][profile])


def arm_freq_to_profile(model: int, output: str):
    """P1 state rule: the profile whose ``arm_freq`` equals ``output``.

    ``0`` is ``None``. Returns ``None`` (Python) when no profile matches, which the
    Check_Task reports as a failure.
    """
    text = output.strip()
    if text == "0":
        return "None"
    matches = [name for name, freq in OVERCLOCK_PROFILES[model].items() if str(freq) == text]
    return matches[0] if len(matches) == 1 else None


# --------------------------------------------------------------------------
# D6 onscreen keyboard
# --------------------------------------------------------------------------


@given(mode=st.sampled_from(SQUEEK_ENUM))
def test_squeekboard_mode_round_trips(mode: str) -> None:
    code = SQUEEK_CODES[mode]
    output = UPSTREAM_SQUEEK_OUTPUT[code]
    assert SQUEEK_OUTPUTS[output] == mode


def test_squeekboard_maps_cover_the_enumeration_and_upstream_codes(upstream_script: str) -> None:
    assert set(SQUEEK_CODES) == set(SQUEEK_ENUM)
    assert set(SQUEEK_CODES.values()) == set(UPSTREAM_SQUEEK_OUTPUT)
    assert set(SQUEEK_OUTPUTS) == set(UPSTREAM_SQUEEK_OUTPUT.values())
    assert len(set(SQUEEK_CODES.values())) == len(SQUEEK_CODES)
    for code in SQUEEK_CODES.values():
        assert re.search(rf"^\s*{code}\*\)", upstream_script, flags=re.MULTILINE), code


# --------------------------------------------------------------------------
# P1 overclock
# --------------------------------------------------------------------------


@st.composite
def model_and_accepted_profile(draw):
    model = draw(st.sampled_from(PI_MODELS_WITH_PROFILES))
    profile = draw(st.sampled_from(["None"] + sorted(OVERCLOCK_PROFILES[model])))
    return model, profile


@given(case=model_and_accepted_profile())
def test_overclock_profile_round_trips(case) -> None:
    model, profile = case
    assert arm_freq_to_profile(model, profile_to_arm_freq(model, profile)) == profile


@given(model=st.sampled_from(PI_MODELS_WITH_PROFILES), freq=st.integers(min_value=-10, max_value=3000))
def test_unmatched_arm_freq_is_a_failure(model: int, freq: int) -> None:
    known = {0} | {int(v) for v in OVERCLOCK_PROFILES[model].values()}
    if freq in known:
        assert arm_freq_to_profile(model, str(freq)) is not None
    else:
        assert arm_freq_to_profile(model, str(freq)) is None


@given(model=st.sampled_from(PI_MODELS_WITH_PROFILES), text=st.text(max_size=12))
def test_non_numeric_arm_freq_is_a_failure(model: int, text: str) -> None:
    if text.strip() in {"0"} | {str(v) for v in OVERCLOCK_PROFILES[model].values()}:
        return
    assert arm_freq_to_profile(model, text) is None


@given(model=st.sampled_from(PI_MODELS_WITH_PROFILES))
def test_accepted_overclock_values_match_the_profile_map(model: int, render_expression) -> None:
    accepted = render_expression("raspi_config__overclock_accepted", raspi_config__pi_model=model)
    assert sorted(accepted) == sorted(["None", *OVERCLOCK_PROFILES[model]])


def test_overclock_frequencies_are_distinct_per_model_and_match_upstream(upstream_script: str) -> None:
    for model, profiles in OVERCLOCK_PROFILES.items():
        freqs = list(profiles.values())
        assert len(set(freqs)) == len(freqs), model
        assert 0 not in freqs
    # set_overclock <name> <arm_freq> ... calls in do_overclock (High differs per model).
    upstream = [(m.group(1), int(m.group(2))) for m in re.finditer(r"set_overclock (\w+) (\d+) ", upstream_script)]
    # Pi 1 uses Modest, Medium, High (950) and Turbo; the Pi 2 branch sets High to 1000.
    assert sorted(OVERCLOCK_PROFILES[1].items()) == sorted(
        [p for p in upstream if p != ("High", 1000)]
    )
    assert ("High", 1000) in upstream
    assert OVERCLOCK_PROFILES[2] == {"High": 1000}


# --------------------------------------------------------------------------
# A11 log storage
# --------------------------------------------------------------------------


@given(value=st.sampled_from(LOG_ENUM))
def test_log_storage_code_is_in_range_and_matches_upstream(value: str, upstream_script: str) -> None:
    code = LOG_CODES[value]
    assert isinstance(code, int) and 1 <= code <= 5
    # do_journald_storage turns codes 2..5 into the Storage= string; 1 (and anything
    # else) removes the drop-in, which the Check_Task reads as ``default``.
    match = re.search(rf"^\s*{code}\) JSTRING=\"(\w*)\"", upstream_script, flags=re.MULTILINE)
    if value == "default":
        assert code == 1 and match is None
    else:
        assert match is not None and match.group(1) == value


@given(pair=st.lists(st.sampled_from(LOG_ENUM), min_size=2, max_size=2, unique=True))
def test_distinct_log_storage_values_have_distinct_codes(pair: list[str]) -> None:
    first, second = pair
    assert LOG_CODES[first] != LOG_CODES[second]


def test_log_storage_map_covers_the_enumeration() -> None:
    assert set(LOG_CODES) == set(LOG_ENUM)
    assert sorted(LOG_CODES.values()) == [1, 2, 3, 4, 5]
