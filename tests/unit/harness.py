"""Rendering harness for the controller-side tests.

Builds an ansible-core ``Templar`` from ``defaults/main.yml``, ``vars/main.yml``
and generated inputs, so that the named expressions, ``when`` lists, ``argv``
templates and ``fail_msg`` strings of the role are rendered by Ansible's own
templating engine (``regex_replace``, ``urlencode``, ``hash``,
``password_hash``, ``ternary`` and so on behave as they do in a real play).

The module is tolerant: a missing role file loads as an empty mapping, so the
harness imports and runs while other parts of the role are still being written.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, Mapping

from ansible.parsing.dataloader import DataLoader
from ansible.template import Templar
from hypothesis import HealthCheck, settings

try:  # ansible-core 2.19+ only templates strings that are marked as trusted.
    from ansible.template import trust_as_template as _trust_as_template
except ImportError:  # ansible-core < 2.19
    _trust_as_template = None

ROLE_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = UNIT_DIR / "fixtures"
UPSTREAM_SCRIPT = FIXTURES_DIR / "raspi-config-trixie"

# --------------------------------------------------------------------------
# Hypothesis settings
# --------------------------------------------------------------------------

#: Minimum number of examples for every property test (design, "Iterations").
MIN_EXAMPLES = 100
#: Examples for tests over large string spaces (Properties 7 to 11, 23, 31).
LARGE_EXAMPLES = 200

PROFILE_NAME = "raspi_config"


def register_profile() -> None:
    """Register and load the shared Hypothesis profile (idempotent)."""
    settings.register_profile(
        PROFILE_NAME,
        max_examples=MIN_EXAMPLES,
        # Rendering through Templar is slow on the first call; no per-example deadline.
        deadline=None,
        # The rendering fixtures are session scoped and never mutated by a test.
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
        # Keep the example database next to the tests instead of the working directory.
        database=_example_database(),
    )
    settings.load_profile(PROFILE_NAME)


def _example_database():
    try:
        from hypothesis.database import DirectoryBasedExampleDatabase

        return DirectoryBasedExampleDatabase(str(UNIT_DIR / ".hypothesis" / "examples"))
    except Exception:  # pragma: no cover - fall back to the Hypothesis default
        return None


#: Use as ``@pbt_settings`` / ``@pbt_settings_large`` on a property test.
pbt_settings = settings(max_examples=MIN_EXAMPLES)
pbt_settings_large = settings(max_examples=LARGE_EXAMPLES)

# --------------------------------------------------------------------------
# Loading role data
# --------------------------------------------------------------------------

_loader = DataLoader()


def load_yaml(path: os.PathLike | str, default: Any = None) -> Any:
    """Load a YAML file with Ansible's loader (keeps template trust on 2.19+).

    A missing or empty file returns ``default`` (an empty dict when ``None``).
    """
    p = Path(path)
    if not p.is_file():
        return {} if default is None else default
    data = _loader.load_from_file(str(p))
    if data is None:
        return {} if default is None else default
    return data


def load_defaults(root: Path = ROLE_ROOT) -> dict:
    return dict(load_yaml(root / "defaults" / "main.yml") or {})


def load_role_vars(root: Path = ROLE_ROOT) -> dict:
    return dict(load_yaml(root / "vars" / "main.yml") or {})


#: Facts every rendering needs unless the caller overrides them.
DEFAULT_CONTEXT: dict[str, Any] = {
    "ansible_check_mode": False,
    "inventory_hostname": "testhost",
}


def build_variables(
    inputs: Mapping[str, Any] | None = None,
    *,
    defaults: Mapping[str, Any] | None = None,
    role_vars: Mapping[str, Any] | None = None,
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge variables in Ansible precedence order.

    ``defaults/main.yml`` < ``vars/main.yml`` < generated ``inputs``; ``context``
    (``ansible_check_mode``, ``inventory_hostname``, ``ansible_facts`` ...) sits
    below the role data so a test can still override any of them through
    ``inputs``.
    """
    merged: dict[str, Any] = dict(DEFAULT_CONTEXT)
    merged.update(context or {})
    merged.update(load_defaults() if defaults is None else defaults)
    merged.update(load_role_vars() if role_vars is None else role_vars)
    merged.update(inputs or {})
    return merged


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def trust(value: Any) -> Any:
    """Mark every string in ``value`` as a trusted template (no-op before 2.19)."""
    if _trust_as_template is None:
        return value
    if isinstance(value, str):
        return _trust_as_template(value)
    if isinstance(value, list):
        return [trust(v) for v in value]
    if isinstance(value, tuple):
        return tuple(trust(v) for v in value)
    if isinstance(value, dict):
        return {k: trust(v) for k, v in value.items()}
    return value


def make_templar(variables: Mapping[str, Any]) -> Templar:
    """Return an ansible-core ``Templar`` over ``variables``."""
    return Templar(loader=_loader, variables=trust(dict(variables)))


def render(templar: Templar, value: Any) -> Any:
    """Render ``value`` (string, list or dict) with Ansible's templating rules.

    Undefined variables raise, as they do in a play with the default
    ``DEFAULT_UNDEFINED_VAR_BEHAVIOR``.
    """
    return templar.template(trust(value))


def render_expression(templar: Templar, expression: str) -> Any:
    """Render ``{{ expression }}``; ``expression`` may be a variable name."""
    return render(templar, "{{ " + expression + " }}")


def render_when(templar: Templar, conditions: Any) -> bool:
    """Evaluate a ``when`` value with Ansible's semantics.

    A missing ``when`` is true. A list is the logical AND of its items. Booleans
    are used as they are. Strings are evaluated as Jinja expressions, like
    Ansible's ``Conditional`` does.
    """
    if conditions is None:
        return True
    if not isinstance(conditions, (list, tuple)):
        conditions = [conditions]
    for cond in conditions:
        if isinstance(cond, bool):
            result = cond
        else:
            text = str(cond).strip()
            if text in ("True", "true"):
                result = True
            elif text in ("False", "false"):
                result = False
            else:
                rendered = render(templar, "{% if " + text + " %}True{% else %}False{% endif %}")
                result = rendered is True or str(rendered) == "True"
        if not result:
            return False
    return True


def render_argv(templar: Templar, task: Any) -> list[str]:
    """Render the ``argv`` of a parsed ``command`` task into a list of strings."""
    argv = task.argv
    if argv is None:
        raise ValueError(f"task {task.name!r} has no argv")
    rendered = render(templar, argv)
    if not isinstance(rendered, list):
        raise ValueError(f"argv of {task.name!r} rendered to {type(rendered).__name__}, not a list")
    return [str(item) for item in rendered]


def render_text(templar: Templar, text: Any) -> str:
    """Render a message template (``fail_msg``, ``msg`` ...) to a string."""
    return str(render(templar, text))


def flatten(value: Any) -> Iterable[str]:
    """Yield every string found in nested lists, dicts and tuples (for leak checks)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for k, v in value.items():
            yield from flatten(k)
            yield from flatten(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from flatten(v)
    elif value is not None:
        yield str(value)
