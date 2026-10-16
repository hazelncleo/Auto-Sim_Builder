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

from auto_sim_builder.core.validation import validate_description, validate_name


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
