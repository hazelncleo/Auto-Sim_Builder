import sqlite3
from typing import Literal


_NAME_TABLES = {"object" : "objects", "model" : "models"}


def name_exists(
    connection: sqlite3.Connection,
    kind: Literal["object", "model"],
    name: str,
    exclude_id: int | None = None
    ) -> bool:
    """Check if a given object/model name exists in the database"""
    
    table = _NAME_TABLES[kind]

    row = connection.execute(
        f"SELECT 1 FROM {table} WHERE name = ? COLLATE NOCASE AND id IS NOT ?",
        (name, exclude_id)
    ).fetchone()
    
    return row is not None


def insert_object():
    pass


def get_object():
    pass


def list_objects():
    pass


def update_object():
    pass


def delete_object():
    pass


def models_using_object():
    pass


def insert_object_file():
    pass


def list_object_files():
    pass


def update_file_snapshot():
    pass


def insert_software():
    pass


def delete_software():
    pass


def list_software():
    pass


def set_software_command():
    pass


def objects_using_software():
    pass


def insert_object_software():
    pass


def list_object_software():
    pass


def parameter_names(
    connection: sqlite3.Connection,
    object_id: int,
    exclude_id: int | None = None
    ) -> list[str]:
    """Returns a list of all parameter names in an object"""

    names = connection.execute(
        "SELECT name FROM object_parameters WHERE object_id = ? AND id IS NOT ?",
        (object_id, exclude_id)
    ).fetchall()

    return [name[0] for name in names]


def insert_parameter():
    pass


def update_parameter():
    pass


def delete_parameter():
    pass


def list_parameters():
    pass


def insert_choice():
    pass


def delete_choice():
    pass


def list_choices():
    pass


def insert_model():
    pass


def get_model():
    pass


def list_models():
    pass


def update_model():
    pass


def delete_model():
    pass


def set_build_status():
    pass


def insert_model_geometry():
    pass


def list_model_geometries():
    pass


def insert_parameter_value():
    pass


def update_parameter_value():
    pass


def list_parameter_values():
    pass
