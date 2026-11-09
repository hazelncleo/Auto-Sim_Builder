import sqlite3

import pytest

from auto_sim_builder.core.specs import FileSpec, ObjectKind, ObjectSpec, ParameterSpec, ParamType
from auto_sim_builder.db.queries import (
    delete_choice,
    delete_object,
    delete_parameter,
    get_object,
    insert_object,
    insert_object_file,
    insert_choice,
    insert_parameter,
    list_choices,
    list_object_files,
    list_objects,
    list_parameters,
    models_using_object,
    name_exists,
    parameter_names,
    update_file_snapshot,
    update_object,
    update_parameter,
)


def add_object(db, name="obj", kind="analysis"):
    return insert_object(db, ObjectSpec(name=name, kind=ObjectKind(kind)))


def add_parameter(db, object_id, name):
    return insert_parameter(
        db, object_id, ParameterSpec(name=name, type=ParamType.FLOAT, default_value="1")
    )


def add_model(db, name, analysis_id):
    return db.execute(
        "INSERT INTO models (name, analysis_id) VALUES (?, ?)", (name, analysis_id)
    ).lastrowid


def add_geometry(db, model_id, geometry_id):
    db.execute(
        "INSERT INTO model_geometries (model_id, geometry_id) VALUES (?, ?)",
        (model_id, geometry_id),
    )


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
    assert list_choices(db, parameter_id) == ("steel", "aluminium", "copper")


def test_insert_parameter_without_choices_stores_none(db):
    parameter_id = insert_parameter(db, add_object(db), ParameterSpec(name="width", type=ParamType.FLOAT, default_value="1"))
    assert list_choices(db, parameter_id) == ()


def test_insert_parameter_choices_only_on_new_parameter(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    finish_id = insert_parameter(db, object_id, choice_spec("matte", "gloss", name="finish"))
    assert list_choices(db, material_id) == ("steel", "copper")
    assert list_choices(db, finish_id) == ("matte", "gloss")


def test_insert_parameter_empty_string_choice_allowed(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", ""))
    assert list_choices(db, parameter_id) == ("steel", "")


def test_insert_parameter_duplicate_choice_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_parameter(db, add_object(db), choice_spec("steel", "steel"))


def test_insert_choice_appends(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    insert_choice(db, parameter_id, "copper")
    assert list_choices(db, parameter_id) == ("steel", "copper")


def test_insert_choice_same_value_on_other_parameter_allowed(db):
    object_id = add_object(db)
    material_id = insert_parameter(db, object_id, choice_spec("steel"))
    other_id = insert_parameter(db, object_id, choice_spec("copper", name="other"))
    insert_choice(db, other_id, "steel")
    assert list_choices(db, material_id) == ("steel",)
    assert list_choices(db, other_id) == ("copper", "steel")


def test_insert_choice_duplicate_rejected(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel"))
    with pytest.raises(sqlite3.IntegrityError):
        insert_choice(db, parameter_id, "steel")


def test_insert_choice_unknown_parameter_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_choice(db, 999, "steel")


def test_deleting_parameter_deletes_choices(db):
    parameter_id = insert_parameter(db, add_object(db), choice_spec("steel", "copper"))
    delete_parameter(db, parameter_id)
    assert list_choices(db, parameter_id) == ()


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
    delete_parameter(db, parameter_id)
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


def get_object_row(db, name):
    return db.execute("SELECT * FROM objects WHERE name = ?", (name,)).fetchone()


def test_insert_object_stores_all_fields(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS, description="Flat plate"))
    row = get_object_row(db, "plate")
    assert row is not None
    assert row["kind"] == "analysis"
    assert row["description"] == "Flat plate"


def test_insert_object_returns_new_id(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert type(object_id) is int
    assert get_object_row(db, "plate")["id"] == object_id


def test_insert_object_returns_different_ids(db):
    first = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    second = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    assert first != second


@pytest.mark.parametrize("kind", list(ObjectKind), ids=[k.value for k in ObjectKind])
def test_insert_object_each_kind(db, kind):
    insert_object(db, ObjectSpec(name="plate", kind=kind))
    assert get_object_row(db, "plate")["kind"] == kind.value


def test_insert_object_empty_description_stored_as_empty_string(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert get_object_row(db, "plate")["description"] == ""


def test_insert_object_shows_in_name_exists(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert name_exists(db, "object", "Plate")


def test_insert_object_can_hold_parameters(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_parameter(db, object_id, width_spec())
    assert parameter_names(db, object_id) == ["width"]


def test_insert_object_duplicate_name_rejected(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    with pytest.raises(sqlite3.IntegrityError):
        insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.GEOMETRY))


@pytest.mark.parametrize("name", ["", "_plate", "my plate", "plate/1"], ids=["empty", "underscore-first", "space", "slash"])
def test_insert_object_unsafe_name_rejected(db, name):
    with pytest.raises(sqlite3.IntegrityError):
        insert_object(db, ObjectSpec(name=name, kind=ObjectKind.ANALYSIS))


def test_list_objects_empty_database(db):
    assert list_objects(db) == []


def test_list_objects_returns_id_spec_pairs(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    [(listed_id, spec)] = list_objects(db)
    assert listed_id == object_id
    assert type(spec) is ObjectSpec


def test_list_objects_round_trips_spec(db):
    spec = ObjectSpec(name="plate", kind=ObjectKind.GEOMETRY, description="Flat plate")
    insert_object(db, spec)
    assert list_objects(db)[0][1] == spec


@pytest.mark.parametrize("kind", list(ObjectKind), ids=[k.value for k in ObjectKind])
def test_list_objects_kind_is_enum(db, kind):
    insert_object(db, ObjectSpec(name="plate", kind=kind))
    spec = list_objects(db)[0][1]
    assert type(spec.kind) is ObjectKind
    assert spec.kind is kind


def test_list_objects_sorted_by_name(db):
    for name in ["plate", "beam", "shell"]:
        insert_object(db, ObjectSpec(name=name, kind=ObjectKind.ANALYSIS))
    assert [spec.name for _, spec in list_objects(db)] == ["beam", "plate", "shell"]


def test_list_objects_sorted_ignoring_case(db):
    for name in ["plate", "Beam", "anchor", "Shell"]:
        insert_object(db, ObjectSpec(name=name, kind=ObjectKind.ANALYSIS))
    assert [spec.name for _, spec in list_objects(db)] == ["anchor", "Beam", "plate", "Shell"]


def test_list_objects_ids_follow_their_names(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    beam_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    assert [(object_id, spec.name) for object_id, spec in list_objects(db)] == [
        (beam_id, "beam"),
        (plate_id, "plate"),
    ]


def test_list_objects_includes_both_kinds(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    assert {spec.kind for _, spec in list_objects(db)} == {ObjectKind.ANALYSIS, ObjectKind.GEOMETRY}


def test_list_objects_after_delete(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    delete_object(db, plate_id)
    assert [spec.name for _, spec in list_objects(db)] == ["beam"]


def test_get_object_found(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    result = get_object(db, object_id)
    assert result is not None
    found_id, spec = result
    assert found_id == object_id
    assert type(spec) is ObjectSpec


def test_get_object_round_trips_spec(db):
    spec = ObjectSpec(name="plate", kind=ObjectKind.GEOMETRY, description="Flat plate")
    object_id = insert_object(db, spec)
    assert get_object(db, object_id) == (object_id, spec)


@pytest.mark.parametrize("kind", list(ObjectKind), ids=[k.value for k in ObjectKind])
def test_get_object_kind_is_enum(db, kind):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=kind))
    spec = get_object(db, object_id)[1]
    assert type(spec.kind) is ObjectKind
    assert spec.kind is kind


def test_get_object_picks_right_object(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    beam_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY, description="Beam"))
    insert_object(db, ObjectSpec(name="shell", kind=ObjectKind.GEOMETRY))
    assert get_object(db, beam_id) == (
        beam_id,
        ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY, description="Beam"),
    )


def test_get_object_matches_list_objects(db):
    for name in ["plate", "beam"]:
        insert_object(db, ObjectSpec(name=name, kind=ObjectKind.ANALYSIS))
    for object_id, spec in list_objects(db):
        assert get_object(db, object_id) == (object_id, spec)


def test_get_object_empty_database(db):
    assert get_object(db, 1) is None


def test_get_object_unknown_id(db):
    insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert get_object(db, 999) is None


def test_get_object_after_delete(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    delete_object(db, object_id)
    assert get_object(db, object_id) is None


def test_delete_object_returns_true(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert delete_object(db, object_id) is True
    assert get_object(db, object_id) is None


def test_delete_object_only_that_object(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    delete_object(db, plate_id)
    assert [spec.name for _, spec in list_objects(db)] == ["beam"]


def test_delete_object_unknown_returns_false(db):
    assert delete_object(db, 999) is False


def test_delete_object_twice_second_returns_false(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert delete_object(db, object_id) is True
    assert delete_object(db, object_id) is False


def test_delete_object_frees_name(db):
    spec = ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS)
    delete_object(db, insert_object(db, spec))
    assert not name_exists(db, "object", "plate")
    insert_object(db, spec)
    assert name_exists(db, "object", "plate")


def test_delete_object_deletes_parameters_and_choices(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    material_id = insert_parameter(db, object_id, choice_spec("steel", "copper"))
    insert_parameter(db, object_id, width_spec())
    delete_object(db, object_id)
    assert list_parameters(db, object_id) == []
    assert list_choices(db, material_id) == ()


def test_delete_object_leaves_other_parameters(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    beam_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    insert_parameter(db, plate_id, width_spec())
    material_id = insert_parameter(db, beam_id, choice_spec("steel"))
    delete_object(db, plate_id)
    assert parameter_names(db, beam_id) == ["material"]
    assert list_choices(db, material_id) == ("steel",)


def test_delete_object_used_as_analysis_rejected(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    add_model(db, "run_1", object_id)
    with pytest.raises(sqlite3.IntegrityError):
        delete_object(db, object_id)
    assert get_object(db, object_id) is not None


def test_delete_object_used_as_geometry_rejected(db):
    analysis_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    geometry_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    model_id = add_model(db, "run_1", analysis_id)
    add_geometry(db, model_id, geometry_id)
    with pytest.raises(sqlite3.IntegrityError):
        delete_object(db, geometry_id)
    assert get_object(db, geometry_id) is not None


def test_delete_object_allowed_after_model_deleted(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    model_id = add_model(db, "run_1", object_id)
    db.execute("DELETE FROM models WHERE id = ?", (model_id,))
    assert delete_object(db, object_id) is True


def test_update_object_returns_true(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert update_object(db, object_id, "plate", "New description") is True


def test_update_object_renames(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    update_object(db, object_id, "panel", "")
    assert get_object(db, object_id)[1].name == "panel"
    assert not name_exists(db, "object", "plate")


def test_update_object_changes_description(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    update_object(db, object_id, "plate", "Flat plate")
    assert get_object(db, object_id)[1].description == "Flat plate"


def test_update_object_clears_description(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS, description="old"))
    update_object(db, object_id, "plate", "")
    assert get_object_row(db, "plate")["description"] == ""


@pytest.mark.parametrize("kind", list(ObjectKind), ids=[k.value for k in ObjectKind])
def test_update_object_keeps_kind(db, kind):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=kind))
    update_object(db, object_id, "panel", "Renamed")
    assert get_object(db, object_id) == (
        object_id,
        ObjectSpec(name="panel", kind=kind, description="Renamed"),
    )


def test_update_object_only_that_object(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS, description="Plate"))
    beam_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY, description="Beam"))
    update_object(db, plate_id, "panel", "Panel")
    assert get_object(db, beam_id) == (
        beam_id,
        ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY, description="Beam"),
    )


def test_update_object_keeps_parameters(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_parameter(db, object_id, choice_spec("steel", "copper"))
    before = list_parameters(db, object_id)
    update_object(db, object_id, "panel", "Renamed")
    assert list_parameters(db, object_id) == before


@pytest.mark.parametrize("name", ["plate", "Plate"], ids=["same", "case-only"])
def test_update_object_same_name_allowed(db, name):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert update_object(db, object_id, name, "") is True
    assert get_object(db, object_id)[1].name == name


def test_update_object_name_clash_rejected(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    with pytest.raises(sqlite3.IntegrityError):
        update_object(db, plate_id, "beam", "")


@pytest.mark.parametrize("name", ["", "_plate", "my plate", "plate/1"], ids=["empty", "underscore-first", "space", "slash"])
def test_update_object_unsafe_name_rejected(db, name):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    with pytest.raises(sqlite3.IntegrityError):
        update_object(db, object_id, name, "")


def test_update_object_unknown_returns_false(db):
    assert update_object(db, 999, "plate", "") is False


def test_models_using_object_unused(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    assert models_using_object(db, object_id) == []


def test_models_using_object_unknown_object(db):
    assert models_using_object(db, 999) == []


def test_models_using_object_as_analysis(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    model_id = add_model(db, "run_1", object_id)
    assert models_using_object(db, object_id) == [model_id]


def test_models_using_object_as_geometry(db):
    analysis_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    geometry_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    model_id = add_model(db, "run_1", analysis_id)
    add_geometry(db, model_id, geometry_id)
    assert models_using_object(db, geometry_id) == [model_id]


def test_models_using_object_returns_ints(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    add_model(db, "run_1", object_id)
    assert all(type(model_id) is int for model_id in models_using_object(db, object_id))


def test_models_using_object_several_models_sorted(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    model_ids = [add_model(db, name, object_id) for name in ["run_3", "run_1", "run_2"]]
    assert models_using_object(db, object_id) == sorted(model_ids)


def test_models_using_object_analysis_and_geometry_combined(db):
    analysis_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    geometry_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    first = add_model(db, "run_1", geometry_id)
    second = add_model(db, "run_2", analysis_id)
    add_geometry(db, second, geometry_id)
    assert models_using_object(db, geometry_id) == [first, second]


def test_models_using_object_no_duplicates(db):
    object_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    model_id = add_model(db, "run_1", object_id)
    add_geometry(db, model_id, object_id)
    assert models_using_object(db, object_id) == [model_id]


def test_models_using_object_only_given_object(db):
    plate_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    shell_id = insert_object(db, ObjectSpec(name="shell", kind=ObjectKind.ANALYSIS))
    beam_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    plate_model = add_model(db, "run_1", plate_id)
    shell_model = add_model(db, "run_2", shell_id)
    add_geometry(db, shell_model, beam_id)
    assert models_using_object(db, plate_id) == [plate_model]
    assert models_using_object(db, shell_id) == [shell_model]
    assert models_using_object(db, beam_id) == [shell_model]


def test_models_using_object_geometry_not_counted_for_analysis(db):
    analysis_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    geometry_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    model_id = add_model(db, "run_1", analysis_id)
    add_geometry(db, model_id, geometry_id)
    assert models_using_object(db, analysis_id) == [model_id]
    assert models_using_object(db, geometry_id) == [model_id]


def test_models_using_object_empty_after_model_deleted(db):
    analysis_id = insert_object(db, ObjectSpec(name="plate", kind=ObjectKind.ANALYSIS))
    geometry_id = insert_object(db, ObjectSpec(name="beam", kind=ObjectKind.GEOMETRY))
    model_id = add_model(db, "run_1", analysis_id)
    add_geometry(db, model_id, geometry_id)
    db.execute("DELETE FROM models WHERE id = ?", (model_id,))
    assert models_using_object(db, analysis_id) == []
    assert models_using_object(db, geometry_id) == []


def file_spec(**changes):
    fields = dict(
        rel_path="plate.py",
        size_bytes=1234,
        mtime_ns=1_700_000_000_000_000_000,
        sha256="a" * 64,
        imported_at="2026-11-09T12:00:00",
    )
    return FileSpec(**(fields | changes))


def get_file_rows(db, object_id):
    return db.execute(
        "SELECT * FROM object_files WHERE object_id = ? ORDER BY id", (object_id,)
    ).fetchall()


def test_insert_object_file_stores_all_fields(db):
    object_id = add_object(db)
    insert_object_file(db, object_id, file_spec())
    [row] = get_file_rows(db, object_id)
    assert row["rel_path"] == "plate.py"
    assert row["size_bytes"] == 1234
    assert row["mtime_ns"] == 1_700_000_000_000_000_000
    assert row["sha256"] == "a" * 64
    assert row["imported_at"] == "2026-11-09T12:00:00"


def test_insert_object_file_returns_new_id(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec())
    assert type(file_id) is int
    assert get_file_rows(db, object_id)[0]["id"] == file_id


def test_insert_object_file_returns_different_ids(db):
    object_id = add_object(db)
    first = insert_object_file(db, object_id, file_spec())
    second = insert_object_file(db, object_id, file_spec(rel_path="mesh.inp"))
    assert first != second


def test_insert_object_file_nested_path_stored_as_given(db):
    object_id = add_object(db)
    insert_object_file(db, object_id, file_spec(rel_path="mesh/parts/plate.inp"))
    assert get_file_rows(db, object_id)[0]["rel_path"] == "mesh/parts/plate.inp"


def test_insert_object_file_empty_file(db):
    object_id = add_object(db)
    insert_object_file(db, object_id, file_spec(size_bytes=0))
    assert get_file_rows(db, object_id)[0]["size_bytes"] == 0


def test_insert_object_file_only_on_given_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_object_file(db, plate_id, file_spec())
    assert len(get_file_rows(db, plate_id)) == 1
    assert get_file_rows(db, beam_id) == []


def test_insert_object_file_same_path_on_other_object_allowed(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_object_file(db, plate_id, file_spec())
    insert_object_file(db, beam_id, file_spec())
    assert get_file_rows(db, beam_id)[0]["rel_path"] == "plate.py"


def test_insert_object_file_duplicate_path_rejected(db):
    object_id = add_object(db)
    insert_object_file(db, object_id, file_spec())
    with pytest.raises(sqlite3.IntegrityError):
        insert_object_file(db, object_id, file_spec(sha256="b" * 64))


def test_insert_object_file_unknown_object_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        insert_object_file(db, 999, file_spec())


def test_delete_object_deletes_its_files(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_object_file(db, plate_id, file_spec())
    insert_object_file(db, beam_id, file_spec())
    delete_object(db, plate_id)
    assert get_file_rows(db, plate_id) == []
    assert len(get_file_rows(db, beam_id)) == 1


def test_list_object_files_empty_object(db):
    assert list_object_files(db, add_object(db)) == []


def test_list_object_files_unknown_object(db):
    assert list_object_files(db, 999) == []


def test_list_object_files_returns_id_spec_pairs(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec())
    [(listed_id, spec)] = list_object_files(db, object_id)
    assert listed_id == file_id
    assert type(spec) is FileSpec


def test_list_object_files_round_trips_spec(db):
    object_id = add_object(db)
    spec = file_spec(rel_path="mesh/plate.inp", size_bytes=0)
    file_id = insert_object_file(db, object_id, spec)
    assert list_object_files(db, object_id) == [(file_id, spec)]


def test_list_object_files_only_from_given_object(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    insert_object_file(db, plate_id, file_spec(rel_path="plate.py"))
    insert_object_file(db, beam_id, file_spec(rel_path="beam.py"))
    assert [spec.rel_path for _, spec in list_object_files(db, beam_id)] == ["beam.py"]
    assert [spec.rel_path for _, spec in list_object_files(db, plate_id)] == ["plate.py"]


def test_list_object_files_sorted_by_path(db):
    object_id = add_object(db)
    paths = ["plate.py", "mesh/part.inp", "build.py", "mesh/assembly.inp", "README.md"]
    for path in paths:
        insert_object_file(db, object_id, file_spec(rel_path=path))
    assert [spec.rel_path for _, spec in list_object_files(db, object_id)] == sorted(paths)


def test_list_object_files_ids_follow_their_paths(db):
    object_id = add_object(db)
    plate_id = insert_object_file(db, object_id, file_spec(rel_path="plate.py"))
    build_id = insert_object_file(db, object_id, file_spec(rel_path="build.py"))
    assert [(file_id, spec.rel_path) for file_id, spec in list_object_files(db, object_id)] == [
        (build_id, "build.py"),
        (plate_id, "plate.py"),
    ]


def test_list_object_files_after_object_deleted(db):
    object_id = add_object(db)
    insert_object_file(db, object_id, file_spec())
    delete_object(db, object_id)
    assert list_object_files(db, object_id) == []


def test_update_file_snapshot_returns_true(db):
    file_id = insert_object_file(db, add_object(db), file_spec())
    assert update_file_snapshot(db, file_id, 99, 2, "b" * 64) is True


def test_update_file_snapshot_changes_snapshot(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec())
    update_file_snapshot(db, file_id, 4321, 1_800_000_000_000_000_000, "b" * 64)
    [(_, spec)] = list_object_files(db, object_id)
    assert spec.size_bytes == 4321
    assert spec.mtime_ns == 1_800_000_000_000_000_000
    assert spec.sha256 == "b" * 64


def test_update_file_snapshot_keeps_path_and_import_time(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec(rel_path="mesh/plate.inp"))
    update_file_snapshot(db, file_id, 4321, 2, "b" * 64)
    [(listed_id, spec)] = list_object_files(db, object_id)
    assert listed_id == file_id
    assert spec.rel_path == "mesh/plate.inp"
    assert spec.imported_at == "2026-11-09T12:00:00"


def test_update_file_snapshot_to_empty_file(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec())
    update_file_snapshot(db, file_id, 0, 2, "b" * 64)
    assert list_object_files(db, object_id)[0][1].size_bytes == 0


def test_update_file_snapshot_same_values_returns_true(db):
    spec = file_spec()
    file_id = insert_object_file(db, add_object(db), spec)
    assert update_file_snapshot(db, file_id, spec.size_bytes, spec.mtime_ns, spec.sha256) is True


def test_update_file_snapshot_only_that_file(db):
    object_id = add_object(db)
    plate_id = insert_object_file(db, object_id, file_spec(rel_path="plate.py"))
    build_spec = file_spec(rel_path="build.py")
    build_id = insert_object_file(db, object_id, build_spec)
    update_file_snapshot(db, plate_id, 4321, 2, "b" * 64)
    assert (build_id, build_spec) in list_object_files(db, object_id)


def test_update_file_snapshot_leaves_other_objects(db):
    plate_id = add_object(db, "plate")
    beam_id = add_object(db, "beam")
    file_id = insert_object_file(db, plate_id, file_spec())
    beam_file = file_spec()
    insert_object_file(db, beam_id, beam_file)
    update_file_snapshot(db, file_id, 4321, 2, "b" * 64)
    assert list_object_files(db, beam_id)[0][1] == beam_file


def test_update_file_snapshot_unknown_returns_false(db):
    assert update_file_snapshot(db, 999, 1, 1, "a" * 64) is False


def test_update_file_snapshot_after_object_deleted_returns_false(db):
    object_id = add_object(db)
    file_id = insert_object_file(db, object_id, file_spec())
    delete_object(db, object_id)
    assert update_file_snapshot(db, file_id, 1, 1, "a" * 64) is False
