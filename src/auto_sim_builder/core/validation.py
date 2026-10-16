from string import ascii_letters, digits
from auto_sim_builder.core.params import ParamType
from math import isfinite


class ValidationError(ValueError):
    """A validation failure tied to the input field that caused it."""

    def __init__(self, message: str, field: str):
        super().__init__(message)
        self.field = field


ALLOWED_CHARACTERS = set(ascii_letters + digits + '_-.')
ALLOWED_STARTING_CHARACTERS = set(ascii_letters + digits)


# TODO: Validate values against type / range / string length / choices


def validate_name(name: str, current_names: set[str]) -> None:
    """Check name matches the following criteria

    - Is a string
    - Does not match any current object/model names
    - Less than 100 characters
    - Only contains digits, letters, underscores, hyphens and period.
    - Must start with a digit or letter
    - Must not be empty

    NOTE: current_names should be casefolded
    """

    if not isinstance(name, str):
        raise ValueError(f"'{name}' is not a string")

    elif name.casefold() in current_names:
        raise ValueError(f"'{name}' is already used")

    elif len(name) >= 100:
        raise ValueError(f"'{name}' is longer than 99 characters")

    elif len(name) == 0:
        raise ValueError("name cannot be empty")

    elif not set(name) <= ALLOWED_CHARACTERS:
        raise ValueError(f"'{name}' contains restricted characters")

    elif name[0] not in ALLOWED_STARTING_CHARACTERS:
        raise ValueError(f"'{name}' contains restricted first character")


def validate_description(description: str) -> None:
    """Check description matches the following criteria

    - Is a string
    - Less than 250 characters
    - No control characters (tabs, newlines, etc.)
    """

    if not isinstance(description, str):
        raise ValueError("description is not a string")

    elif len(description) >= 250:
        raise ValueError("description is longer than 249 characters")

    elif not description.isprintable():
        raise ValueError("description contains non-printable characters")


def validate_range(ptype: ParamType, lower_bound: float | None, upper_bound: float | None) -> None:
    """Check range is valid for the given parameter dtype

    BOOL, CHOICE
    - cannot have bounds

    STR
    - must either be not set or non-negative integers
    - lower_bound must be smaller or equal to upper_bound

    INT
    - must be not set or integers
    - lower_bound must be smaller or equal to upper_bound

    FLOAT
    - must be either not set or a finite value
    - lower_bound must be smaller or equal to upper_bound
    """
    match ptype:
        case ParamType.BOOL | ParamType.CHOICE:
            if (lower_bound is not None) or (upper_bound is not None):
                raise ValueError(f"'{ptype}' cannot have bounds")

        case ParamType.STR:
            if lower_bound is not None:
                if not lower_bound.is_integer():
                    raise ValidationError(f"'{lower_bound}' is not an integer", "lower")
                elif lower_bound < 0:
                    raise ValidationError(f"'{lower_bound}' is negative", "lower")

            if upper_bound is not None:
                if not upper_bound.is_integer():
                    raise ValidationError(f"'{upper_bound}' is not an integer", "upper")
                elif upper_bound < 0:
                    raise ValidationError(f"'{upper_bound}' is negative", "upper")

        case ParamType.INT:
            if (lower_bound is not None) and (not lower_bound.is_integer()):
                raise ValidationError(f"'{lower_bound}' is not an integer", "lower")

            if (upper_bound is not None) and (not upper_bound.is_integer()):
                raise ValidationError(f"'{upper_bound}' is not an integer", "upper")

        case ParamType.FLOAT:
            if (lower_bound is not None) and not isfinite(lower_bound):
                raise ValidationError(f"'{lower_bound}' is not a finite value", "lower")

            elif (upper_bound is not None) and not isfinite(upper_bound):
                raise ValidationError(f"'{upper_bound}' is not a finite value", "upper")

        case _:
            raise ValueError(f"'{ptype}' is not a valid parameter type")

    if (lower_bound is not None) and (upper_bound is not None) and (lower_bound > upper_bound):
        raise ValidationError(f"'{lower_bound}' is greater than '{upper_bound}'", "upper")