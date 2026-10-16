from enum import StrEnum


class ParamType(StrEnum):
    """Parameter types; values must match the CHECK on object_parameters.type."""

    INT = "int"
    FLOAT = "float"
    STR = "str"
    BOOL = "bool"
    CHOICE = "choice"
