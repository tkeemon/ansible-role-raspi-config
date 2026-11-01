"""Unit tests for ``tasks/first_boot.yml`` (removal of the first-boot raspi-config prompt).

The file has two ``ansible.builtin.file`` tasks with ``state: absent``: one for the login
shell hook and one for the getty override. Only the override file notifies
``Reload systemd``. The ``getty@tty1.service.d`` directory is never removed, so no task
may target it. ``ansible.builtin.file`` supports check mode and reports the failing path
natively, which covers the check-mode and failure criteria.

**Validates: Requirements 18.1, 18.2, 18.3**
"""

from __future__ import annotations

import pytest

PROFILE_HOOK = "/etc/profile.d/raspi-config.sh"
GETTY_DIR = "/etc/systemd/system/getty@tty1.service.d"
GETTY_OVERRIDE = f"{GETTY_DIR}/raspi-config-override.conf"


@pytest.fixture(scope="module")
def first_boot_tasks(parsed_role):
    return parsed_role.by_file("first_boot.yml")


def _paths(tasks) -> list[str]:
    return [t.args["path"] for t in tasks]


def _task_for(tasks, path: str):
    matches = [t for t in tasks if t.args["path"] == path]
    assert len(matches) == 1, f"expected exactly one task for {path}"
    return matches[0]


def test_exactly_the_two_paths_are_managed(first_boot_tasks) -> None:
    assert len(first_boot_tasks) == 2
    assert all(t.short_module == "file" for t in first_boot_tasks)
    assert sorted(_paths(first_boot_tasks)) == sorted([PROFILE_HOOK, GETTY_OVERRIDE])


def test_both_tasks_set_state_absent(first_boot_tasks) -> None:
    for task in first_boot_tasks:
        assert task.args["state"] == "absent", task.label()


def test_only_the_override_file_notifies_reload_systemd(first_boot_tasks) -> None:
    assert _task_for(first_boot_tasks, GETTY_OVERRIDE).notify == ("Reload systemd",)
    assert _task_for(first_boot_tasks, PROFILE_HOOK).notify == ()


def test_the_getty_directory_is_not_removed(first_boot_tasks) -> None:
    assert GETTY_DIR not in _paths(first_boot_tasks)
    for task in first_boot_tasks:
        assert task.args["path"].endswith((".sh", ".conf")), task.label()
        assert task.args["state"] != "directory"
