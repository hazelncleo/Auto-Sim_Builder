import sqlite3
from typing import Literal
from auto_sim_builder.core.specs import ObjectKind, ObjectSpec, ParameterSpec, ParamType


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


def insert_object(
    connection: sqlite3.Connection,
    object_data: ObjectSpec
) -> int:
    """Insert an object's own row, returning the new object's id."""

    cursor = connection.execute(
        """
        INSERT INTO objects (name, description, kind)
        VALUES (?,?,?)
        """,
        (
            object_data.name,
            object_data.description,
            object_data.kind
        )
    )

    return cursor.lastrowid


def get_object(
    connection: sqlite3.Connection,
    object_id: int
) -> tuple[int, ObjectSpec] | None:
    """Return an object's (id, spec) pair, or None if it doesn't exist."""

    row = connection.execute(
        """
        SELECT id, name, description, kind
        FROM objects WHERE id = ?
        """,
        (object_id,)
    ).fetchone()

    if row is None:
        return None

    spec = ObjectSpec(
        name = row["name"],
        kind = ObjectKind(row["kind"]),
        description = row["description"]
    )

    return (object_id, spec)


def list_objects(
    connection: sqlite3.Connection
) -> list[tuple[int, ObjectSpec]]:
    """Return (id, spec) pairs for every object, sorted by name ignoring case."""

    rows = connection.execute(
        """
        SELECT id, name, description, kind
        FROM objects ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    objects = []
    for single_object in rows:

        spec = ObjectSpec(
            name        = single_object["name"],
            description = single_object["description"],
            kind        = ObjectKind(single_object["kind"])
        )

        objects.append((single_object["id"], spec))

    return objects


def update_object(
    connection: sqlite3.Connection,
    object_id: int,
    name: str,
    description: str
) -> bool:
    """Change an object's name and description. Returns False if it didn't exist."""

    cursor = connection.execute(
        """
        UPDATE objects
        SET name = ?, description = ?
        WHERE id = ?
        """,
        (
            name,
            description,
            object_id
        )
    )

    return cursor.rowcount > 0


def delete_object(
    connection: sqlite3.Connection,
    object_id: int
) -> bool:
    """Delete an object (parameters and choices cascade). Returns False if it didn't exist.

    Raises IntegrityError while any model uses it, check models_using_object first.
    """

    cursor = connection.execute(
        "DELETE FROM objects WHERE id = ?",
        (object_id,)
    )
    
    return cursor.rowcount > 0


def models_using_object(
    connection: sqlite3.Connection,
    object_id: int
) -> list[int]:
    """Return the ids of models using an object as their analysis or a geometry, sorted."""
    
    rows = connection.execute(
        """
        SELECT id FROM models WHERE analysis_id = ?
        UNION
        SELECT model_id FROM model_geometries WHERE geometry_id = ?
        ORDER BY 1
        """,
        (object_id, object_id)
    ).fetchall()

    return [model[0] for model in rows]


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
    """Insert a parameter and its choices, returning the new parameter's id."""
    
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
    """Overwrite a parameter and replace its choices with the spec's.

    Returns False, without touching any choices, if the parameter doesn't exist.
    """

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
    """Delete a parameter (its choices cascade). Returns False if it didn't exist."""

    cursor = connection.execute(
        "DELETE FROM object_parameters WHERE id = ?",
        (parameter_id,)
    )
    
    return cursor.rowcount > 0


def list_parameters(
    connection: sqlite3.Connection,
    object_id: int
) -> list[tuple[int, ParameterSpec]]:
    """Return (id, spec) pairs for an object's parameters, in creation order."""
    
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
    """Add a choice to the end of a parameter's choices."""

    connection.execute(
        "INSERT INTO parameter_choices (parameter_id, value) VALUES (?, ?)",
        (parameter_id, choice)
    )


def delete_choice(
    connection: sqlite3.Connection,
    parameter_id: int,
    choice: str
) -> bool:
    """Delete one choice (exact match). Returns False if it didn't exist."""

    cursor = connection.execute(
        "DELETE FROM parameter_choices WHERE parameter_id = ? AND value = ?",
        (parameter_id, choice)
    )

    return cursor.rowcount > 0


def list_choices(
    connection: sqlite3.Connection,
    parameter_id: int
) -> tuple[str, ...]:
    """Return a parameter's choices in the order they were added."""
    
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
