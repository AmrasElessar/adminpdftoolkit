"""Operation registry.

An operation is one tool: a ``Params`` model (validation *and* the UI form,
via JSON Schema) plus a ``run`` method executed inside a worker process.
Adding a tool means adding one class — the API, the catalogue and the UI
pick it up from the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as _Field

from ..core.files import safe_filename

ProgressFn = Callable[[float, str], None]


def Field(default: Any = ..., *, tr: str, en: str, help_tr: str = "", help_en: str = "", **kw: Any) -> Any:  # noqa: N802
    """``pydantic.Field`` carrying bilingual labels for the generated form."""
    extra: dict[str, Any] = {"title_tr": tr, "title_en": en}
    if help_tr:
        extra |= {"help_tr": help_tr, "help_en": help_en or help_tr}
    ui = kw.pop("ui", None)
    if ui:
        extra["ui"] = ui
    return _Field(default, title=en, json_schema_extra=extra, **kw)


def FileParam(  # noqa: N802
    *, tr: str, en: str, accept: list[str], required: bool = True, help_tr: str = "", help_en: str = ""
) -> Any:
    """A parameter naming another uploaded file (certificate, image, font…).

    The value is a file id. The API checks it exists and has an accepted
    kind, and the worker receives it as ``ctx.files[<field name>]``.
    """
    return Field(
        ... if required else "",
        tr=tr,
        en=en,
        help_tr=help_tr,
        help_en=help_en,
        max_length=64,
        ui={"widget": "file", "accept": accept},
    )


def file_params(params_cls: type[BaseModel]) -> dict[str, list[str]]:
    """``{field_name: accepted_kinds}`` for every FileParam of a model."""
    out: dict[str, list[str]] = {}
    for name, f in params_cls.model_fields.items():
        extra = f.json_schema_extra
        ui = extra.get("ui") if isinstance(extra, dict) else None
        if isinstance(ui, dict) and ui.get("widget") == "file":
            accept = ui.get("accept")
            out[name] = [str(a) for a in accept] if isinstance(accept, list) else []
    return out


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoParams(Params):
    pass


@dataclass
class InputFile:
    path: Path
    name: str
    password: str = ""

    @property
    def stem(self) -> str:
        return self.name.rsplit(".", 1)[0] if "." in self.name else self.name


@dataclass
class Output:
    path: Path
    name: str


@dataclass
class Context:
    inputs: list[InputFile]
    output_dir: Path
    progress: ProgressFn = lambda _f, _m: None
    outputs: list[Output] = field(default_factory=list)
    # Extra files referenced by FileParam fields, keyed by field name.
    files: dict[str, InputFile] = field(default_factory=dict)
    # JSON-serialisable result for "query" operations (inspect, validate…).
    data: dict[str, Any] | None = None

    def output(self, name: str) -> Path:
        """Reserve a unique, safe output path and record it as a result."""
        safe = safe_filename(name, default="output")
        stem, dot, ext = safe.rpartition(".")
        if not dot:
            stem, ext = safe, ""
        candidate, n = safe, 2
        taken = {o.name for o in self.outputs}
        while candidate in taken:
            candidate = f"{stem} ({n}).{ext}" if ext else f"{stem} ({n})"
            n += 1
        path = self.output_dir / f"{len(self.outputs):03d}_{candidate}"
        self.outputs.append(Output(path, candidate))
        return path


class Operation:
    name: ClassVar[str]
    category: ClassVar[str]  # pages | optimize | protect | stamp | convert | ...
    title_tr: ClassVar[str]
    title_en: ClassVar[str]
    description_tr: ClassVar[str] = ""
    description_en: ClassVar[str] = ""
    accepts: ClassVar[frozenset[str]] = frozenset({"pdf"})
    min_inputs: ClassVar[int] = 1
    max_inputs: ClassVar[int] = 1
    Params: ClassVar[type[Params]] = NoParams
    # True for operations whose main result is ``ctx.data`` rather than files.
    returns_data: ClassVar[bool] = False
    # Hidden from the tool grid; driven by a dedicated UI (e.g. the editor).
    hidden: ClassVar[bool] = False

    def run(self, ctx: Context, params: Any) -> None:
        raise NotImplementedError

    @classmethod
    def describe(cls) -> dict[str, Any]:
        return {
            "name": cls.name,
            "category": cls.category,
            "title": {"tr": cls.title_tr, "en": cls.title_en},
            "description": {"tr": cls.description_tr, "en": cls.description_en},
            "accepts": sorted(cls.accepts),
            "min_inputs": cls.min_inputs,
            "max_inputs": cls.max_inputs,
            "returns_data": cls.returns_data,
            "hidden": cls.hidden,
            "schema": cls.Params.model_json_schema(),
        }


REGISTRY: dict[str, type[Operation]] = {}


def register(cls: type[Operation]) -> type[Operation]:
    if cls.name in REGISTRY:
        raise RuntimeError(f"duplicate operation {cls.name!r}")
    REGISTRY[cls.name] = cls
    return cls


def load_all() -> dict[str, type[Operation]]:
    """Import every module in this package (and installed plugins) so their
    ``@register`` calls run. New tools need no edit here."""
    import importlib
    import pkgutil

    from .. import plugins

    for pkg in (__package__, plugins.__name__):
        module = importlib.import_module(pkg)
        for info in pkgutil.iter_modules(module.__path__):
            if not info.name.startswith("_") and info.name != "base":
                importlib.import_module(f"{pkg}.{info.name}")
    return REGISTRY
