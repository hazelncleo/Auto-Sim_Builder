import sqlite3

import pytest

UNSAFE_NAMES = ["", ".", "..", "../x", "a/b", "a\\b", "has space", "tab\there", "new\nline",
                "star*", "plate?", "ümlaut", "colon:name",
                ".hidden", "...", "-rf", "_private"]
SAFE_NAMES = ["plate", "Plate_V2", "a", "123", "plate_v1.2-a", "fsi.coupled", "x" * 100]


def add_object(db, name="obj", kind="analysis"):
    return db.execute(
        "INSERT INTO objects (name, kind) VALUES (?, ?)", (name, kind)
    ).lastrowid


def add_file(db, object_id, rel_path="build.py"):
    return db.execute(
        "INSERT INTO object_files (object_id, rel_path, size_bytes, mtime_ns, sha256, imported_at)"
        " VALUES (?, ?, 1, 1, 'hash', '2026-10-14T12:00:00')",
        (object_id, rel_path),
    ).lastrowid


def add_software(db, key="abaqus"):
    return db.execute("INSERT INTO software (key) VALUES (?)", (key,)).lastrowid


def add_parameter(db, object_id, name="width", type="float", default="1",
                  min_value=None, max_value=None):
    return db.execute(
        "INSERT INTO object_parameters (object_id, name, type, default_value, min_value, max_value)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (object_id, name, type, default, min_value, max_value),
    ).lastrowid


def add_model(db, analysis_id, name="model"):
    return db.execute(
        "INSERT INTO models (name, analysis_id) VALUES (?, ?)", (name, analysis_id)
    ).lastrowid


def count(db, table):
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


# Names


@pytest.mark.parametrize("name", UNSAFE_NAMES)
def test_unsafe_object_names_rejected(db, name):
    with pytest.raises(sqlite3.IntegrityError):
        add_object(db, name)


@pytest.mark.parametrize("name", UNSAFE_NAMES)
def test_unsafe_model_names_rejected(db, name):
    analysis = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_model(db, analysis, name)


@pytest.mark.parametrize("name", SAFE_NAMES)
def test_safe_names_accepted(db, name):
    analysis = add_object(db, name)
    add_model(db, analysis, name)


# Allowed values


def test_bad_kind_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        add_object(db, kind="mesh")


def test_bad_parameter_type_rejected(db):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, type="complex")


def test_bad_build_status_rejected(db):
    model = add_model(db, add_object(db))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE models SET build_status = 'running', built_at = 'now' WHERE id = ?",
            (model,),
        )


# Parameter ranges


def test_min_above_max_rejected(db):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, min_value=5, max_value=1)


@pytest.mark.parametrize(
    "min_value, max_value", [(None, 5), (1, None), (None, None), (2, 2)]
)
def test_open_and_equal_ranges_accepted(db, min_value, max_value):
    add_parameter(db, add_object(db), min_value=min_value, max_value=max_value)


@pytest.mark.parametrize("type", ["bool", "choice"])
@pytest.mark.parametrize("min_value, max_value", [(0, None), (None, 1), (0, 1)])
def test_range_on_bool_or_choice_rejected(db, type, min_value, max_value):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, type=type, min_value=min_value, max_value=max_value)


@pytest.mark.parametrize(
    "min_value, max_value", [(-1, None), (None, -1), (0.5, None), (None, 2.5)]
)
def test_bad_string_lengths_rejected(db, min_value, max_value):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, type="str", min_value=min_value, max_value=max_value)


def test_whole_string_lengths_accepted(db):
    add_parameter(db, add_object(db), type="str", default="abc", min_value=0, max_value=10)


def test_missing_default_rejected(db):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, default=None)


# Build status


@pytest.mark.parametrize(
    "status, built_at", [(None, None), ("success", "2026-10-14T12:00:00")]
)
def test_build_status_with_matching_timestamp_accepted(db, status, built_at):
    model = add_model(db, add_object(db))
    db.execute(
        "UPDATE models SET build_status = ?, built_at = ? WHERE id = ?",
        (status, built_at, model),
    )


@pytest.mark.parametrize(
    "status, built_at", [("success", None), (None, "2026-10-14T12:00:00")]
)
def test_build_status_without_matching_timestamp_rejected(db, status, built_at):
    model = add_model(db, add_object(db))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "UPDATE models SET build_status = ?, built_at = ? WHERE id = ?",
            (status, built_at, model),
        )


# Uniqueness


def test_duplicate_object_name_rejected(db):
    add_object(db, "plate")
    with pytest.raises(sqlite3.IntegrityError):
        add_object(db, "plate", kind="geometry")


def test_duplicate_model_name_rejected(db):
    analysis = add_object(db)
    add_model(db, analysis, "run")
    with pytest.raises(sqlite3.IntegrityError):
        add_model(db, analysis, "run")


def test_duplicate_software_key_rejected(db):
    add_software(db, "abaqus")
    with pytest.raises(sqlite3.IntegrityError):
        add_software(db, "abaqus")


def test_duplicate_file_path_in_one_object_rejected(db):
    obj = add_object(db)
    add_file(db, obj, "mesh.msh")
    with pytest.raises(sqlite3.IntegrityError):
        add_file(db, obj, "mesh.msh")


def test_same_file_path_in_different_objects_accepted(db):
    add_file(db, add_object(db, "a"), "mesh.msh")
    add_file(db, add_object(db, "b"), "mesh.msh")


def test_duplicate_parameter_name_in_one_object_rejected(db):
    obj = add_object(db)
    add_parameter(db, obj, "width")
    with pytest.raises(sqlite3.IntegrityError):
        add_parameter(db, obj, "width")


def test_same_parameter_name_in_different_objects_accepted(db):
    add_parameter(db, add_object(db, "a"), "width")
    add_parameter(db, add_object(db, "b"), "width")


def test_file_building_two_software_rejected(db):
    obj = add_object(db)
    build_file = add_file(db, obj)
    db.execute(
        "INSERT INTO object_software VALUES (?, ?, ?)", (obj, add_software(db, "abaqus"), build_file)
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO object_software VALUES (?, ?, ?)", (obj, add_software(db, "fluent"), build_file)
        )


def test_several_software_without_build_file_accepted(db):
    obj = add_object(db)
    for key in ("abaqus", "fluent", "mpcci"):
        db.execute("INSERT INTO object_software VALUES (?, ?, NULL)", (obj, add_software(db, key)))


# Foreign keys


def test_deleting_object_used_as_analysis_fails(db):
    analysis = add_object(db)
    add_model(db, analysis)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM objects WHERE id = ?", (analysis,))


def test_deleting_object_used_as_geometry_fails(db):
    model = add_model(db, add_object(db, "a"))
    geometry = add_object(db, "g", kind="geometry")
    db.execute("INSERT INTO model_geometries VALUES (?, ?)", (model, geometry))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM objects WHERE id = ?", (geometry,))


def test_deleting_software_in_use_fails(db):
    software = add_software(db)
    db.execute("INSERT INTO object_software VALUES (?, ?, NULL)", (add_object(db), software))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM software WHERE id = ?", (software,))


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO object_files (object_id, rel_path, size_bytes, mtime_ns, sha256, imported_at)"
        " VALUES (999, 'x', 1, 1, 'hash', 'now')",
        "INSERT INTO models (name, analysis_id) VALUES ('m', 999)",
        "INSERT INTO object_parameters (object_id, name, type, default_value)"
        " VALUES (999, 'p', 'int', '1')",
    ],
)
def test_missing_references_rejected(db, sql):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(sql)


# Cascades


def test_deleting_unused_object_removes_its_rows(db):
    obj = add_object(db)
    build_file = add_file(db, obj)
    db.execute("INSERT INTO object_software VALUES (?, ?, ?)", (obj, add_software(db), build_file))
    parameter = add_parameter(db, obj, "elem", type="choice", default="C3D8")
    db.execute("INSERT INTO parameter_choices VALUES (?, 'C3D8')", (parameter,))

    db.execute("DELETE FROM objects WHERE id = ?", (obj,))

    for table in ("object_files", "object_software", "object_parameters", "parameter_choices"):
        assert count(db, table) == 0, table


def test_deleting_model_removes_links_and_values_but_not_objects(db):
    analysis = add_object(db, "a")
    geometry = add_object(db, "g", kind="geometry")
    parameter = add_parameter(db, geometry)
    model = add_model(db, analysis)
    db.execute("INSERT INTO model_geometries VALUES (?, ?)", (model, geometry))
    db.execute("INSERT INTO model_parameter_values VALUES (?, ?, '2')", (model, parameter))

    db.execute("DELETE FROM models WHERE id = ?", (model,))

    assert count(db, "model_geometries") == 0
    assert count(db, "model_parameter_values") == 0
    assert count(db, "objects") == 2


def test_deleting_parameter_removes_its_choices(db):
    parameter = add_parameter(db, add_object(db), type="choice", default="a")
    db.executemany("INSERT INTO parameter_choices VALUES (?, ?)", [(parameter, "a"), (parameter, "b")])

    db.execute("DELETE FROM object_parameters WHERE id = ?", (parameter,))

    assert count(db, "parameter_choices") == 0


# STRICT


def test_text_in_integer_column_rejected(db):
    obj = add_object(db)
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO object_files (object_id, rel_path, size_bytes, mtime_ns, sha256, imported_at)"
            " VALUES (?, 'x', 'abc', 1, 'hash', 'now')",
            (obj,),
        )


def test_numeric_text_stored_as_integer(db):
    file_id = add_file(db, add_object(db))
    db.execute("UPDATE object_files SET size_bytes = '12' WHERE id = ?", (file_id,))

    assert db.execute("SELECT size_bytes FROM object_files").fetchone()[0] == 12
