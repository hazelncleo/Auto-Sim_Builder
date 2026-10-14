import sqlite3
from importlib.resources import files
from os import PathLike

# Must match 'PRAGMA user_version = ...' at end of schema.sql
SCHEMA_VERSION = 1


class NotAutosimDatabaseError(Exception):
    """Database was made by another program."""


class SchemaVersionError(Exception):
    """Database schema version doesn't match SCHEMA_VERSION."""


def connect(path: str | PathLike[str]) -> sqlite3.Connection:
    """Open the database at `path`, creating the tables if it's new."""
    connection = sqlite3.connect(path)

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row

        version = connection.execute("PRAGMA user_version").fetchone()[0]

        if version == 0:
            # Tables but no version: another program's database
            has_tables = connection.execute(
                "SELECT 1 FROM sqlite_master LIMIT 1"
            ).fetchone()
            if has_tables:
                raise NotAutosimDatabaseError(f"{path}: not an autosim database")

            _apply_schema(connection)

        elif version != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"{path}: schema version {version}, expected {SCHEMA_VERSION}"
            )
    except BaseException:
        connection.close()
        raise

    return connection


def _apply_schema(connection: sqlite3.Connection) -> None:
    """Run schema.sql, rolling back if it fails."""
    sql = files("auto_sim_builder.db").joinpath("schema.sql").read_text()

    try:
        connection.executescript(sql)
    except sqlite3.Error:
        connection.rollback()
        raise