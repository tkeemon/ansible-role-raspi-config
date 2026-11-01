"""Property 13: Deprecation warnings match defined variables.

For any subset of the six Deprecated_Variables defined with arbitrary values, the
deprecation task prints exactly one warning per defined variable, and each warning
names the variable and its Option. For all task files other than ``deprecations.yml``,
no task's ``when``, ``argv``, ``loop``, or ``environment`` references a
Deprecated_Variable name.

The task in ``tasks/deprecations.yml`` is a single looping ``debug`` task. The test
renders its ``loop``, then renders ``when`` and ``msg`` once per item, with the
generated Deprecated_Variables defined as play variables, so the
``lookup('ansible.builtin.vars', ...)`` default is evaluated by Ansible's own engine.

**Validates: Requirements 8.4, 8.6, 8.7**
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given

import harness
import strategies

try:  # Resolve FQCN plugins such as ``ansible.builtin.vars`` outside ansible-playbook.
    from ansible.plugins.loader import init_plugin_loader
except ImportError:  # pragma: no cover - ansible-core releases without the function
    pass
else:
    init_plugin_loader()

DEPRECATIONS_FILE = "deprecations.yml"
DEPRECATED = harness.load_role_vars().get("raspi_config__deprecated_variables") or []
NAMES = [entry["name"] for entry in DEPRECATED]
OPTION_OF = {entry["name"]: entry["option"] for entry in DEPRECATED}


@pytest.fixture(scope="module")
def deprecation_task(parsed_role):
    tasks = parsed_role.by_file(DEPRECATIONS_FILE)
    assert len(tasks) == 1, "tasks/deprecations.yml must hold exactly one task"
    task = tasks[0]
    assert task.short_module == "debug"
    return task


def _warnings(task, render_expression, render_when, render_text, defined: dict) -> list[str]:
    """Messages the task prints, one per loop item whose ``when`` is true."""
    items = render_expression(task.raw["loop"].strip().removeprefix("{{").removesuffix("}}").strip(), defined)
    messages = []
    for item in items:
        inputs = {**defined, "item": item}
        if render_when(task.effective_when, inputs):
            messages.append(render_text(task.args["msg"], inputs))
    return messages


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


def test_the_deprecated_list_has_the_six_variables_with_options() -> None:
    assert len(NAMES) == 6
    assert len(set(NAMES)) == 6
    assert all(OPTION_OF[name] for name in NAMES)


# --------------------------------------------------------------------------
# One warning per defined variable (Requirements 8.4, 8.6)
# --------------------------------------------------------------------------


@given(defined=strategies.deprecated_subsets())
def test_one_warning_per_defined_deprecated_variable(
    deprecation_task, render_expression, render_when, render_text, defined
) -> None:
    messages = _warnings(deprecation_task, render_expression, render_when, render_text, defined)

    assert len(messages) == len(defined)
    for name in defined:
        matching = [m for m in messages if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", m)]
        assert len(matching) == 1, f"expected exactly one warning for {name}"
        assert "[DEPRECATED]" in matching[0]
        assert OPTION_OF[name] in matching[0]


@given(defined=strategies.deprecated_subsets())
def test_no_warning_for_variables_that_are_not_defined(
    deprecation_task, render_expression, render_when, render_text, defined
) -> None:
    messages = _warnings(deprecation_task, render_expression, render_when, render_text, defined)
    joined = "\n".join(messages)
    for name in set(NAMES) - set(defined):
        assert name not in joined


def test_nothing_is_printed_when_no_deprecated_variable_is_defined(
    deprecation_task, render_expression, render_when, render_text
) -> None:
    assert _warnings(deprecation_task, render_expression, render_when, render_text, {}) == []


def test_message_is_built_from_the_item_only(deprecation_task) -> None:
    """The message reads ``item`` and nothing else, so the value is never printed (Requirement 8.7)."""
    template = str(deprecation_task.args["msg"])
    assert "lookup" not in template
    assert set(re.findall(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)", template)) == {"item"}


def test_task_loops_over_the_data_table_and_hides_the_value(deprecation_task) -> None:
    assert "raspi_config__deprecated_variables" in str(deprecation_task.raw["loop"])
    assert deprecation_task.raw["loop_control"]["label"] == "{{ item.name }}"


# --------------------------------------------------------------------------
# Other task files never reference a Deprecated_Variable (Requirement 8.6)
# --------------------------------------------------------------------------


def _referenced_text(task) -> str:
    """Text of the ``when``, ``argv``, ``loop`` and ``environment`` of ``task``,
    including the conditions and environment inherited from enclosing blocks."""
    parts = [str(c) for c in task.effective_when]
    parts.append(str(task.argv))
    parts.append(str(task.raw.get("loop")))
    parts.append(str(task.raw.get("with_items")))
    parts.append(str(task.environment))
    for block in task.block_chain:
        parts.append(str(block.environment))
    return "\n".join(parts)


def test_no_other_task_references_a_deprecated_variable(parsed_tasks) -> None:
    offenders = []
    for task in parsed_tasks:
        if task.file == DEPRECATIONS_FILE:
            continue
        text = _referenced_text(task)
        for name in NAMES:
            if name in text:
                offenders.append(f"{task.label()} references {name}")
    assert not offenders, "\n".join(offenders)


def test_deprecated_names_appear_in_no_task_file_other_than_the_deprecation_task(role_root) -> None:
    """Stricter than the property: not even a name in a comment-free task body."""
    offenders = []
    for path in sorted((role_root / "tasks").glob("*.yml")):
        if path.name == DEPRECATIONS_FILE:
            continue
        content = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {name}" for name in NAMES if name in content]
    assert not offenders, "\n".join(offenders)
