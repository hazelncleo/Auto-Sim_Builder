# TODO: Schema tests. Every rejection raises sqlite3.IntegrityError.
# Test what's accepted as well as what's rejected.
#
# Names (objects and models)
#   - '', '.', '..', '../x', 'has space' rejected; 'plate_v1.2-a' accepted
#
# Allowed values
#   - bad objects.kind, object_parameters.type, models.build_status rejected
#
# Parameter ranges
#   - min_value > max_value rejected; open ranges (NULL min or max) accepted
#   - bool / choice with a min or max set rejected
#   - str with a negative or fractional length rejected; whole-number lengths accepted
#   - missing default_value rejected
#
# Build status
#   - build_status without built_at rejected, and the other way round
#   - both or neither accepted
#
# Uniqueness
#   - duplicate object name / model name / software key
#   - same rel_path twice in one object (allowed in different objects)
#   - same parameter name twice in one object (allowed in different objects)
#   - one file as the build file for two software; NULL build files allowed more than once
#
# Foreign keys
#   - deleting an object used as a model's analysis fails
#   - deleting an object used as a model's geometry fails
#   - deleting software an object uses fails
#   - rows pointing at ids that don't exist rejected
#
# Cascades
#   - deleting an unused object removes its files, software links, parameters and choices
#   - deleting a model removes its geometry links and values, but not the objects
#   - deleting a parameter removes its choices
#
# STRICT
#   - 'abc' in an INTEGER column rejected; '12' stored as the integer 12
