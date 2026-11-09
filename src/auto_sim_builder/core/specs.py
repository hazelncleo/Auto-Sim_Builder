# Plain data types shared by core/ and db/. Must never import from the project,
# so db/ can use them without an import cycle.

from enum import StrEnum
from dataclasses import dataclass


class ParamType(StrEnum):
    """Parameter types, values must match the CHECK on object_parameters.type."""

    INT    = "int"
    FLOAT  = "float"
    STR    = "str"
    BOOL   = "bool"
    CHOICE = "choice"


@dataclass(frozen = True, kw_only = True, slots = True)
class ParameterSpec:
    """A parameters data, post cleaning. Ready for use in core."""
    name:          str
    type:          ParamType
    default_value: str
    min_value:     float | None = None
    max_value:     float | None = None
    description:   str = ""
    choices:       tuple[str, ...] = ()


class ObjectKind(StrEnum):
    """Object kinds, values must match the CHECK on objects.kind."""

    ANALYSIS = "analysis"
    GEOMETRY = "geometry"


@dataclass(frozen = True, kw_only = True, slots = True)
class ObjectSpec:
    """An object's own row data, post cleaning. Ready for use in core."""
    name:        str
    kind:        ObjectKind
    description: str = ""
