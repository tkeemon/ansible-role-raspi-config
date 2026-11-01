"""Parse the role's task files into flat, queryable records.

``parse_role(root)`` flattens every file under ``tasks/`` into ``ParsedTask``
objects. Each record carries:

* the effective tags: tags of the ``import_tasks`` that pulls the file in
  (read from ``tasks/main.yml``, followed through nested imports), tags of every
  enclosing block, and the task's own tags; ``always`` is kept as a tag;
* ``notify``, ``no_log``, ``environment`` (effective: the task's own value, else
  the nearest enclosing block's), ``when`` (own and effective), ``register``,
  ``changed_when``, ``failed_when``, ``check_mode``, ``ignore_errors``;
* the module name and its arguments;
* the enclosing block (``ParsedBlock``), the section of the block the task sits
  in (``block``, ``rescue`` or ``always``), and the file and position.

Tags are stored as sets of strings. Nothing here renders templates; use
``harness`` for that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from harness import ROLE_ROOT, load_yaml

# Keywords that are not module names. Anything else in a task mapping is the
# action (module) key.
TASK_KEYWORDS = frozenset(
    {
        "name", "when", "tags", "notify", "listen", "no_log", "environment", "register",
        "changed_when", "failed_when", "check_mode", "ignore_errors", "ignore_unreachable",
        "vars", "loop", "loop_control", "until", "retries", "delay", "become", "become_user",
        "become_method", "become_flags", "become_exe", "delegate_to", "delegate_facts", "run_once",
        "args", "diff", "any_errors_fatal", "connection", "collections", "module_defaults",
        "throttle", "timeout", "debugger", "async", "poll", "remote_user", "port",
        "no_log", "action", "local_action", "block", "rescue", "always", "notified",
        "max_fail_percentage", "serial", "strategy", "order", "tasks", "pre_tasks", "post_tasks",
    }
)

IMPORT_MODULES = frozenset({"import_tasks", "import_role"})
INCLUDE_MODULES = frozenset({"include_tasks", "include_role"})


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _tag_set(value: Any) -> frozenset[str]:
    """Tags may be a string, a comma separated string or a list."""
    tags: set[str] = set()
    for item in _as_list(value):
        for part in str(item).split(","):
            part = part.strip()
            if part:
                tags.add(part)
    return frozenset(tags)


def _short(module: Optional[str]) -> Optional[str]:
    return module.rsplit(".", 1)[-1] if module else module


def _line(obj: Any) -> Optional[int]:
    pos = getattr(obj, "ansible_pos", None)
    if pos and len(pos) >= 2:
        return pos[1]
    return None


@dataclass
class ParsedBlock:
    """A ``block`` entry (with its ``rescue`` and ``always`` sections)."""

    file: str
    name: Optional[str]
    raw: dict
    tags: frozenset[str]
    effective_tags: frozenset[str]
    when: list
    effective_when: list
    environment: Any
    no_log: Any
    parent: Optional["ParsedBlock"] = None
    line: Optional[int] = None
    tasks: list["ParsedTask"] = field(default_factory=list, repr=False)

    @property
    def chain(self) -> list["ParsedBlock"]:
        """Enclosing blocks from the outermost to ``self``."""
        out: list[ParsedBlock] = []
        node: Optional[ParsedBlock] = self
        while node is not None:
            out.append(node)
            node = node.parent
        return out[::-1]


@dataclass
class ParsedTask:
    """One task of a task file, with inherited attributes resolved."""

    file: str  # base name, e.g. "system.yml"
    path: Path
    index: int  # position in the flattened file, document order
    name: Optional[str]
    raw: dict
    module: Optional[str]  # as written, e.g. "ansible.builtin.command"
    args: Any  # module arguments (dict, string for free-form, or None)
    tags: frozenset[str]  # the task's own tags
    effective_tags: frozenset[str]  # import + block + own tags
    notify: tuple[str, ...]
    no_log: Any  # own value, else the nearest enclosing block's, else None
    environment: Any  # own value, else the nearest enclosing block's, else None
    when: list  # own conditions
    effective_when: list  # import + enclosing blocks + own conditions
    register: Optional[str]
    changed_when: Any
    failed_when: Any
    check_mode: Any
    ignore_errors: Any
    block: Optional[ParsedBlock]
    section: Optional[str]  # "block", "rescue", "always" or None (top level)
    imported_via: Optional[str] = None  # file that imports this one, if any
    line: Optional[int] = None

    @property
    def short_module(self) -> Optional[str]:
        return _short(self.module)

    @property
    def is_import(self) -> bool:
        return self.short_module in IMPORT_MODULES

    @property
    def is_include(self) -> bool:
        return self.short_module in INCLUDE_MODULES

    @property
    def argv(self) -> Any:
        """The ``argv`` module argument, or ``None``."""
        if isinstance(self.args, dict):
            return self.args.get("argv")
        return None

    @property
    def tag_prefix_file(self) -> str:
        """File base name without extension (the ``SUBMENU`` of a tag)."""
        return self.path.stem

    @property
    def text(self) -> str:
        """The task's YAML mapping as text, for 'does the task mention X' checks."""
        import yaml  # local: only needed here

        def plain(v: Any) -> Any:
            if isinstance(v, dict):
                return {str(k): plain(x) for k, x in v.items()}
            if isinstance(v, (list, tuple)):
                return [plain(x) for x in v]
            if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
                return v
            return str(v)

        return yaml.safe_dump(plain(self.raw), sort_keys=False, allow_unicode=True)

    @property
    def block_chain(self) -> list[ParsedBlock]:
        return self.block.chain if self.block else []

    def label(self) -> str:
        return f"{self.file}:{self.line or '?'} {self.name or self.module}"


@dataclass
class ParsedRole:
    root: Path
    tasks: list[ParsedTask]
    blocks: list[ParsedBlock]
    #: file base name -> tags added by the import_tasks that pulls it in
    import_tags: dict[str, frozenset[str]]

    def by_file(self, name: str) -> list[ParsedTask]:
        return [t for t in self.tasks if t.file == name]

    def files(self) -> list[str]:
        seen: list[str] = []
        for t in self.tasks:
            if t.file not in seen:
                seen.append(t.file)
        return seen

    def with_tag(self, tag: str) -> list[ParsedTask]:
        return [t for t in self.tasks if tag in t.effective_tags]

    def select(self, tag: str) -> list[ParsedTask]:
        """Tasks Ansible selects for ``--tags tag``: the tag's tasks plus ``always``."""
        return [t for t in self.tasks if tag in t.effective_tags or "always" in t.effective_tags]

    def all_tags(self) -> set[str]:
        out: set[str] = set()
        for t in self.tasks:
            out |= t.effective_tags
        return out

    def __iter__(self) -> Iterator[ParsedTask]:
        return iter(self.tasks)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def _find_module(item: dict) -> tuple[Optional[str], Any]:
    for key in ("action", "local_action"):
        if key in item:
            val = item[key]
            if isinstance(val, dict):
                return str(val.get("module")), {k: v for k, v in val.items() if k != "module"}
            parts = str(val).split(None, 1)
            return (parts[0] if parts else None), (parts[1] if len(parts) > 1 else None)
    for key, value in item.items():
        key = str(key)
        if key in TASK_KEYWORDS or key.startswith("with_"):
            continue
        args = value
        if isinstance(item.get("args"), dict):
            args = dict(value) if isinstance(value, dict) else {"_raw_params": value}
            args.update(item["args"])
        return key, args
    return None, None


def _import_target(task: ParsedTask) -> Optional[str]:
    """File name an ``import_tasks`` task points at (``None`` when not static)."""
    if task.short_module != "import_tasks":
        return None
    args = task.args
    if isinstance(args, dict):
        args = args.get("file") or args.get("_raw_params")
    if not isinstance(args, str) or "{{" in args:
        return None
    return args


class _FileParser:
    def __init__(self, path: Path, inherited_tags: frozenset[str], inherited_when: list,
                 imported_via: Optional[str]):
        self.path = path
        self.file = path.name
        self.inherited_tags = inherited_tags
        self.inherited_when = inherited_when
        self.imported_via = imported_via
        self.tasks: list[ParsedTask] = []
        self.blocks: list[ParsedBlock] = []

    def parse(self) -> None:
        data = load_yaml(self.path, default=[])
        if isinstance(data, dict):  # tolerate a mapping with a ``tasks`` key
            data = data.get("tasks", [])
        self._walk(_as_list(data), parent=None, section=None)

    def _walk(self, items: list, parent: Optional[ParsedBlock], section: Optional[str]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            if "block" in item:
                self._block(item, parent, section)
            else:
                self._task(item, parent, section)

    def _base_tags(self, parent: Optional[ParsedBlock]) -> frozenset[str]:
        return parent.effective_tags if parent else self.inherited_tags

    def _base_when(self, parent: Optional[ParsedBlock]) -> list:
        return list(parent.effective_when) if parent else list(self.inherited_when)

    def _block(self, item: dict, parent: Optional[ParsedBlock], section: Optional[str]) -> None:
        own_tags = _tag_set(item.get("tags"))
        when = _as_list(item.get("when"))
        block = ParsedBlock(
            file=self.file,
            name=item.get("name"),
            raw=item,
            tags=own_tags,
            effective_tags=self._base_tags(parent) | own_tags,
            when=when,
            effective_when=self._base_when(parent) + when,
            environment=item.get("environment", parent.environment if parent else None),
            no_log=item.get("no_log", parent.no_log if parent else None),
            parent=parent,
            line=_line(item),
        )
        self.blocks.append(block)
        before = len(self.tasks)
        for sec in ("block", "rescue", "always"):
            self._walk(_as_list(item.get(sec)), parent=block, section=sec)
        block.tasks = self.tasks[before:]

    def _task(self, item: dict, parent: Optional[ParsedBlock], section: Optional[str]) -> None:
        module, args = _find_module(item)
        own_tags = _tag_set(item.get("tags"))
        when = _as_list(item.get("when"))
        notify = tuple(str(n) for n in _as_list(item.get("notify")))
        self.tasks.append(
            ParsedTask(
                file=self.file,
                path=self.path,
                index=len(self.tasks),
                name=item.get("name"),
                raw=item,
                module=module,
                args=args,
                tags=own_tags,
                effective_tags=self._base_tags(parent) | own_tags,
                notify=notify,
                no_log=item["no_log"] if "no_log" in item else (parent.no_log if parent else None),
                environment=item["environment"] if "environment" in item
                else (parent.environment if parent else None),
                when=when,
                effective_when=self._base_when(parent) + when,
                register=item.get("register"),
                changed_when=item.get("changed_when"),
                failed_when=item.get("failed_when"),
                check_mode=item.get("check_mode"),
                ignore_errors=item.get("ignore_errors"),
                block=parent,
                section=section,
                imported_via=self.imported_via,
                line=_line(item),
            )
        )


def parse_task_file(
    path: Path,
    inherited_tags: frozenset[str] = frozenset(),
    inherited_when: Optional[list] = None,
    imported_via: Optional[str] = None,
) -> tuple[list[ParsedTask], list[ParsedBlock]]:
    """Parse one task file. ``inherited_tags`` are the tags of the importing task."""
    parser = _FileParser(Path(path), frozenset(inherited_tags), list(inherited_when or []), imported_via)
    parser.parse()
    return parser.tasks, parser.blocks


def parse_role(root: Path = ROLE_ROOT, tasks_dir: str = "tasks") -> ParsedRole:
    """Flatten every ``*.yml`` / ``*.yaml`` file under ``<root>/tasks`` (tolerates a missing directory).

    ``main.yml`` is parsed first; for each static ``import_tasks`` its effective
    tags and ``when`` are passed on to the imported file, recursively. Files that
    no import reaches are still parsed, with no inherited tags.
    """
    root = Path(root)
    base = root / tasks_dir
    files: dict[str, Path] = {}
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in (".yml", ".yaml"):
                files[str(p.relative_to(base))] = p

    tasks: list[ParsedTask] = []
    blocks: list[ParsedBlock] = []
    import_tags: dict[str, frozenset[str]] = {}
    done: set[str] = set()

    def process(rel: str, tags: frozenset[str], when: list, via: Optional[str]) -> None:
        if rel in done or rel not in files:
            return
        done.add(rel)
        file_tasks, file_blocks = parse_task_file(files[rel], tags, when, via)
        tasks.extend(file_tasks)
        blocks.extend(file_blocks)
        for t in file_tasks:
            target = _import_target(t)
            if target is None:
                continue
            target_rel = str((Path(rel).parent / target)) if Path(rel).parent != Path(".") else target
            if target_rel not in files and target in files:
                target_rel = target
            import_tags[Path(target_rel).name] = t.effective_tags
            process(target_rel, t.effective_tags, t.effective_when, rel)

    process("main.yml", frozenset(), [], None)
    for rel in files:
        process(rel, frozenset(), [], None)
    return ParsedRole(root=root, tasks=tasks, blocks=blocks, import_tags=import_tags)
