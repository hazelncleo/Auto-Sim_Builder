import sqlite3

import pytest

from auto_sim_builder.core.params import ParameterSpec, ParamType
from auto_sim_builder.db.queries import (
    delete_choice,
    delete_parameter,
    insert_choice,
    insert_parameter,
    list_choices,
    list_parameters,
    name_exists,
    parameter_names,
    update_parameter,
)


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


def get_parameter(db, object_id, name):
    return db.execute(
        "SELECT * FROM object_parameters WHERE object_id = ? AND name = ?",
        (object_id, name),
    ).fetchone()


def test_insert_parameter_stores_all_fields(db):
    object_id = add_object(db)
    spec = ParameterSpec(
        name="width",
        type=ParamType.FLOAT,
        default_value="2.5",
        min_value=0.0,
        max_value=10.0,
        description="Plate width in mm",
    )
    insert_parameter(db, object_id, spec)
    row = get_parameter(db, object_id, "width")
    assert row is not None
    assert row["type"] == "float"
    assert row["default_value"] == "2.5"
    assert row["min_value"] == 0.0
    assert row["max_value"] == 10.0
    assert row["description"] == "Plate width in mm"


def test_insert_parameter_empty_description_stored_as_empty_string(db):
    object_id = add_object(db)
    insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert get_parameter(db, object_id, "width")["description"] == ""


def test_insert_parameter_unbounded_stored_as_null(db):
    object_id = add_object(db)
    insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    row = get_parameter(db, object_id, "width")
    assert row["min_value"] is None
    assert row["max_value"] is None


@pytest.mark.parametrize("param_type", list(ParamType), ids=[t.value for t in ParamType])
def test_insert_parameter_each_type(db, param_type):
    object_id = add_object(db)
    insert_parameter(db, object_id, ParameterSpec(name="p", type=param_type, default_value="1"))
    assert get_parameter(db, object_id, "p")["type"] == param_type.value


def test_insert_parameter_shows_in_parameter_names(db):
    object_id = add_object(db)
    insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert parameter_names(db, object_id) == ["width"]


def test_insert_parameter_only_on_given_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_parameter(db, plate_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert parameter_names(db, beam_id) == []


def test_insert_parameter_same_name_on_other_object_allowed(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    spec = ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1")
    insert_parameter(db, plate_id, spec)
    insert_parameter(db, beam_id, spec)
    assert parameter_names(db, beam_id) == ["width"]


def test_insert_parameter_duplicate_name_rejected(db):
    object_id = add_object(db)
    spec = ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1")
    insert_parameter(db, object_id, spec)
    with pytest.raises(sqlite3.IntegrityError):
        insert_parameter(db, object_id, spec)


def test_insert_parameter_unknown_object_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_parameter(db, 999, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))


def get_choices(db, parameter_id):
    rows = db.execute(
        "SELECT value FROM parameter_choices WHERE parameter_id = ? ORDER BY rowid",
        (parameter_id,),
    ).fetchall()
    return [row[0] for row in rows]


def choice_spec(*choices, name="material"):
    return ParameterSpec(name=name, type=ParamType.CHOICE, default_value=choices[0], choices=choices)


def test_insert_parameter_returns_new_id(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert type(parameter_id) is int
    assert get_parameter(db, object_id, "width")["id"] == parameter_id


def test_insert_parameter_returns_different_ids(db):
    object_id = add_object(db)
    first = insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    second = insert_parameter(db, object_id, ParameterSpec(name="height", type=ParamType.FLOAT, default_value="1"))
    assert first != second


def test_insert_parameter_stores_choices_in_order(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "aluminium", "copper"))
    assert get_choices(db, parameter_id) == ["steel", "aluminium", "copper"]


def test_insert_parameter_without_choices_stores_none(db):
    parameter_id = insert_parameter(db, add_object(db), ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert get_choices(db, parameter_id) == []


def test_insert_parameter_choices_only_on_new_parameter(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    finish_id = insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    assert get_choices(db, material_id) == ["steel", "copper"]
    assert get_choices(db, finish_id) == ["matte", "gloss"]


def test_insert_parameter_empty_string_choice_allowed(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", ""))
    assert get_choices(db, parameter_id) == ["steel", ""]


def test_insert_parameter_duplicate_choice_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_parameter(db, add_object(db), choice_spec("steel", "steel"))


def test_insert_choice_appends(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    insert_choice(db, parameter_id, "copper")
    assert get_choices(db, parameter_id) == ["steel", "copper"]


def test_insert_choice_same_value_on_other_parameter_allowed(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel"))
    other_id = insert_parameter(db, object_id, choice_spec("copper", name="other"))
    insert_choice(db, other_id, "steel")
    assert get_choices(db, material_id) == ["steel"]
    assert get_choices(db, other_id) == ["copper", "steel"]


def test_insert_choice_duplicate_rejected(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    with pytest.raises(sqlite3.IntegrityError):
        insert_choice(db, parameter_id, "steel")


def test_insert_choice_unknown_parameter_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_choice(db, 999, "steel")


def test_deleting_parameter_deletes_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    db.execute("DELETE FROM object_parameters WHERE id = ?", (parameter_id,))
    assert get_choices(db, parameter_id) == []


def test_list_choices_returns_tuple_of_strings(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    choices = list_choices(db, parameter_id)
    assert type(choices) is tuple
    assert all(type(choice) is str for choice in choices)


def test_list_choices_in_insertion_order(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "aluminium", "copper"))
    insert_choice(db, parameter_id, "brass")
    assert list_choices(db, parameter_id) == ("steel", "aluminium", "copper", "brass")


def test_list_choices_matches_spec(db):
    spec = choice_spec("steel", "", "copper")
    parameter_id = insert_parameter(db, add_object(db), spec)
    assert list_choices(db, parameter_id) == spec.choices


def test_list_choices_only_from_given_parameter(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    assert list_choices(db, material_id) == ("steel", "copper")


def test_list_choices_non_choice_parameter_empty(db):
    parameter_id = insert_parameter(db, add_object(db), ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert list_choices(db, parameter_id) == ()


def test_list_choices_unknown_parameter_empty(db):
    assert list_choices(db, 999) == ()


def test_list_choices_after_parameter_deleted_empty(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    db.execute("DELETE FROM object_parameters WHERE id = ?", (parameter_id,))
    assert list_choices(db, parameter_id) == ()


def test_delete_choice_removes_only_that_choice(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "aluminium", "copper"))
    assert delete_choice(db, parameter_id, "aluminium") is True
    assert list_choices(db, parameter_id) == ("steel", "copper")


def test_delete_choice_only_on_given_parameter(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    other_id = insert_parameter(db, object_id, choice_spec("steel", "brass", name="other"))
    delete_choice(db, material_id, "steel")
    assert list_choices(db, material_id) == ("copper",)
    assert list_choices(db, other_id) == ("steel", "brass")


def test_delete_choice_case_sensitive(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    assert delete_choice(db, parameter_id, "Steel") is False
    assert list_choices(db, parameter_id) == ("steel",)


def test_delete_choice_empty_string(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", ""))
    delete_choice(db, parameter_id, "")
    assert list_choices(db, parameter_id) == ("steel",)


def test_delete_choice_all_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    delete_choice(db, parameter_id, "steel")
    delete_choice(db, parameter_id, "copper")
    assert list_choices(db, parameter_id) == ()


def test_delete_choice_missing_value_returns_false(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    assert delete_choice(db, parameter_id, "brass") is False
    assert list_choices(db, parameter_id) == ("steel", "copper")


def test_delete_choice_unknown_parameter_returns_false(db):
    assert delete_choice(db, 999, "steel") is False


def test_delete_choice_then_re_add_goes_to_end(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    delete_choice(db, parameter_id, "steel")
    insert_choice(db, parameter_id, "steel")
    assert list_choices(db, parameter_id) == ("copper", "steel")


def test_delete_choice_leaves_parameter(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, choice_spec("steel"))
    delete_choice(db, parameter_id, "steel")
    assert parameter_names(db, object_id) == ["material"]


def test_delete_choice_twice_second_returns_false(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    assert delete_choice(db, parameter_id, "steel") is True
    assert delete_choice(db, parameter_id, "steel") is False


def test_delete_parameter_returns_true(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert delete_parameter(db, parameter_id) is True
    assert parameter_names(db, object_id) == []


def test_delete_parameter_only_that_parameter(db):
    object_id = add_object(db)
    width_id = insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    insert_parameter(db, object_id, ParameterSpec(name="height", type=ParamType.FLOAT, default_value="1"))
    delete_parameter(db, width_id)
    assert parameter_names(db, object_id) == ["height"]


def test_delete_parameter_leaves_other_objects(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    spec = ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1")
    width_id = insert_parameter(db, plate_id, spec)
    insert_parameter(db, beam_id, spec)
    delete_parameter(db, width_id)
    assert parameter_names(db, beam_id) == ["width"]


def test_delete_parameter_deletes_its_choices(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    finish_id = insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    delete_parameter(db, material_id)
    assert list_choices(db, material_id) == ()
    assert list_choices(db, finish_id) == ("matte", "gloss")


def test_delete_parameter_unknown_returns_false(db):
    assert delete_parameter(db, 999) is False


def test_delete_parameter_twice_second_returns_false(db):
    parameter_id = insert_parameter(db, add_object(db), ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert delete_parameter(db, parameter_id) is True
    assert delete_parameter(db, parameter_id) is False


def test_delete_parameter_frees_name(db):
    object_id = add_object(db)
    spec = ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1")
    parameter_id = insert_parameter(db, object_id, spec)
    delete_parameter(db, parameter_id)
    insert_parameter(db, object_id, spec)
    assert parameter_names(db, object_id) == ["width"]


def test_delete_parameter_leaves_object(db):
    object_id = add_object(db, "plate")
    parameter_id = insert_parameter(db, object_id, ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    delete_parameter(db, parameter_id)
    assert name_exists(db, "object", "plate")


def width_spec(**changes):
    fields = dict(name="width", type=ParamType.FLOAT, default_value="1")
    return ParameterSpec(**(fields | changes))


def test_update_parameter_returns_true(db):
    parameter_id = insert_parameter(db, add_object(db), width_spec())
    assert update_parameter(db, parameter_id, width_spec(default_value="2")) is True


def test_update_parameter_overwrites_all_fields(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, width_spec(description="old"))
    update_parameter(db, parameter_id, ParameterSpec(
        name="height",
        type=ParamType.INT,
        default_value="5",
        min_value=1.0,
        max_value=10.0,
        description="Plate height",
    ))
    row = get_parameter(db, object_id, "height")
    assert row["id"] == parameter_id
    assert row["type"] == "int"
    assert row["default_value"] == "5"
    assert row["min_value"] == 1.0
    assert row["max_value"] == 10.0
    assert row["description"] == "Plate height"
    assert parameter_names(db, object_id) == ["height"]


def test_update_parameter_clears_bounds_and_description(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, width_spec(min_value=0.0, max_value=5.0, description="old"))
    update_parameter(db, parameter_id, width_spec())
    row = get_parameter(db, object_id, "width")
    assert row["min_value"] is None
    assert row["max_value"] is None
    assert row["description"] == ""


def test_update_parameter_only_that_parameter(db):
    object_id = add_object(db)
    width_id = insert_parameter(db, object_id, width_spec())
    insert_parameter(db, object_id, width_spec(name="height", default_value="7"))
    update_parameter(db, width_id, width_spec(default_value="2"))
    assert get_parameter(db, object_id, "height")["default_value"] == "7"


def test_update_parameter_keeps_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    parameter_id = insert_parameter(db, plate_id, width_spec())
    update_parameter(db, parameter_id, width_spec(default_value="2"))
    assert parameter_names(db, plate_id) == ["width"]
    assert parameter_names(db, beam_id) == []


def test_update_parameter_replaces_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    update_parameter(db, parameter_id, choice_spec("brass", "steel"))
    assert list_choices(db, parameter_id) == ("brass", "steel")


def test_update_parameter_reorders_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper", "brass"))
    update_parameter(db, parameter_id, choice_spec("brass", "steel", "copper"))
    assert list_choices(db, parameter_id) == ("brass", "steel", "copper")


def test_update_parameter_away_from_choice_clears_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    update_parameter(db, parameter_id, width_spec())
    assert list_choices(db, parameter_id) == ()


def test_update_parameter_to_choice_adds_choices(db):
    parameter_id = insert_parameter(db, add_object(db), width_spec())
    update_parameter(db, parameter_id, choice_spec("steel", "copper"))
    assert list_choices(db, parameter_id) == ("steel", "copper")


def test_update_parameter_leaves_other_choices(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    finish_id = insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    update_parameter(db, material_id, choice_spec("brass"))
    assert list_choices(db, finish_id) == ("matte", "gloss")


def test_update_parameter_same_name_allowed(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, width_spec())
    assert update_parameter(db, parameter_id, width_spec(default_value="3")) is True
    assert get_parameter(db, object_id, "width")["default_value"] == "3"


def test_update_parameter_name_clash_rejected(db):
    object_id = add_object(db)
    width_id = insert_parameter(db, object_id, width_spec())
    insert_parameter(db, object_id, width_spec(name="height"))
    with pytest.raises(sqlite3.IntegrityError):
        update_parameter(db, width_id, width_spec(name="height"))


def test_update_parameter_unknown_returns_false(db):
    assert update_parameter(db, 999, width_spec()) is False


def test_update_parameter_unknown_with_choices_returns_false(db):
    assert update_parameter(db, 999, choice_spec("steel")) is False
    assert list_choices(db, 999) == ()


def test_list_parameters_empty_object(db):
    assert list_parameters(db, add_object(db)) == []


def test_list_parameters_unknown_object(db):
    assert list_parameters(db, 999) == []


def test_list_parameters_returns_id_spec_pairs(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, width_spec())
    [(listed_id, spec)] = list_parameters(db, object_id)
    assert listed_id == parameter_id
    assert type(spec) is ParameterSpec


def test_list_parameters_round_trips_spec(db):
    object_id = add_object(db)
    spec = ParameterSpec(
        name="width",
        type=ParamType.FLOAT,
        default_value="2.5",
        min_value=0.0,
        max_value=10.0,
        description="Plate width in mm",
    )
    insert_parameter(db, object_id, spec)
    assert list_parameters(db, object_id)[0][1] == spec


def test_list_parameters_round_trips_choices(db):
    object_id = add_object(db)
    spec = choice_spec("steel", "", "copper")
    insert_parameter(db, object_id, spec)
    assert list_parameters(db, object_id)[0][1] == spec


@pytest.mark.parametrize("param_type", list(ParamType), ids=[t.value for t in ParamType])
def test_list_parameters_type_is_enum(db, param_type):
    object_id = add_object(db)
    insert_parameter(db, object_id, ParameterSpec(name="p", type=param_type, default_value="1"))
    spec = list_parameters(db, object_id)[0][1]
    assert type(spec.type) is ParamType
    assert spec.type is param_type


def test_list_parameters_in_creation_order(db):
    object_id = add_object(db)
    ids = [
        insert_parameter(db, object_id, width_spec(name=name))
        for name in ["width", "Height", "angle"]
    ]
    listed = list_parameters(db, object_id)
    assert [parameter_id for parameter_id, _ in listed] == ids
    assert [spec.name for _, spec in listed] == ["width", "Height", "angle"]


def test_list_parameters_each_gets_own_choices(db):
    object_id = add_object(db)
    insert_parameter(db, object_id, choice_spec("steel", "copper"))
    insert_parameter(db, object_id, width_spec())
    insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    choices = [spec.choices for _, spec in list_parameters(db, object_id)]
    assert choices == [("steel", "copper"), (), ("matte", "gloss")]


def test_list_parameters_only_from_given_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_parameter(db, plate_id, width_spec())
    insert_parameter(db, beam_id, width_spec(name="length"))
    assert [spec.name for _, spec in list_parameters(db, plate_id)] == ["width"]


def test_list_parameters_after_update(db):
    object_id = add_object(db)
    parameter_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    new_spec = choice_spec("brass", name="alloy")
    update_parameter(db, parameter_id, new_spec)
    assert list_parameters(db, object_id) == [(parameter_id, new_spec)]


def test_list_parameters_after_delete(db):
    object_id = add_object(db)
    width_id = insert_parameter(db, object_id, width_spec())
    height_id = insert_parameter(db, object_id, width_spec(name="height"))
    delete_parameter(db, width_id)
    assert [parameter_id for parameter_id, _ in list_parameters(db, object_id)] == [height_id]
