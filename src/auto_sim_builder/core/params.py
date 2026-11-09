from enum import StrEnum
from dataclasses import dataclass


class ParamType(StrEnum):
    """Parameter types, values must match the CHECK on object_parameters.type."""

    INT    = "int"
    FLOAT  = "float"
    STR    = "str"
    BOOL   = "bool"
    CHOICE = "choice"


@dataclass(frozen=True, kw_only=True, slots=True)
class ParameterSpec:
    """A parameters data, post cleaning. Ready for use in core."""
    name:          str
    type:          ParamType
    default_value: str
    min_value:     float | None = None
    max_value:     float | None = None
    description:   str = ""
    choices:       tuple[str, ...] = ()
