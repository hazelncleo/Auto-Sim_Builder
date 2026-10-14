# TODO: core/build.py tests. Run builds through a stub runner, not real
# Abaqus/Fluent/MPCCI; how builds launch is still an open question.
#
# Before building
#   - modified object files need Verify OK; the build doesn't start without it
#   - missing object files block the build
#
# Model folder
#   - only listed files are copied into models/<name>/
#   - rebuild wipes the folder but keeps logs/
#
# Running
#   - every build file of every object receives all of the model's values
#   - Abaqus .inp gets a *PARAMETER block with values formatted by type
#   - each build writes logs/build-YYYYMMDD-HHMMSS.log
#
# Status
#   - success / failure recorded in build_status with built_at
#   - a failed model is kept
#   - a second build while one is running is refused
