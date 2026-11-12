"""The schema guard must fail hard (not skip) when isolation is lost."""

import pytest

from tests.db.schema_guard import assert_test_schema


class FakeConn:
    def __init__(self, schema):
        self.schema = schema

    def execute(self, sql):
        assert sql == "SELECT current_schema()"
        return self

    def fetchone(self):
        return {"current_schema": self.schema}


def test_guard_accepts_the_test_schema():
    assert_test_schema(FakeConn("test_abc"), "test_abc")


@pytest.mark.parametrize("schema", ["public", None, "test_other"])
def test_guard_raises_when_search_path_was_dropped(schema):
    with pytest.raises(RuntimeError, match="unpooled"):
        assert_test_schema(FakeConn(schema), "test_abc")
