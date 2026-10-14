# Database Schema

## Overview
- **Objects** are either an `analysis` or a `geometry`. Each has a unique name, a description, files, and parameters. An object's files are copied into `objects/<name>/` in the project folder.
- **Software** is a fixed catalogue of programs defined in code (`abaqus`, `fluent`, `mpcci`). How a build file is built depends on its software and file type, and is handled in code, not the database. For example, an Abaqus `.py` is run with Python, while an Abaqus `.inp` gets a `*PARAMETER` block added. Each project picks which ones it uses and can optionally override the command for each one, e.g. `abq2024`.
- **Object software:** an object uses one or more of the project's software. Each can have its own build file, and every object needs at least one build file. All of an object's parameters are passed to every build; build order doesn't matter.
- **Parameters** belong to an object and record what values they can take.
- **Models** combine exactly one analysis with any number of geometries (zero or more). A model stores its own parameter values, which override the object defaults. Creating a model copies its objects' files into `models/<name>/`.
- **Fixed once created** (enforced in `core/`, see below):
  - **Objects:** `name` and `description` can always be changed. **Parameters** (and their choices) can be added, edited, cloned and deleted **until the object is used by a model**, then they lock. They unlock again if every model using the object is deleted. Kind, files, software and build files are always locked. The one exception is the file snapshot (`size_bytes`/`mtime_ns`/`sha256`), which "Verify OK" may refresh. For any other change, clone the object into a new one.
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
`src/auto_sim_builder/db/schema.sql` contains these tables:
- **No PRAGMA:** `foreign_keys` is per connection, so `connect()` sets it.
- **One transaction:** wrapped in `BEGIN; … COMMIT;`, so a failure never leaves half a schema.
- **Version stamp:** ends with `PRAGMA user_version = 1;`, so `connect()` can tell a new file (`0`) from a ready one (`1`) or one that needs migrating (anything else).
- **`STRICT` tables:** column types are enforced (needs SQLite ≥ 3.37). Values that convert without loss are converted (`'12'` → `12`, `42` → `'42'`); anything else is rejected, e.g. `'abc'` in an `INTEGER` column.

```sql
-- PRAGMA foreign_keys = ON is set by connect() on every connection, not here.

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
                CHECK (name <> '' AND name NOT IN ('.', '..') AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
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
                CHECK (name <> '' AND name NOT IN ('.', '..') AND name NOT GLOB '*[^A-Za-z0-9_.-]*'),
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
```

## Database vs code
The database only checks the **shape** of the data: keys, foreign keys, `NOT NULL`, `UNIQUE` and `CHECK`s. There are **no triggers**. Every rule about **what is allowed when** lives in `core/`. `core/` is the only code that writes to the database: the interface and the helper commands both go through it. The interface also uses these checks to explain why an action isn't available *before* the user tries it.

**What the database still guarantees by itself**
- **Foreign keys:** an object can't be deleted while a model uses it, and software can't be deleted while an object uses it.
- **Cascades:** deleting an object removes its files, software links, parameters and choices. Deleting a model removes its geometry links and values.
- **Keys and checks:** unique names, filesystem-safe names, valid `kind`/`type`/`build_status`, consistent parameter ranges, and `build_status`/`built_at` set together.

## Rules enforced in `core/`

### Creating
- **One transaction:** create each object together with its files, software and build files, and each model together with its geometries and values.
- **Object completeness:** every object has at least one software and at least one build file.
- **Software keys:** `software.key` must be a key from the catalogue in code.
- **Build files:** a build file must be one of the same object's files, and its file type must be one its software accepts (Abaqus: `.py` or `.inp`). The build mode comes from the file type.
- **Model objects:** `models.analysis_id` must be an `analysis` object, and every geometry link must point to a `geometry` object.
- **Parameter name clashes:** parameter names must be unique across a model's analysis and geometries. Refuse to create the model otherwise.

### Locks
- **Objects:** only `name` and `description` change. Kind, files, software and build files never change, and no files or software are added after creation. The one exception is "Verify OK", which may refresh a file's snapshot (`size_bytes`/`mtime_ns`/`sha256`).
- **Parameters and choices:** they can be added, edited, cloned and deleted only while the object is **unused**, meaning it isn't any model's analysis or geometry. They lock again as soon as a model uses the object.
- **Choices:** only `choice` parameters have choices. Delete a parameter's choices before changing its type away from `choice`.
- **Models:** only `name`, `description`, the build status and the values change. Geometries can't be added or removed after creation.
- **Parameter values:** a value's parameter must belong to one of the model's objects. Only the `value` column is ever updated.

### Values
- **Validation:** whenever a value is written to `model_parameter_values` or set as `default_value`, check it against the parameter's `type`, `min_value`/`max_value` (numeric bound or string length) and `parameter_choices`.
- **Bool values:** accept `true`/`false` and `1`/`0`, ignoring case (so `True` and `TRUE` work too). Always store the Python spellings `"True"`/`"False"`. These go into an Abaqus `*PARAMETER` block as they are, and become a Python `bool` in the `params` dict.
- **Editing parameters:** when a parameter's type, range or choices change, re-check its `default_value` against them.

### Files and folders
- **Edit detection:** before a model is created, cloned or rebuilt, check every listed file of its objects. Compare `size_bytes`/`mtime_ns` first and only re-hash when those differ.
  - **Modified** files must be confirmed with "Verify OK", which overwrites the stored snapshot (there is only ever one snapshot per file).
  - **Missing** files block the build.
  - **Unlisted** files in `objects/<name>/` are ignored: building copies only the files listed in `object_files`.
- **Renaming:** renaming an object or model also moves its folder (`objects/<name>/` or `models/<name>/`).

### Connections and config
- **Foreign keys:** run `PRAGMA foreign_keys = ON` on every connection; the foreign keys and cascades depend on it.
- **Applying the schema:** `connect()` reads `schema.sql` with `importlib.resources`, i.e. `files("auto_sim_builder.db").joinpath("schema.sql").read_text()`, never a bare `open("schema.sql")`, which would look in the user's project folder. It runs the file with `executescript()` when `PRAGMA user_version` is `0`.
- **Schema versioning:** `user_version = 1` means the schema is ready. Any other value means the database needs migrating.
- **Command lookup:** use `software.command`, then the config, then the catalogue default.

## Open questions (pending Abaqus testing)
- **Build interpreter:** whether Python build scripts run inside Abaqus (`abaqus cae noGUI=...`) and how parameters are passed in.
- **Models with several objects:** which objects need a build file, the build order, and how to handle files with the same name when several objects are copied into one `models/<name>/` folder.
- **Fluent / MPCCI:** how Fluent and MPCCI builds are launched and receive their parameters.
