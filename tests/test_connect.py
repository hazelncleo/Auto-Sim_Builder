import sqlite3

import pytest

from auto_sim_builder.db import (
    SCHEMA_VERSION,
    NotAutosimDatabaseError,
    SchemaVersionError,
    connect,
)

TABLES = {
    "software",
    "objects",
    "object_files",
    "object_software",
    "object_parameters",
    "parameter_choices",
    "models",
    "model_geometries",
    "model_parameter_values",
}


def table_names(connection):
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row[0] for row in rows}


def test_new_database_gets_schema(tmp_path):
    connection = connect(tmp_path / "autosim.db")

    assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert table_names(connection) == TABLES
    connection.close()


def test_reopen_keeps_data(tmp_path):
    path = tmp_path / "autosim.db"
    with connect(path) as connection:
        connection.execute("INSERT INTO software (key) VALUES ('abaqus')")
    connection.close()

    connection = connect(path)
    assert connection.execute("SELECT key FROM software").fetchone()["key"] == "abaqus"
    connection.close()


def test_foreign_keys_enabled(db):
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_rows_are_sqlite_rows(db):
    db.execute("INSERT INTO software (key) VALUES ('abaqus')")
    row = db.execute("SELECT key FROM software").fetchone()

    assert isinstance(row, sqlite3.Row)
    assert row["key"] == "abaqus"


def test_other_programs_database_rejected_and_untouched(tmp_path):
    path = tmp_path / "other.db"
    other = sqlite3.connect(path)
    other.execute("CREATE TABLE notes (text TEXT)")
    other.close()

    with pytest.raises(NotAutosimDatabaseError):
        connect(path)

    other = sqlite3.connect(path)
    assert table_names(other) == {"notes"}
    other.close()


def test_wrong_schema_version_rejected(tmp_path):
    path = tmp_path / "autosim.db"
    connect(path).close()

    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    raw.close()

    with pytest.raises(SchemaVersionError):
        connect(path)
