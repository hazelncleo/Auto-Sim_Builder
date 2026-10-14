# TODO: add_object(db, name, kind) helper that inserts a minimal valid object,
# for the foreign key and cascade tests in test_schema.py.

import pytest

from auto_sim_builder.db import connect


@pytest.fixture
def db():
    """Fresh in-memory database with the schema applied."""
    connection = connect(":memory:")
    yield connection
    connection.close()
