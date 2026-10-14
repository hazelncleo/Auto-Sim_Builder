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
