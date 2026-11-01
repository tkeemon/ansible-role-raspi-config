"""Hypothesis strategies for the controller-side property tests.

One strategy per row of the design's Testing Strategy table. Strategies that
depend on role data (``enum_values``, ``deprecated_subsets``, ``check_results``)
read ``vars/main.yml`` when they are built and fall back to built-in lists when
the data is missing, so they stay usable while the role is incomplete.
"""

from __future__ import annotations

from typing import Any, NamedTuple, Optional, Sequence

from hypothesis import strategies as st

from harness import load_role_vars

# --------------------------------------------------------------------------
# Generic YAML values (Properties 7, 12, 13)
# --------------------------------------------------------------------------

#: Strings and numbers that YAML 1.1 and Ansible's ``bool`` filter coerce.
COERCIBLE = ["yes", "no", "true", "True", "false", "False", "on", "off", "0", "1", 0, 1]


def _scalars() -> st.SearchStrategy:
    return st.one_of(
        st.text(max_size=20),
        st.integers(min_value=-(2**31), max_value=2**31),
        st.floats(allow_nan=False, allow_infinity=False),
        st.booleans(),
        st.none(),
    )


def yaml_values() -> st.SearchStrategy:
    """Any YAML-shaped value: text, ints, floats, booleans, null, lists.

    Includes the values that look like booleans or numbers (``"yes"``, ``"no"``,
    ``"true"``, ``"True"``, ``0``, ``1``) so that coercion bugs are found.
    """
    return st.one_of(
        _scalars(),
        st.lists(_scalars(), max_size=4),
        st.sampled_from(COERCIBLE),
    )


def _swapcase_variants(value: str) -> list[str]:
    return [value.swapcase(), value.upper(), value.lower(), value.capitalize()]


def enum_values(var: Optional[str] = None, accepted: Optional[Sequence[Any]] = None) -> st.SearchStrategy:
    """Accepted values of ``var`` plus near misses and random values.

    ``accepted`` defaults to ``raspi_config__enums[var]`` from ``vars/main.yml``.
    Generates the accepted values, case-swapped variants, whitespace-padded
    variants, and random text. The empty string is listed in ``accepted`` where
    the Option accepts the Unmanaged_Value.
    """
    if accepted is None:
        accepted = (load_role_vars().get("raspi_config__enums") or {}).get(var, [])
    accepted = [a for a in accepted]
    exact = st.sampled_from(accepted) if accepted else st.nothing()
    strs = [str(a) for a in accepted if isinstance(a, str) and a]
    near = (
        st.sampled_from(strs).flatmap(
            lambda v: st.one_of(
                st.sampled_from(_swapcase_variants(v)),
                st.tuples(st.sampled_from(["", " ", "\t", "\n"]), st.sampled_from(["", " ", "\t", "\n"])).map(
                    lambda pad: pad[0] + v + pad[1]
                ),
                st.just(v[:-1]),
                st.just(v + "x"),
            )
        )
        if strs
        else st.nothing()
    )
    return st.one_of(exact, near, st.text(max_size=20), st.sampled_from([" ", "", "None"]))


# --------------------------------------------------------------------------
# Hostnames, SSIDs, passphrases (Properties 8, 9, 20, 31)
# --------------------------------------------------------------------------

_HOST_LABEL = r"[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?"


def hostnames() -> st.SearchStrategy:
    """Valid labels plus near misses: edge hyphens, dots, underscores, lengths 0 and 64."""
    valid = st.from_regex(_HOST_LABEL, fullmatch=True)
    alnum = st.text(alphabet="abcXYZ019", min_size=1, max_size=10)
    return st.one_of(
        valid,
        alnum.map(lambda s: "-" + s),
        alnum.map(lambda s: s + "-"),
        st.tuples(alnum, alnum).map(lambda p: p[0] + "." + p[1]),
        st.tuples(alnum, alnum).map(lambda p: p[0] + "_" + p[1]),
        alnum.map(lambda s: s + "\n"),  # '$' in a regex matches before a trailing newline
        st.just(""),
        st.text(alphabet="a", min_size=63, max_size=63),
        st.text(alphabet="a", min_size=64, max_size=64),
        st.text(max_size=70),
    )


_UTF8_SAMPLES = ["a", "é", "€", "😀", "\u0000", " "]


def ssids() -> st.SearchStrategy:
    """Full-Unicode SSIDs with byte lengths clustered around the 32-byte limit."""
    mixed = st.lists(st.sampled_from(_UTF8_SAMPLES), max_size=40).map("".join)
    return st.one_of(
        st.text(max_size=40),
        mixed,
        st.integers(min_value=30, max_value=34).map(lambda n: "a" * n),
        st.integers(min_value=14, max_value=18).map(lambda n: "é" * n),  # 2 bytes each
        st.integers(min_value=10, max_value=12).map(lambda n: "€" * n),  # 3 bytes each
        st.integers(min_value=7, max_value=9).map(lambda n: "😀" * n),  # 4 bytes each
        st.just(""),
    )


def psks() -> st.SearchStrategy:
    """Passphrases with lengths clustered around the 8 and 63 character limits."""
    return st.one_of(
        st.text(max_size=70),
        st.integers(min_value=6, max_value=9).flatmap(lambda n: st.text(min_size=n, max_size=n)),
        st.integers(min_value=61, max_value=65).flatmap(lambda n: st.text(min_size=n, max_size=n)),
        st.just(""),
    )


# --------------------------------------------------------------------------
# Reference files (Property 10)
# --------------------------------------------------------------------------


class ReferenceFile(NamedTuple):
    """Generated reference file.

    ``members`` are the values the matching predicate must accept;
    ``lookalikes`` appear in the file in a position that must not match
    (comments, other columns, other sections).
    """

    content: str
    members: frozenset[str]
    lookalikes: frozenset[str]


_UPPER2 = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2)
_NAME = st.text(alphabet="abcdefghij KLMNOP-", min_size=1, max_size=15).map(str.strip).filter(bool)
_CHARSET = st.sampled_from(["UTF-8", "ISO-8859-1", "ISO-8859-15", "EUC-JP"])
_LANG = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=3)
_REGION = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=2)
_CODE = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=2, max_size=8)


@st.composite
def tab_files(draw) -> ReferenceFile:
    """``/usr/share/zoneinfo/iso3166.tab``: comments, blank lines, ``CC<TAB>Name`` rows."""
    lines: list[str] = ["# comment line", ""]
    members: set[str] = set()
    look: set[str] = set()
    for _ in range(draw(st.integers(0, 12))):
        kind = draw(st.sampled_from(["row", "row", "commented", "space", "name_column", "blank", "comment"]))
        code, name = draw(_UPPER2), draw(_NAME)
        if kind == "row":
            lines.append(f"{code}\t{name}")
            members.add(code)
        elif kind == "commented":
            lines.append(f"#{code}\t{name}")
            look.add(code)
        elif kind == "space":
            lines.append(f"{code} {name}")  # separator is not a tab
            look.add(code)
        elif kind == "name_column":
            other = draw(_UPPER2)
            lines.append(f"{other}\t{code} {name}")
            members.add(other)
            look.add(code)
        elif kind == "blank":
            lines.append("")
        else:
            lines.append(f"# {name}")
    look -= members
    return ReferenceFile("\n".join(lines) + "\n", frozenset(members), frozenset(look))


@st.composite
def supported_files(draw) -> ReferenceFile:
    """``/usr/share/i18n/SUPPORTED``: ``locale CHARSET`` rows (first field is the locale)."""
    lines: list[str] = ["# SUPPORTED", ""]
    members: set[str] = set()
    look: set[str] = set()
    for _ in range(draw(st.integers(0, 12))):
        kind = draw(st.sampled_from(["utf8", "plain", "commented", "blank"]))
        lang, region, cs = draw(_LANG), draw(_REGION), draw(_CHARSET)
        if kind == "utf8":
            loc = f"{lang}_{region}.UTF-8"
            lines.append(f"{loc} UTF-8")
            members.add(loc)
            look.update({f"{lang}_{region}", "UTF-8"})
        elif kind == "plain":
            loc = f"{lang}_{region}"
            lines.append(f"{loc} {cs}")
            members.add(loc)
            look.add(cs)
        elif kind == "commented":
            loc = f"{lang}_{region}.UTF-8"
            lines.append(f"#{loc} UTF-8")
            look.add(loc)
        else:
            lines.append("")
    look -= members
    return ReferenceFile("\n".join(lines) + "\n", frozenset(members), frozenset(look))


@st.composite
def base_lst(draw) -> ReferenceFile:
    """``/usr/share/X11/xkb/rules/base.lst``: ``! model|layout|variant|option`` sections."""
    sections = ["model", "layout", "variant", "option"]
    order = draw(st.permutations(sections))
    lines: list[str] = []
    in_layout: set[str] = set()
    elsewhere: set[str] = set()
    for sec in order:
        lines.append(f"! {sec}")
        for _ in range(draw(st.integers(0, 6))):
            code, desc = draw(_CODE), draw(_NAME)
            if draw(st.booleans()):
                lines.append(f"  {code:<15} {desc}")
                (in_layout if sec == "layout" else elsewhere).add(code)
            else:
                lines.append("")
        lines.append("")
    return ReferenceFile("\n".join(lines) + "\n", frozenset(in_layout), frozenset(elsewhere - in_layout))


# --------------------------------------------------------------------------
# Proxy values (Property 11)
# --------------------------------------------------------------------------

#: One character from every Unicode whitespace class that ``str.isspace`` accepts.
WHITESPACE_CHARS = [
    " ", "\t", "\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x1f", "\x85", "\xa0",
    "\u1680", "\u2000", "\u2001", "\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007",
    "\u2008", "\u2009", "\u200a", "\u2028", "\u2029", "\u202f", "\u205f", "\u3000",
]

_URLISH = st.builds(
    lambda scheme, host, port: f"{scheme}://{host}:{port}",
    st.sampled_from(["http", "https", "socks5", "ftp"]),
    st.from_regex(r"[a-z0-9]([a-z0-9.-]{0,20}[a-z0-9])?", fullmatch=True),
    st.integers(1, 65535),
)


def proxy_values() -> st.SearchStrategy:
    """URL-like strings, strings with each whitespace class, lengths around 2048."""
    with_ws = st.tuples(_URLISH, st.sampled_from(WHITESPACE_CHARS), st.integers(0, 2)).map(
        lambda t: t[0][: len(t[0]) // 2] + t[1] + t[0][len(t[0]) // 2 :]
        if t[2] == 0
        else (t[1] + t[0] if t[2] == 1 else t[0] + t[1])
    )
    sized = st.integers(2046, 2050).map(lambda n: "http://" + "a" * (n - 7))
    return st.one_of(_URLISH, with_ws, sized, st.just(""), st.text(max_size=40))


# --------------------------------------------------------------------------
# Check results (Properties 2, 3, 4)
# --------------------------------------------------------------------------


class CheckResult(NamedTuple):
    rc: int
    stdout: str
    stderr: str


def output_keys(option: Any = None) -> list[str]:
    """Keys of an Option's Check_Task output map.

    ``option`` may be an iterable of keys (the Option's own output map) or
    ``None``/a TASK_NAME, for which the boolean map ``0``/``1`` is used.
    """
    if option is None or isinstance(option, str):
        return ["0", "1"]
    return [str(k) for k in option]


def check_results(option: Any = None) -> st.SearchStrategy:
    """``(rc, stdout, stderr)`` with rc in -1..255 and stdout from the Option's map keys,
    padded keys, or random text."""
    keys = output_keys(option)
    key = st.sampled_from(keys)
    stdout = st.one_of(
        key,
        key.map(lambda k: k + "\n"),
        key.map(lambda k: " " + k + " \n"),
        key.map(lambda k: k + k),
        key.map(lambda k: k + "\nextra"),
        st.sampled_from(["", "\n", "-1", "2", "yes", "ok"]),
        st.text(max_size=20),
    )
    return st.builds(CheckResult, st.integers(-1, 255), stdout, st.text(max_size=30))


# --------------------------------------------------------------------------
# Hardware (Properties 6, 25)
# --------------------------------------------------------------------------

PI_MODELS = [0, 1, 2, 3, 4, 5]

#: Board type codes decoded from a new-style revision code ((revision >> 4) & 0xff).
KNOWN_BOARD_TYPES = [
    0x00, 0x01, 0x02, 0x03, 0x04, 0x06, 0x08, 0x09, 0x0A, 0x0C, 0x0D, 0x0E, 0x10, 0x11,
    0x12, 0x13, 0x14, 0x15, 0x17, 0x18, 0x19, 0x1A,
]


def pi_models(include_invalid: bool = False) -> st.SearchStrategy:
    """Pi_Model values 0..5 (and ``-1`` plus out-of-range integers when ``include_invalid``)."""
    valid = st.sampled_from(PI_MODELS)
    if not include_invalid:
        return valid
    return st.one_of(valid, st.just(-1), st.integers(-5, 20))


def board_types() -> st.SearchStrategy:
    """Known board type codes, ``-1`` (old-style revision), and random bytes."""
    return st.one_of(st.sampled_from(KNOWN_BOARD_TYPES), st.just(-1), st.integers(0, 255))


# --------------------------------------------------------------------------
# Key=value configuration files (Property 23)
# --------------------------------------------------------------------------


class KvFile(NamedTuple):
    """``/etc/default/*`` style file.

    ``expected`` is the value a shell would see for ``key`` after sourcing the
    file (the last assignment wins; commented lines and look-alike keys are
    ignored), or ``None`` when the key is absent.
    """

    content: str
    key: str
    expected: Optional[str]


_VALUE = st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJ0123456789_.@-:,/", max_size=15)
_QUOTED = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_.@- ", max_size=15)
_OTHER_KEY = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ_", min_size=1, max_size=8)


@st.composite
def kv_files(draw, key: str = "LANG") -> KvFile:
    """A file of ``KEY=value`` lines with ``key`` quoted, unquoted, missing, or duplicated."""
    n_assign = draw(st.sampled_from([0, 1, 1, 1, 2, 3]))
    noise = draw(st.lists(st.sampled_from(["other", "comment", "blank", "prefix", "suffix"]), max_size=6))
    order = draw(st.permutations(noise + ["__assign__"] * n_assign))
    lines: list[str] = []
    expected: Optional[str] = None
    for kind in order:
        if kind == "__assign__":
            if draw(st.booleans()):
                v = draw(_QUOTED)
                lines.append(f'{key}="{v}"')
            else:
                v = draw(_VALUE)
                lines.append(f"{key}={v}")
            expected = v
        elif kind == "other":
            k = draw(_OTHER_KEY)
            lines.append(f"{k}={draw(_VALUE)}" if k != key else f"{k}_X={draw(_VALUE)}")
        elif kind == "comment":
            lines.append(f"#{key}={draw(_VALUE)}")
        elif kind == "blank":
            lines.append("")
        elif kind == "prefix":
            lines.append(f"{key}_OTHER={draw(_VALUE)}")
        else:
            lines.append(f"X{key}={draw(_VALUE)}")
    return KvFile("\n".join(lines) + ("\n" if lines else ""), key, expected)


# --------------------------------------------------------------------------
# Deprecated variables (Property 13)
# --------------------------------------------------------------------------

_FALLBACK_DEPRECATED = [
    "raspi_config_enable_legacy_camera",
    "raspi_config_enable_remote_gpio",
    "raspi_config_enable_pixel_doubling",
    "raspi_config_gpu_memory",
    "raspi_config_wait_on_network",
    "raspi_config_enable_glamor",
]


def deprecated_names() -> list[str]:
    entries = load_role_vars().get("raspi_config__deprecated_variables") or []
    names = [str(e["name"]) for e in entries if isinstance(e, dict) and "name" in e]
    return names or list(_FALLBACK_DEPRECATED)


def deprecated_subsets() -> st.SearchStrategy:
    """Dict of a subset of the Deprecated_Variable names to arbitrary ``yaml_values()``."""
    names = deprecated_names()
    return st.dictionaries(st.sampled_from(names), yaml_values(), max_size=len(names))


# --------------------------------------------------------------------------
# Helpers for the structural tests
# --------------------------------------------------------------------------


def sampled_items(items: Sequence[Any]) -> st.SearchStrategy:
    """``st.sampled_from`` that degrades to ``st.nothing()`` for an empty sequence."""
    return st.sampled_from(list(items)) if items else st.nothing()
