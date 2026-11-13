"""Tests for source filter normalization."""

import pytest

from src.api.filters import configured_sources, normalize_sources

SOURCES = ["BC Cancer", "Canadian Cancer Society", "Cleveland Clinic"]


def test_none_and_empty_mean_no_filter():
    assert normalize_sources(None, SOURCES) is None
    assert normalize_sources([], SOURCES) is None


def test_all_sources_means_no_filter():
    assert normalize_sources(list(reversed(SOURCES)), SOURCES) is None


def test_single_source_stays_a_string():
    assert normalize_sources("BC Cancer", SOURCES) == "BC Cancer"
    assert normalize_sources(["BC Cancer"], SOURCES) == "BC Cancer"


def test_two_sources_become_a_deduplicated_list():
    assert normalize_sources(
        ["Cleveland Clinic", "BC Cancer", "BC Cancer"], SOURCES
    ) == ["BC Cancer", "Cleveland Clinic"]


def test_unknown_source_raises():
    with pytest.raises(ValueError, match="Mayo Clinic"):
        normalize_sources(["Mayo Clinic"], SOURCES)


def test_configured_sources_reads_config():
    assert configured_sources() == SOURCES
