import pytest

from auto_sim_builder.db.queries import name_exists, parameter_names


def add_object(db, name="obj", kind="analysis"):
    return db.execute(
        "INSERT INTO objects (name, kind) VALUES (?, ?)", (name, kind)
    ).lastrowid


def add_parameter(db, object_id, name):
    return db.execute(
        "INSERT INTO object_parameters (object_id, name, type, default_value)"
        " VALUES (?, ?, 'float', '1')",
        (object_id, name),
    ).lastrowid


def add_model(db, name, analysis_id):
    return db.execute(
        "INSERT INTO models (name, analysis_id) VALUES (?, ?)", (name, analysis_id)
    ).lastrowid


def test_name_exists_empty_database(db):
    assert not name_exists(db, "object", "plate")
    assert not name_exists(db, "model", "plate")


@pytest.mark.parametrize("name", ["plate", "Plate", "PLATE"], ids=["exact", "capital", "upper"])
def test_object_name_exists_ignoring_case(db, name):
    add_object(db, "plate")
    assert name_exists(db, "object", name)


@pytest.mark.parametrize("name", ["run_1", "Run_1", "RUN_1"], ids=["exact", "capital", "upper"])
def test_model_name_exists_ignoring_case(db, name):
    add_model(db, "run_1", add_object(db))
    assert name_exists(db, "model", name)


def test_different_name_not_found(db):
    add_object(db, "plate")
    assert not name_exists(db, "object", "plate2")
    assert not name_exists(db, "object", "plat")


def test_object_and_model_names_are_separate(db):
    add_model(db, "plate", add_object(db, "analysis"))
    assert not name_exists(db, "object", "plate")
    assert not name_exists(db, "model", "analysis")


@pytest.mark.parametrize("name", ["plate", "Plate"], ids=["same", "case-only"])
def test_exclude_id_ignores_renamed_row(db, name):
    plate_id = add_object(db, "plate")
    assert not name_exists(db, "object", name, exclude_id=plate_id)


def test_exclude_id_still_finds_other_rows(db):
    plate_id = add_object(db, "plate")
    add_object(db, "beam")
    assert name_exists(db, "object", "Beam", exclude_id=plate_id)


def test_unknown_kind_rejected(db):
    with pytest.raises(KeyError):
        name_exists(db, "objects", "plate")


def test_parameter_names_empty_object(db):
    assert parameter_names(db, add_object(db)) == []


def test_parameter_names_returns_strings(db):
    object_id = add_object(db)
    add_parameter(db, object_id, "width")
    add_parameter(db, object_id, "Height")
    names = parameter_names(db, object_id)
    assert sorted(names) == ["Height", "width"]
    assert all(type(name) is str for name in names)


def test_parameter_names_only_from_given_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    add_parameter(db, plate_id, "width")
    add_parameter(db, beam_id, "length")
    assert parameter_names(db, plate_id) == ["width"]


def test_parameter_names_exclude_id(db):
    object_id = add_object(db)
    width_id = add_parameter(db, object_id, "width")
    add_parameter(db, object_id, "height")
    assert parameter_names(db, object_id, exclude_id=width_id) == ["height"]


def test_parameter_names_exclude_id_from_other_object_ignored(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    add_parameter(db, plate_id, "width")
    length_id = add_parameter(db, beam_id, "length")
    assert parameter_names(db, plate_id, exclude_id=length_id) == ["width"]


def test_parameter_names_unknown_object(db):
    assert parameter_names(db, 999) == []
