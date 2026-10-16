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
    validate_parameter_range,
    clean_parameter_value,
    clean_choice,
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
    validate_parameter_range(ptype, lower, upper)


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
        validate_parameter_range(ptype, lower, upper)
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
        validate_parameter_range(ptype, lower, upper)


def test_unknown_type_rejected():
    with pytest.raises(ValueError, match="not a valid parameter type"):
        validate_parameter_range("flaot", 1.0, 2.0)


def test_validation_error_is_value_error():
    with pytest.raises(ValueError):
        validate_parameter_range(ParamType.INT, 1.5, None)


@pytest.mark.parametrize(
    "value, lower, upper, stored",
    [
        ("1.5", None, None, "1.5"),
        ("-2", None, None, "-2.0"),
        ("1e3", None, None, "1000.0"),
        ("0.1", None, None, "0.1"),
        ("0", 0.0, 10.0, "0.0"),
        ("10", 0.0, 10.0, "10.0"),
        ("5.5", 0.0, None, "5.5"),
        ("-1e9", None, 0.0, "-1000000000.0"),
        (" 10 ", None, None, "10.0"),
        ("1_000", None, None, "1000.0"),
    ],
    ids=["plain", "whole-number", "exponent", "shortest-repr", "at-lower", "at-upper",
         "lower-only", "upper-only", "whitespace", "underscore"],
)
def test_valid_float_value_accepted(value, lower, upper, stored):
    assert clean_parameter_value(ParamType.FLOAT, value, lower, upper, None) == stored


@pytest.mark.parametrize(
    "value, lower, upper, message",
    [
        ("bruh", None, None, "not a number"),
        ("", None, None, "not a number"),
        ("1.5.2", None, None, "not a number"),
        ("nan", None, None, "not a finite value"),
        ("inf", None, None, "not a finite value"),
        ("-Infinity", None, None, "not a finite value"),
        ("-0.001", 0.0, 10.0, "smaller than the lower bound"),
        ("10.001", 0.0, 10.0, "greater than the upper bound"),
        ("١٢", None, None, "non-ascii"),
        ("５", None, None, "non-ascii"),
    ],
    ids=["text", "empty", "two-points", "nan", "inf", "neg-infinity", "below-lower",
         "above-upper", "arabic-digits", "full-width-digit"],
)
def test_invalid_float_value_rejected(value, lower, upper, message):
    with pytest.raises(ValidationError, match=message) as error:
        clean_parameter_value(ParamType.FLOAT, value, lower, upper, None)
    assert error.value.field == "value"


def test_float_value_message_shows_typed_text():
    with pytest.raises(ValidationError, match="'1e3' is greater"):
        clean_parameter_value(ParamType.FLOAT, "1e3", None, 10.0, None)


def test_unknown_type_value_rejected():
    with pytest.raises(ValueError, match="not a valid parameter type"):
        clean_parameter_value("flaot", "1.0", None, None, None)


@pytest.mark.parametrize(
    "value, lower, upper, stored",
    [
        ("5", None, None, "5"),
        ("-3", None, None, "-3"),
        ("+7", None, None, "7"),
        ("007", None, None, "7"),
        (" 10 ", None, None, "10"),
        ("1_000", None, None, "1000"),
        ("0", 0.0, 10.0, "0"),
        ("10", 0.0, 10.0, "10"),
        ("99", 0.0, None, "99"),
        ("-99", None, 0.0, "-99"),
        ("1" * 30, None, None, "1" * 30),
    ],
    ids=["plain", "negative", "plus-sign", "leading-zeros", "whitespace", "underscore",
         "at-lower", "at-upper", "lower-only", "upper-only", "huge"],
)
def test_valid_int_value_accepted(value, lower, upper, stored):
    assert clean_parameter_value(ParamType.INT, value, lower, upper, None) == stored


@pytest.mark.parametrize(
    "value, lower, upper, message",
    [
        ("bruh", None, None, "not a whole number"),
        ("", None, None, "not a whole number"),
        ("1.5", None, None, "not a whole number"),
        ("5.0", None, None, "not a whole number"),
        ("1e3", None, None, "not a whole number"),
        ("nan", None, None, "not a whole number"),
        ("1" * 5000, None, None, "not a whole number"),
        ("١٢", None, None, "non-ascii"),
        ("５", None, None, "non-ascii"),
        ("-1", 0.0, 10.0, "smaller than the lower bound"),
        ("11", 0.0, 10.0, "greater than the upper bound"),
    ],
    ids=["text", "empty", "fraction", "point-zero", "exponent", "nan", "over-digit-limit",
         "arabic-digits", "full-width-digit", "below-lower", "above-upper"],
)
def test_invalid_int_value_rejected(value, lower, upper, message):
    with pytest.raises(ValidationError, match=message) as error:
        clean_parameter_value(ParamType.INT, value, lower, upper, None)
    assert error.value.field == "value"


def test_int_value_message_shows_whole_number_bound():
    with pytest.raises(ValidationError, match="upper bound of '10'"):
        clean_parameter_value(ParamType.INT, "11", None, 10.0, None)


@pytest.mark.parametrize(
    "value, lower, upper",
    [
        ("plate", None, None),
        ("", None, None),
        ("", 0.0, 5.0),
        (" padded ", None, None),
        ("Ti-6Al-4V (annealed) / 'grade 5'", None, None),
        (" ~", None, None),
        ("abc", 3.0, 3.0),
        ("abcde", 3.0, 5.0),
        ("x" * 1000, 1.0, None),
        ("x", None, 1.0),
    ],
    ids=["plain", "empty-open", "empty-zero-min", "spaces-kept", "punctuation",
         "ascii-edges", "exact-length", "at-max", "lower-only", "upper-only"],
)
def test_valid_str_value_accepted(value, lower, upper):
    assert clean_parameter_value(ParamType.STR, value, lower, upper, None) == value


@pytest.mark.parametrize(
    "value, lower, upper, message",
    [
        ("two\nlines", None, None, "non-ascii or control"),
        ("a\tb", None, None, "non-ascii or control"),
        ("nul\x00", None, None, "non-ascii or control"),
        ("del\x7f", None, None, "non-ascii or control"),
        ("café", None, None, "non-ascii or control"),
        ("20°C", None, None, "non-ascii or control"),
        ("5 – 10 mm", None, None, "non-ascii or control"),
        ("non\xa0breaking", None, None, "non-ascii or control"),
        ("zero​width", None, None, "non-ascii or control"),
        ("", 1.0, None, "shorter than minimum length"),
        ("ab", 3.0, 5.0, "shorter than minimum length"),
        ("abcdef", 3.0, 5.0, "longer than maximum length"),
    ],
    ids=["newline", "tab", "nul", "del", "accent", "degree", "en-dash", "nbsp", "zero-width",
         "empty-below-min", "below-min", "above-max"],
)
def test_invalid_str_value_rejected(value, lower, upper, message):
    with pytest.raises(ValidationError, match=message) as error:
        clean_parameter_value(ParamType.STR, value, lower, upper, None)
    assert error.value.field == "value"


def test_str_value_message_shows_whole_number_length():
    with pytest.raises(ValidationError, match="maximum length '5'"):
        clean_parameter_value(ParamType.STR, "abcdef", None, 5.0, None)


@pytest.mark.parametrize(
    "value, stored",
    [
        ("true", "True"),
        ("True", "True"),
        ("TRUE", "True"),
        ("tRuE", "True"),
        ("1", "True"),
        ("false", "False"),
        ("False", "False"),
        ("FALSE", "False"),
        ("0", "False"),
        (" true ", "True"),
        ("\t0\n", "False"),
    ],
    ids=["true", "True", "TRUE", "mixed-case", "one", "false", "False", "FALSE", "zero",
         "spaces", "tab-newline"],
)
def test_valid_bool_value_accepted(value, stored):
    assert clean_parameter_value(ParamType.BOOL, value, None, None, None) == stored


@pytest.mark.parametrize(
    "value",
    ["yes", "no", "on", "off", "t", "f", "2", "-1", "1.0", "00", "", " ", "true false", "ＴＲＵＥ"],
    ids=["yes", "no", "on", "off", "t", "f", "two", "minus-one", "one-point-zero", "double-zero",
         "empty", "blank", "both", "full-width"],
)
def test_invalid_bool_value_rejected(value):
    with pytest.raises(ValidationError, match="boolean") as error:
        clean_parameter_value(ParamType.BOOL, value, None, None, None)
    assert error.value.field == "value"


MATERIALS = {"Steel", "Aluminium", "steel-304", "Ti 6Al-4V"}


@pytest.mark.parametrize(
    "value, stored",
    [
        ("Steel", "Steel"),
        ("steel-304", "steel-304"),
        ("Ti 6Al-4V", "Ti 6Al-4V"),
        (" Aluminium ", "Aluminium"),
        ("\tSteel\n", "Steel"),
    ],
    ids=["exact", "lowercase-choice", "inner-space", "padded", "tab-newline"],
)
def test_valid_choice_value_accepted(value, stored):
    assert clean_parameter_value(ParamType.CHOICE, value, None, None, MATERIALS) == stored


@pytest.mark.parametrize(
    "value",
    ["steel", "STEEL", "Aluminum", "Ti  6Al-4V", "Brass", "", " ", "Steel, Aluminium"],
    ids=["wrong-case", "upper-case", "misspelt", "double-inner-space", "not-listed", "empty",
         "blank", "two-choices"],
)
def test_invalid_choice_value_rejected(value):
    with pytest.raises(ValidationError, match="is not one of") as error:
        clean_parameter_value(ParamType.CHOICE, value, None, None, MATERIALS)
    assert error.value.field == "value"


def test_choice_value_message_lists_choices():
    with pytest.raises(ValidationError) as error:
        clean_parameter_value(ParamType.CHOICE, "Brass", None, None, {"Steel", "Copper"})
    assert "Steel" in str(error.value) and "Copper" in str(error.value)


@pytest.mark.parametrize("choices", [None, set()], ids=["none", "empty"])
def test_choice_without_choices_rejected(choices):
    with pytest.raises(ValueError, match="at least one choice") as error:
        clean_parameter_value(ParamType.CHOICE, "Steel", None, None, choices)
    assert not isinstance(error.value, ValidationError)


@pytest.mark.parametrize(
    "choice, current, stored",
    [
        ("Steel", set(), "Steel"),
        ("Aluminium", {"Steel"}, "Aluminium"),
        (" Copper ", {"Steel"}, "Copper"),
        ("\tBrass\n", set(), "Brass"),
        ("Ti 6Al-4V", set(), "Ti 6Al-4V"),
        ("", {"Steel"}, ""),
        ("   ", set(), ""),
        ("x" * 99, set(), "x" * 99),
        (" " + "x" * 99 + " ", set(), "x" * 99),
    ],
    ids=["first", "second", "padded", "tab-newline", "inner-space", "empty", "blank",
         "99-characters", "99-after-strip"],
)
def test_valid_choice_accepted(choice, current, stored):
    assert clean_choice(choice, current) == stored


@pytest.mark.parametrize(
    "choice, current, message",
    [
        ("x" * 100, set(), "longer than 99"),
        ("café", set(), "non-ascii or control"),
        ("20°C", set(), "non-ascii or control"),
        ("a\x00b", set(), "non-ascii or control"),
        ("two\nlines", set(), "non-ascii or control"),
        ("Steel", {"Steel"}, "already a selectable choice"),
        (" Steel ", {"Steel"}, "already a selectable choice"),
        ("", {""}, "already a selectable choice"),
        ("steel", {"Steel"}, "only differs in case from 'Steel'"),
        (" STEEL ", {"Steel", "Copper"}, "only differs in case from 'Steel'"),
    ],
    ids=["too-long", "accent", "degree", "nul", "inner-newline", "duplicate",
         "padded-duplicate", "empty-duplicate", "case-clash", "padded-case-clash"],
)
def test_invalid_choice_rejected(choice, current, message):
    with pytest.raises(ValidationError, match=message) as error:
        clean_choice(choice, current)
    assert error.value.field == "choice"


def test_non_str_choice_rejected():
    with pytest.raises(ValueError, match="not a string") as error:
        clean_choice(None, set())
    assert not isinstance(error.value, ValidationError)
