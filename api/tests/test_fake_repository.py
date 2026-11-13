"""Run the shared repository behaviour suite against the in-memory fake."""

import pytest

from tests.fakes import InMemoryThreadRepository
from tests.repository_contract import *  # noqa: F401,F403


@pytest.fixture
def repo():
    return InMemoryThreadRepository()
