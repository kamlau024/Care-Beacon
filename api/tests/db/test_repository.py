"""Run the shared repository behaviour suite against Postgres."""

import pytest

from src.chat.repository import ThreadRepository
from tests.repository_contract import *  # noqa: F401,F403


@pytest.fixture
def repo(db):
    # `db` skips the whole module when TEST_DATABASE_URL is unset.
    return ThreadRepository(connect=db)
