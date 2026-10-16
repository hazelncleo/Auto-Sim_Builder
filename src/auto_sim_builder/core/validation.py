import string

ALLOWED_CHARACTERS = set(string.ascii_letters + string.digits + '_-.')
ALLOWED_STARTING_CHARACTERS = set(string.ascii_letters + string.digits)


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
