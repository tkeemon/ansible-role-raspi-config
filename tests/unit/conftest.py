"""Shared fixtures for the controller-side tests (pytest + Hypothesis).

Fixtures
--------
``role_root``            path of the role
``role_defaults``        parsed ``defaults/main.yml`` (``{}`` while missing)
``role_vars``            parsed ``vars/main.yml`` (``{}`` while missing)
``role_variables``       defaults < vars, the base for every rendering
``make_templar``         factory: ``make_templar(**inputs)`` -> ansible-core ``Templar``
``render_expression``    ``render_expression("raspi_config__valid_hostname", raspi_config_hostname="x")``
``render_when``          evaluate a ``when`` value (or list) with the generated inputs
``render_argv``          render the ``argv`` of a parsed task into a list of strings
``render_text``          render a ``fail_msg`` / ``msg`` template
``parsed_role``          ``taskparser.ParsedRole`` for ``tasks/``
``parsed_tasks``         flat list of ``ParsedTask``
``upstream_script``      text of the pinned Upstream_Script
``upstream_functions``   names defined as ``name() {`` in the pinned Upstream_Script

All fixtures are session scoped, so Hypothesis tests can use them without the
function-scoped-fixture health check. Rendering helpers take the variables per
call, so nothing is shared between examples.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

# Make ``harness``, ``taskparser`` and ``strategies`` importable from any test module.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import harness  # noqa: E402
import taskparser  # noqa: E402

harness.register_profile()


@pytest.fixture(scope="session")
def role_root() -> Path:
    return harness.ROLE_ROOT


@pytest.fixture(scope="session")
def role_defaults() -> dict:
    return harness.load_defaults()


@pytest.fixture(scope="session")
def role_vars() -> dict:
    return harness.load_role_vars()


@pytest.fixture(scope="session")
def role_variables(role_defaults: dict, role_vars: dict) -> dict:
    """``defaults/main.yml`` overlaid with ``vars/main.yml``."""
    return harness.build_variables(defaults=role_defaults, role_vars=role_vars)


@pytest.fixture(scope="session")
def make_templar(role_defaults: dict, role_vars: dict) -> Callable[..., Any]:
    """``make_templar(inputs=None, **more_inputs)`` -> ``Templar``.

    Variables are ``defaults/main.yml`` < ``vars/main.yml`` < ``inputs`` (a mapping,
    for names that are not valid keyword arguments) < keyword inputs.
    """

    def factory(inputs: dict | None = None, **more_inputs: Any):
        merged = dict(inputs or {})
        merged.update(more_inputs)
        variables = harness.build_variables(merged, defaults=role_defaults, role_vars=role_vars)
        return harness.make_templar(variables)

    return factory


@pytest.fixture(scope="session")
def render_expression(make_templar) -> Callable[..., Any]:
    """``render_expression(name_or_expr, inputs=None, **more_inputs)``."""

    def render(expression: str, inputs: dict | None = None, **more_inputs: Any) -> Any:
        return harness.render_expression(make_templar(inputs, **more_inputs), expression)

    return render


@pytest.fixture(scope="session")
def render_when(make_templar) -> Callable[..., bool]:
    """``render_when(conditions, inputs=None, **more_inputs)`` -> bool.

    ``conditions`` is a ``when`` value, or a ``ParsedTask``/``ParsedBlock`` whose
    effective ``when`` list is evaluated.
    """

    def evaluate(conditions: Any, inputs: dict | None = None, **more_inputs: Any) -> bool:
        if hasattr(conditions, "effective_when"):
            conditions = conditions.effective_when
        return harness.render_when(make_templar(inputs, **more_inputs), conditions)

    return evaluate


@pytest.fixture(scope="session")
def render_argv(make_templar) -> Callable[..., list[str]]:
    """``render_argv(task, inputs=None, **more_inputs)`` -> list of strings."""

    def render(task: Any, inputs: dict | None = None, **more_inputs: Any) -> list[str]:
        return harness.render_argv(make_templar(inputs, **more_inputs), task)

    return render


@pytest.fixture(scope="session")
def render_text(make_templar) -> Callable[..., str]:
    """``render_text(template, inputs=None, **more_inputs)`` -> string."""

    def render(template: Any, inputs: dict | None = None, **more_inputs: Any) -> str:
        return harness.render_text(make_templar(inputs, **more_inputs), template)

    return render


@pytest.fixture(scope="session")
def parsed_role(role_root: Path) -> taskparser.ParsedRole:
    return taskparser.parse_role(role_root)


@pytest.fixture(scope="session")
def parsed_tasks(parsed_role: taskparser.ParsedRole) -> list[taskparser.ParsedTask]:
    return parsed_role.tasks


@pytest.fixture(scope="session")
def upstream_script() -> str:
    return harness.UPSTREAM_SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def upstream_functions(upstream_script: str) -> frozenset[str]:
    """Shell functions defined in the pinned Upstream_Script (``^name() {``)."""
    return frozenset(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\(\)\s*\{", upstream_script, flags=re.MULTILINE))
