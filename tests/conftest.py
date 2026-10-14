import pytest

from auto_sim_builder.db import connect


@pytest.fixture
def db():
    """Fresh in-memory database with the schema applied."""
    connection = connect(":memory:")
    yield connection
    connection.close()
