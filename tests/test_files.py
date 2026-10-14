# TODO: core/files.py tests (use tmp_path for source and object folders).
#
# Import scan
#   - lists files recursively with sizes
#   - ignore patterns (files and folders like __pycache__/) start unticked
#
# Limits
#   - a file over max_file_size_mb is refused
#   - a selection over max_object_size_mb is refused; 0 means no limit
#   - limits come from the config, so raising them allows the import
#
# Snapshots
#   - import records size, mtime and sha256 for each copied file
#   - copied files match the source
#
# File check
#   - unchanged files pass without re-hashing (size/mtime match)
#   - a modified file is reported as modified
#   - a touched but unchanged file (new mtime, same content) isn't reported
#   - a deleted file is reported as missing
#   - unlisted files in the object folder are ignored
#   - Verify OK overwrites the snapshot, after which the file passes
