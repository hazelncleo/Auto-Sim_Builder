import sqlite3
from typing import Literal
from auto_sim_builder.core.params import ParameterSpec, ParamType


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


def insert_parameter(
    connection: sqlite3.Connection,
    object_id: int,
    parameter_data: ParameterSpec
) -> int:
    """"""
    
    cursor = connection.execute(
        """
        INSERT INTO object_parameters
            (object_id, name, type, default_value, min_value, max_value, description)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            object_id,
            parameter_data.name,
            parameter_data.type,
            parameter_data.default_value,
            parameter_data.min_value,
            parameter_data.max_value,
            parameter_data.description
        )
    )

    parameter_id = cursor.lastrowid

    connection.executemany(
        "INSERT INTO parameter_choices (parameter_id, value) VALUES (?, ?)",
        [(parameter_id, single_choice) for single_choice in parameter_data.choices]
    )

    return parameter_id


def update_parameter(
    connection: sqlite3.Connection,
    parameter_id: int,
    parameter_data: ParameterSpec
) -> bool:
    """"""

    cursor = connection.execute(
        """
        UPDATE object_parameters
        SET name = ?, type = ?, default_value = ?, min_value = ?, max_value = ?, description = ?
        WHERE id = ?
        """,
        (
            parameter_data.name,
            parameter_data.type,
            parameter_data.default_value,
            parameter_data.min_value,
            parameter_data.max_value,
            parameter_data.description,
            parameter_id
        )
    )

    if cursor.rowcount == 0:
        return False

    connection.execute(
        "DELETE FROM parameter_choices WHERE parameter_id = ?",
        (parameter_id,)
    )

    connection.executemany(
        "INSERT INTO parameter_choices (parameter_id, value) VALUES (?, ?)",
        [(parameter_id, single_choice) for single_choice in parameter_data.choices]
    )

    return True


def delete_parameter(
    connection: sqlite3.Connection,
    parameter_id: int
) -> bool:
    """"""

    cursor = connection.execute(
        "DELETE FROM object_parameters WHERE id = ?",
        (parameter_id,)
    )
    
    return cursor.rowcount > 0


def list_parameters(
    connection: sqlite3.Connection,
    object_id: int
) -> list[tuple[int, ParameterSpec]]:
    
    rows = connection.execute(
        """
        SELECT id, name, type, default_value, min_value, max_value, description
        FROM object_parameters WHERE object_id = ? ORDER BY id
        """,
        (object_id,)
    ).fetchall()

    parameters = []
    for parameter in rows:

        spec = ParameterSpec(
            name          = parameter["name"],
            type          = ParamType(parameter["type"]),
            default_value = parameter["default_value"],
            min_value     = parameter["min_value"],
            max_value     = parameter["max_value"],
            description   = parameter["description"],
            choices       = list_choices(connection, parameter["id"])
        )

        parameters.append((parameter["id"], spec))

    return parameters


def insert_choice(
    connection: sqlite3.Connection,
    parameter_id: int,
    choice: str
) -> None:
    """"""

    connection.execute(
        "INSERT INTO parameter_choices (parameter_id, value) VALUES (?, ?)",
        (parameter_id, choice)
    )


def delete_choice(
    connection: sqlite3.Connection,
    parameter_id: int,
    choice: str
) -> bool:
    """"""

    cursor = connection.execute(
        "DELETE FROM parameter_choices WHERE parameter_id = ? AND value = ?",
        (parameter_id, choice)
    )

    return cursor.rowcount > 0


def list_choices(
    connection: sqlite3.Connection,
    parameter_id: int
) -> tuple[str, ...]:
    """"""
    
    rows = connection.execute(
        "SELECT value FROM parameter_choices WHERE parameter_id = ? ORDER BY rowid",
        (parameter_id,)
    ).fetchall()

    return tuple(choice[0] for choice in rows)


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
