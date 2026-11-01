"""Example tests for ``meta/main.yml``.

**Validates: Requirements 1.1, 1.2**
"""

from __future__ import annotations

import pytest

import harness


@pytest.fixture(scope="module")
def galaxy_info(role_root) -> dict:
    meta = harness.load_yaml(role_root / "meta" / "main.yml")
    return meta["galaxy_info"]


def test_platforms_list_is_exactly_debian_trixie(galaxy_info):
    """Requirement 1.1: Debian is the only platform and trixie its only version."""
    platforms = galaxy_info["platforms"]
    assert len(platforms) == 1
    assert platforms[0]["name"] == "Debian"
    assert list(platforms[0]["versions"]) == ["trixie"]


def test_min_ansible_version_is_2_18(galaxy_info):
    """Requirement 1.2: min_ansible_version is the string "2.18" (not the float 2.18)."""
    assert galaxy_info["min_ansible_version"] == "2.18"
    assert isinstance(galaxy_info["min_ansible_version"], str)
