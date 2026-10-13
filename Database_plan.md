# Database Schema

## Overview
- **Objects** are either an `analysis` or a `geometry`. Each has a unique name, a description, files, and parameters. An object's files are copied into `objects/<name>/` in the project folder.
- **Software** is a fixed catalogue of build targets defined in code (`abaqus_input`, `abaqus_python`, `fluent_python`, `mpcci_python`). Each project picks which ones it uses and can optionally override the command for each one, e.g. `abq2024`.
- **Object software:** an object uses one or more of the project's software. Each can have its own build file, and every object needs at least one build file. All of an object's parameters are passed to every build; build order doesn't matter.
- **Parameters** belong to an object and record what values they can take.
- **Models** combine exactly one analysis with any number of geometries (zero or more). A model stores its own parameter values, which override the object defaults. Creating a model copies its objects' files into `models/<name>/`.
- **Fixed once created:**
  - **Objects:** only `name` and `description` can be changed. Kind, files, software and build files, parameters and choices are locked. The one exception is the file snapshot (`size_bytes`/`mtime_ns`/`sha256`), which "Verify OK" may refresh. To change an object, clone it into a new one.
  - **Models:** `name`, `description`, the build status and the parameter values can be changed. The analysis and geometries are locked.

## Parameter ranges
| type     | `min_value` / `max_value`                 | allowed values          |
|----------|-------------------------------------------|-------------------------|
| `int`    | inclusive numeric bounds (NULL = open)    | n/a                     |
| `float`  | inclusive numeric bounds (NULL = open)    | n/a                     |
| `str`    | min / max **length** (whole numbers, ≥ 0) | n/a                    |
| `choice` | must be NULL                              | `parameter_choices`     |
| `bool`   | must be NULL                              | n/a                     |

All bounds are inclusive.

## Tables
```sql
PRAGMA foreign_keys = ON;   -- must be set on every connection

-- The software this project uses, chosen from the catalogue in code.
-- Keys can't be renamed; they can be added at any time and deleted while unused.
CREATE TABLE software (
    id      INTEGER PRIMARY KEY,
    key     TEXT NOT NULL UNIQUE,   -- catalogue key, e.g. 'abaqus_python'
    command TEXT                    -- e.g. 'abq2024'; NULL = use the config, then the catalogue default
);

-- name doubles as the folder name objects/<name>/, so it must be filesystem-safe
CREATE TABLE objects (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
                CHECK (name <> '' AND name NOT IN ('.', '..') AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
    description TEXT,
    kind        TEXT NOT NULL CHECK (kind IN ('analysis', 'geometry'))
);

CREATE TABLE object_files (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    rel_path    TEXT NOT NULL,            -- relative to objects/<name>/
    size_bytes  INTEGER NOT NULL,         -- edit detection: snapshot taken at import,
    mtime_ns    INTEGER NOT NULL,         --   refreshed by "Verify OK"
    sha256      TEXT    NOT NULL,
    imported_at TEXT    NOT NULL,         -- ISO 8601 timestamp
    UNIQUE (object_id, rel_path)
);

-- Which software an object uses, and the build file for each (optional per software).
CREATE TABLE object_software (
    object_id     INTEGER NOT NULL REFERENCES objects(id) ON DELETE CASCADE,
    software_id   INTEGER NOT NULL REFERENCES software(id),
    build_file_id INTEGER REFERENCES object_files(id),   -- NULL = no build step for this software
    PRIMARY KEY (object_id, software_id),
    UNIQUE (build_file_id)                               -- a file builds at most one software
);

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
);

CREATE TABLE parameter_choices (
    parameter_id INTEGER NOT NULL REFERENCES object_parameters(id) ON DELETE CASCADE,
    value        TEXT NOT NULL,
    PRIMARY KEY (parameter_id, value)
);

-- Objects used by a model can't be deleted while the model exists (default FK behaviour).
-- Insert a model's geometries in the same transaction that creates the model.
-- name doubles as the folder name models/<name>/
CREATE TABLE models (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
                CHECK (name <> '' AND name NOT IN ('.', '..') AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
    description  TEXT,
    analysis_id  INTEGER NOT NULL REFERENCES objects(id),
    build_status TEXT CHECK (build_status IN ('success', 'failed')),  -- NULL = not built yet
    built_at     TEXT,                    -- ISO 8601 timestamp of the last build
    CHECK ((build_status IS NULL) = (built_at IS NULL))
);

CREATE TABLE model_geometries (
    model_id    INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    geometry_id INTEGER NOT NULL REFERENCES objects(id),
    PRIMARY KEY (model_id, geometry_id)
);

CREATE TABLE model_parameter_values (
    model_id     INTEGER NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    parameter_id INTEGER NOT NULL REFERENCES object_parameters(id) ON DELETE CASCADE,
    value        TEXT NOT NULL,
    PRIMARY KEY (model_id, parameter_id)
);
```

## Integrity triggers
These enforce rules that foreign keys can't express.

```sql
-- models.analysis_id must point to an analysis
CREATE TRIGGER models_analysis_kind BEFORE INSERT ON models
WHEN (SELECT kind FROM objects WHERE id = NEW.analysis_id) IS NOT 'analysis'
BEGIN SELECT RAISE(ABORT, 'models.analysis_id must reference an analysis object'); END;

-- model_geometries.geometry_id must point to a geometry
CREATE TRIGGER model_geometries_kind BEFORE INSERT ON model_geometries
WHEN (SELECT kind FROM objects WHERE id = NEW.geometry_id) IS NOT 'geometry'
BEGIN SELECT RAISE(ABORT, 'model_geometries.geometry_id must reference a geometry object'); END;

-- A build file must be one of the same object's files
CREATE TRIGGER object_software_build_file_owner BEFORE INSERT ON object_software
WHEN NEW.build_file_id IS NOT NULL
 AND (SELECT object_id FROM object_files WHERE id = NEW.build_file_id) IS NOT NEW.object_id
BEGIN SELECT RAISE(ABORT, 'build file must belong to the same object'); END;

-- A model's parameter value must belong to its analysis or to one of its geometries
CREATE TRIGGER model_parameter_values_owner BEFORE INSERT ON model_parameter_values
WHEN NOT EXISTS (
    SELECT 1 FROM object_parameters p JOIN models m ON m.id = NEW.model_id
    WHERE p.id = NEW.parameter_id
      AND (p.object_id = m.analysis_id
           OR p.object_id IN (SELECT geometry_id FROM model_geometries WHERE model_id = NEW.model_id))
)
BEGIN SELECT RAISE(ABORT, 'parameter does not belong to an object in this model'); END;

-- ---------------------------------------------------------------------------
-- Objects are locked after creation: only name and description can change.
-- "Delete" triggers only fire while the parent still exists, so deleting a
-- whole object still cascades normally.
-- ---------------------------------------------------------------------------
CREATE TRIGGER objects_locked BEFORE UPDATE ON objects
WHEN NEW.id IS NOT OLD.id OR NEW.kind IS NOT OLD.kind
BEGIN SELECT RAISE(ABORT, 'only an object''s name and description can be changed'); END;

-- Only the snapshot columns may be refreshed (by "Verify OK")
CREATE TRIGGER object_files_locked BEFORE UPDATE ON object_files
WHEN NEW.id IS NOT OLD.id OR NEW.object_id IS NOT OLD.object_id
  OR NEW.rel_path IS NOT OLD.rel_path OR NEW.imported_at IS NOT OLD.imported_at
BEGIN SELECT RAISE(ABORT, 'object files are locked; only the snapshot can be refreshed'); END;

CREATE TRIGGER object_files_no_remove BEFORE DELETE ON object_files
WHEN EXISTS (SELECT 1 FROM objects WHERE id = OLD.object_id)
BEGIN SELECT RAISE(ABORT, 'object files are locked'); END;

CREATE TRIGGER object_parameters_locked BEFORE UPDATE ON object_parameters
BEGIN SELECT RAISE(ABORT, 'object parameters are locked'); END;

CREATE TRIGGER object_parameters_no_remove BEFORE DELETE ON object_parameters
WHEN EXISTS (SELECT 1 FROM objects WHERE id = OLD.object_id)
BEGIN SELECT RAISE(ABORT, 'object parameters are locked'); END;

CREATE TRIGGER parameter_choices_locked BEFORE UPDATE ON parameter_choices
BEGIN SELECT RAISE(ABORT, 'parameter choices are locked'); END;

CREATE TRIGGER parameter_choices_no_remove BEFORE DELETE ON parameter_choices
WHEN EXISTS (SELECT 1 FROM object_parameters WHERE id = OLD.parameter_id)
BEGIN SELECT RAISE(ABORT, 'parameter choices are locked'); END;

CREATE TRIGGER object_software_locked BEFORE UPDATE ON object_software
BEGIN SELECT RAISE(ABORT, 'object software and build files are locked'); END;

CREATE TRIGGER object_software_no_remove BEFORE DELETE ON object_software
WHEN EXISTS (SELECT 1 FROM objects WHERE id = OLD.object_id)
BEGIN SELECT RAISE(ABORT, 'object software and build files are locked'); END;

-- ---------------------------------------------------------------------------
-- Models can't change their objects.
-- (A value's model_id / parameter_id are locked too, so only `value` can be edited.)
-- ---------------------------------------------------------------------------
CREATE TRIGGER models_locked BEFORE UPDATE ON models
WHEN NEW.id IS NOT OLD.id OR NEW.analysis_id IS NOT OLD.analysis_id
BEGIN SELECT RAISE(ABORT, 'a model''s analysis cannot be changed'); END;

CREATE TRIGGER model_geometries_immutable BEFORE UPDATE ON model_geometries
BEGIN SELECT RAISE(ABORT, 'model geometries cannot be changed'); END;

-- Removing a geometry is only allowed as part of deleting the whole model
CREATE TRIGGER model_geometries_no_remove BEFORE DELETE ON model_geometries
WHEN EXISTS (SELECT 1 FROM models WHERE id = OLD.model_id)
BEGIN SELECT RAISE(ABORT, 'model geometries cannot be removed'); END;

CREATE TRIGGER model_parameter_values_keys_immutable BEFORE UPDATE OF model_id, parameter_id ON model_parameter_values
WHEN NEW.model_id IS NOT OLD.model_id OR NEW.parameter_id IS NOT OLD.parameter_id
BEGIN SELECT RAISE(ABORT, 'only model_parameter_values.value can be changed'); END;
```

## Left to application code
- **Value validation:** when a value is written to `model_parameter_values` (or used as `default_value`), check it against the parameter's `type`, its `min_value`/`max_value` (numeric bound or string length), and `parameter_choices`. Doing this in Python gives clearer errors than SQL triggers would.
- **No additions after creation:** the database blocks changing or removing locked rows, but it can't tell creation apart from later, so it still allows *adding* rows. The code must create each object (with its files, software and build files, parameters and choices) and each model (with its geometries) in a single transaction, and refuse to add any of these afterwards.
- **Parameter name clashes:** when a model is created, the parameter names across its analysis and geometries must be unique. Refuse to create the model if two of its objects share a parameter name.
- **Software catalogue:** `software.key` must be a key from the catalogue in code. The catalogue also defines each key's build mode, build file type (`.inp` for `abaqus_input`, `.py` for the `*_python` keys) and default command. The code checks that each build file has the right type for its software.
- **Command lookup:** use `software.command`, then the config, then the catalogue default.
- **Every object needs at least one software and at least one build file.** SQLite can't check this at the end of a transaction, so the code must check it when creating the object.
- **Edit detection:** before a model is created, cloned or rebuilt, check every listed file of its objects. Compare `size_bytes`/`mtime_ns` first and only re-hash when those differ.
  - **Modified** files must be confirmed with "Verify OK", which overwrites the stored snapshot (there is only ever one snapshot per file).
  - **Missing** files block the build.
  - **Unlisted** files in `objects/<name>/` are ignored: building copies only the files listed in `object_files`.
- **Renaming:** renaming an object or model must also move its folder (`objects/<name>/` or `models/<name>/`).
- **Foreign keys:** run `PRAGMA foreign_keys = ON` on every connection.
- **Schema versioning:** optionally use `PRAGMA user_version` to track the schema version for future migrations.

## Open questions (pending Abaqus testing)
- **Build interpreter:** whether Python build scripts run inside Abaqus (`abaqus cae noGUI=...`) and how parameters are passed in.
- **Models with several objects:** which objects need a build file, the build order, and how to handle files with the same name when several objects are copied into one `models/<name>/` folder.
- **Fluent / MPCCI:** how `fluent_python` and `mpcci_python` builds are launched and receive their parameters.
