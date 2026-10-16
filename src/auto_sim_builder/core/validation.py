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


def validate_parameter_range(parameter_type: ParamType, lower_bound: float | None, upper_bound: float | None) -> None:
    """Check range is valid for the given parameter dtype

    BOOL, CHOICE
    - cannot have bounds

    STR
    - must be not set or non-negative integers
    - lower_bound must be smaller or equal to upper_bound

    INT
    - must be not set or integers
    - lower_bound must be smaller or equal to upper_bound

    FLOAT
    - must be not set or a finite value
    - lower_bound must be smaller or equal to upper_bound
    """
    match parameter_type:
        case ParamType.BOOL | ParamType.CHOICE:
            if (lower_bound is not None) or (upper_bound is not None):
                raise ValueError(f"'{parameter_type}' cannot have bounds")

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
            raise ValueError(f"'{parameter_type}' is not a valid parameter type")

    if (lower_bound is not None) and (upper_bound is not None) and (lower_bound > upper_bound):
        raise ValidationError(f"'{lower_bound}' is greater than '{upper_bound}'", "upper")


def clean_parameter_value(
    parameter_type: ParamType,
    value:          str,
    lower_bound:    float | None,
    upper_bound:    float | None,
    choices:        set[str] | None
    ) -> str:
    """Check parameter value is valid and return a cleaned string

    Raises ValidationError (field "value") if the value is invalid.
    Returns the string to store: BOOL → "True"/"False", INT/FLOAT → str(int/float(value)),
    CHOICE → the stripped value, STR → unchanged.

    BOOL
    - '1', '0', 'true' and 'false' are accepted
    - leading and trailing spaces are stripped
    - case is ignored

    CHOICE
    - the choice must be in the choices set
    - leading and trailing spaces are stripped
    - case-sensitive

    STR
    - can only contain ascii and non-control characters
    - must have a length within bounds (inclusive)

    INT
    - must be ascii and a whole number
    - surrounding whitespace and '_' separators are accepted
    - must be within bounds (inclusive)

    FLOAT
    - must be ascii and parseable by float()
    - surrounding whitespace and '_' separators are accepted
    - must be finite
    - must be within bounds (inclusive)
    """
    match parameter_type:
        case ParamType.BOOL:
            bool_value = value.strip().casefold()

            if bool_value in ("true", "1"):
                return "True"
            elif bool_value in ("false", "0"):
                return "False"
            else:
                raise ValidationError(f"'{value}' could not be converted to a boolean. '1', '0', 'true' or 'false' are accepted.", "value")

        case ParamType.CHOICE:
            if not choices:
                raise ValueError("choice parameters require at least one choice")

            choice_value = value.strip()

            if choice_value not in choices:
                raise ValidationError(f"'{value}' is not one of: {', '.join(sorted(choices))}", "value")

            return choice_value

        case ParamType.STR:
            if (not value.isascii()) or (not value.isprintable()):
                raise ValidationError(f"'{value}' contains non-ascii or control characters", "value")

            elif (lower_bound is not None) and (len(value) < lower_bound):
                raise ValidationError(f"'{value}' is shorter than minimum length '{int(lower_bound)}'", "value")

            elif (upper_bound is not None) and (len(value) > upper_bound):
                raise ValidationError(f"'{value}' is longer than maximum length '{int(upper_bound)}'", "value")

            return value

        case ParamType.INT:
            if not value.isascii():
                raise ValidationError(f"'{value}' contains non-ascii characters", "value")

            try:
                int_value = int(value)
            except ValueError:
                raise ValidationError(f"'{value}' is not a whole number", "value") from None

            if (lower_bound is not None) and (int_value < lower_bound):
                raise ValidationError(f"'{value}' is smaller than the lower bound of '{int(lower_bound)}'", "value")

            elif (upper_bound is not None) and (int_value > upper_bound):
                raise ValidationError(f"'{value}' is greater than the upper bound of '{int(upper_bound)}'", "value")

            return str(int_value)

        case ParamType.FLOAT:
            if not value.isascii():
                raise ValidationError(f"'{value}' contains non-ascii characters", "value")
            
            try:
                float_value = float(value)
            except ValueError:
                raise ValidationError(f"'{value}' is not a number", "value") from None

            if not isfinite(float_value):
                raise ValidationError(f"'{value}' is not a finite value", "value")

            elif (lower_bound is not None) and (float_value < lower_bound):
                raise ValidationError(f"'{value}' is smaller than the lower bound of '{lower_bound}'", "value")

            elif (upper_bound is not None) and (float_value > upper_bound):
                raise ValidationError(f"'{value}' is greater than the upper bound of '{upper_bound}'", "value")

            return str(float_value)

        case _:
            raise ValueError(f"'{parameter_type}' is not a valid parameter type")


def clean_choice(choice: str, current_choices: set[str]) -> str:
    """Checks a choice is valid and returns a cleaned string

    Raises ValidationError (field "choice") if the choice is invalid.
    returns the choice with leading and trailing whitespace stripped.

    A new choice must be:
    - a string with only ascii and no control characters
    - once stripped, less than 100 characters
    - must not match a current choice, case insensitive
    
    NOTE: empty strings are allowed
    """

    if not isinstance(choice, str):
        raise ValueError(f"'{choice}' is not a string")

    stripped_choice = choice.strip()

    if len(stripped_choice) > 99:
        raise ValidationError(f"'{choice}' is longer than 99 characters", "choice")

    elif (not stripped_choice.isascii()) or (not stripped_choice.isprintable()):
        raise ValidationError(f"'{choice}' contains non-ascii or control characters", "choice")

    elif stripped_choice in current_choices:
        raise ValidationError(f"'{choice}' is already a selectable choice", "choice")

    clash = next((c for c in current_choices if c.casefold() == stripped_choice.casefold()), None)
    if clash is not None:
        raise ValidationError(f"'{choice}' only differs in case from '{clash}'", "choice")

    return stripped_choice