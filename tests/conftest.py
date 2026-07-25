import pytest

from finops.storage import db


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "test.db")
    db.init_db(path)
    connection = db.get_connection(path)
    yield connection
    connection.close()
