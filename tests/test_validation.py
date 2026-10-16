# TODO: core/validation.py tests (pure function, no database needed).
#
# int / float
#   - values at min and max accepted (bounds are inclusive); just outside rejected
#   - open ranges (no min or no max) accepted
#   - text that isn't a number rejected; '1.5' rejected for int
#
# str
#   - lengths at min / max accepted; one shorter / longer rejected
#
# choice
#   - a listed choice accepted; anything else rejected (case-sensitive)
#
# bool
#   - true / false / 1 / 0 accepted, ignoring case (True, TRUE, ...)
#   - normalised to "True" / "False" for storage
#   - anything else rejected (e.g. "yes", "2", "")
#
# Errors
#   - rejection messages say why (e.g. "above max 10")

import pytest

from auto_sim_builder.core.params import ParamType
from auto_sim_builder.core.validation import (
    ValidationError,
    validate_description,
    validate_name,
    validate_range,
)


def test_valid_name_accepted():
    validate_name("plate_v1.2-a", {"other"})


def test_99_characters_accepted():
    validate_name("x" * 99, set())


@pytest.mark.parametrize(
    "name, taken, message",
    [
        (None, set(), "not a string"),
        ("Plate", {"plate"}, "already used"),
        ("x" * 100, set(), "longer than 99"),
        ("", set(), "empty"),
        ("has space", set(), "restricted characters"),
        (".hidden", set(), "first character"),
    ],
    ids=["not-str", "duplicate", "too-long", "empty", "bad-char", "bad-first-char"],
)
def test_invalid_name_rejected(name, taken, message):
    with pytest.raises(ValueError, match=message):
        validate_name(name, taken)


def test_valid_description_accepted():
    validate_description("Coarse mesh, 5 kN load (café)")


def test_249_character_description_accepted():
    validate_description("x" * 249)


@pytest.mark.parametrize(
    "description, message",
    [
        (None, "not a string"),
        ("x" * 250, "longer than 249"),
        ("two\nlines", "non-printable"),
    ],
    ids=["not-str", "too-long", "non-printable"],
)
def test_invalid_description_rejected(description, message):
    with pytest.raises(ValueError, match=message):
        validate_description(description)


@pytest.mark.parametrize(
    "ptype, lower, upper",
    [
        (ParamType.INT, None, None),
        (ParamType.INT, -5.0, 10.0),
        (ParamType.INT, 3, 3),
        (ParamType.FLOAT, -0.5, 2.25),
        (ParamType.FLOAT, None, 1e-9),
        (ParamType.STR, 0.0, 0.0),
        (ParamType.STR, 1.0, None),
        (ParamType.BOOL, None, None),
        (ParamType.CHOICE, None, None),
        ("int", 1.0, 2.0),
    ],
    ids=["int-open", "int-bounded", "int-equal", "float-bounded", "float-upper-only",
         "str-zero", "str-lower-only", "bool", "choice", "plain-str-type"],
)
def test_valid_range_accepted(ptype, lower, upper):
    validate_range(ptype, lower, upper)


@pytest.mark.parametrize(
    "ptype, lower, upper, field, message",
    [
        (ParamType.INT, 1.5, None, "lower", "not an integer"),
        (ParamType.INT, None, 2.5, "upper", "not an integer"),
        (ParamType.INT, float("nan"), None, "lower", "not an integer"),
        (ParamType.INT, None, float("inf"), "upper", "not an integer"),
        (ParamType.STR, 0.5, None, "lower", "not an integer"),
        (ParamType.STR, -1.0, None, "lower", "negative"),
        (ParamType.STR, None, 2.5, "upper", "not an integer"),
        (ParamType.STR, None, -1.0, "upper", "negative"),
        (ParamType.FLOAT, float("nan"), None, "lower", "not a finite value"),
        (ParamType.FLOAT, None, float("nan"), "upper", "not a finite value"),
        (ParamType.FLOAT, float("-inf"), None, "lower", "not a finite value"),
        (ParamType.FLOAT, None, float("inf"), "upper", "not a finite value"),
        (ParamType.INT, 5.0, 1.0, "upper", "greater than"),
        (ParamType.FLOAT, 0.2, 0.1, "upper", "greater than"),
        (ParamType.STR, 10.0, 3.0, "upper", "greater than"),
    ],
    ids=["int-lower-frac", "int-upper-frac", "int-nan", "int-inf",
         "str-lower-frac", "str-lower-neg", "str-upper-frac", "str-upper-neg",
         "float-lower-nan", "float-upper-nan", "float-lower-inf", "float-upper-inf",
         "int-min-over-max", "float-min-over-max", "str-min-over-max"],
)
def test_invalid_range_rejected(ptype, lower, upper, field, message):
    with pytest.raises(ValidationError, match=message) as error:
        validate_range(ptype, lower, upper)
    assert error.value.field == field


@pytest.mark.parametrize(
    "ptype, lower, upper",
    [
        (ParamType.BOOL, 0.0, None),
        (ParamType.BOOL, None, 1.0),
        (ParamType.CHOICE, 0.0, 1.0),
    ],
    ids=["bool-lower", "bool-upper", "choice-both"],
)
def test_bounds_rejected_for_bool_and_choice(ptype, lower, upper):
    with pytest.raises(ValueError, match="cannot have bounds"):
        validate_range(ptype, lower, upper)


def test_unknown_type_rejected():
    with pytest.raises(ValueError, match="not a valid parameter type"):
        validate_range("flaot", 1.0, 2.0)


def test_validation_error_is_value_error():
    with pytest.raises(ValueError):
        validate_range(ParamType.INT, 1.5, None)
