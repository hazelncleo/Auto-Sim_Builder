-- Auto-Sim Builder database schema (see Database_plan.md).
-- Applied by db.connect() to a new database (user_version = 0).
-- PRAGMA foreign_keys = ON must be set per connection by connect(), not here.
-- The database only checks the shape of the data; all other rules live in core/.

BEGIN;

-- The software this project uses, chosen from the catalogue in code.
-- Keys can't be renamed; they can be added at any time and deleted while unused.
CREATE TABLE software (
    id      INTEGER PRIMARY KEY,
    key     TEXT NOT NULL UNIQUE,   -- catalogue key, e.g. 'abaqus'
    command TEXT                    -- e.g. 'abq2024'; NULL = use the config, then the catalogue default
) STRICT;

-- name doubles as the folder name objects/<name>/, so it must be filesystem-safe
CREATE TABLE objects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
                CHECK (name GLOB '[A-Za-z0-9]*' AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
    description TEXT,
    kind        TEXT NOT NULL CHECK (kind IN ('analysis', 'geometry'))
) STRICT;

CREATE TABLE object_files (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    rel_path    TEXT NOT NULL,            -- relative to objects/<name>/
    size_bytes  INTEGER NOT NULL,         -- edit detection: snapshot taken at import,
    mtime_ns    INTEGER NOT NULL,         --   refreshed by "Verify OK"
    sha256      TEXT    NOT NULL,
    imported_at TEXT    NOT NULL,         -- ISO 8601 timestamp
    UNIQUE (object_id, rel_path)
) STRICT;

-- Which software an object uses, and the build file for each (optional per software).
CREATE TABLE object_software (
    object_id     INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    software_id   INTEGER NOT NULL REFERENCES software(id),
    build_file_id INTEGER REFERENCES object_files(id),   -- NULL = no build step for this software
    PRIMARY KEY (object_id, software_id),
    UNIQUE (build_file_id)                               -- a file builds at most one software
) STRICT;

CREATE TABLE object_parameters (
    id            INTEGER PRIMARY KEY,
    object_id     INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    type          TEXT NOT NULL CHECK (type IN ('float', 'int', 'str', 'bool', 'choice')),
    default_value TEXT NOT NULL,          -- every parameter needs a default
    min_value     REAL,   -- int/float: lower bound; str: min length; NULL = unbounded
    max_value     REAL,   -- int/float: upper bound; str: max length; NULL = unbounded
    description   TEXT,
    UNIQUE (object_id, name),
    CHECK (min_value IS NULL OR max_value IS NULL OR min_value <= max_value),
    CHECK (type NOT IN ('bool', 'choice') OR (min_value IS NULL AND max_value IS NULL)),
    CHECK (type <> 'str' OR (
        (min_value IS NULL OR (min_value >= 0 AND min_value = CAST(min_value AS INTEGER))) AND
        (max_value IS NULL OR (max_value >= 0 AND max_value = CAST(max_value AS INTEGER)))
    ))
) STRICT;

CREATE TABLE parameter_choices (
    parameter_id INTEGER NOT NULL REFERENCES object_parameters(id) ON DELETE CASCADE,
    value        TEXT NOT NULL,
    PRIMARY KEY (parameter_id, value)
) STRICT;

-- Objects used by a model can't be deleted while the model exists (default FK behaviour).
-- Insert a model's geometries in the same transaction that creates the model.
-- name doubles as the folder name models/<name>/
CREATE TABLE models (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
                CHECK (name GLOB '[A-Za-z0-9]*' AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
    description  TEXT,
    analysis_id  INTEGER NOT NULL REFERENCES objects(id),
    build_status TEXT CHECK (build_status IN ('success', 'failed')),  -- NULL = not built yet
    built_at     TEXT,                    -- ISO 8601 timestamp of the last build
    CHECK ((build_status IS NULL) = (built_at IS NULL))
) STRICT;

CREATE TABLE model_geometries (
    model_id    INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    geometry_id INTEGER NOT NULL REFERENCES objects(id),
    PRIMARY KEY (model_id, geometry_id)
) STRICT;

CREATE TABLE model_parameter_values (
    model_id     INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    parameter_id INTEGER NOT NULL REFERENCES object_parameters(id) ON DELETE CASCADE,
    value        TEXT NOT NULL,
    PRIMARY KEY (model_id, parameter_id)
) STRICT;

PRAGMA user_version = 1;

COMMIT;
