"""Tests for plotman/configuration.py"""
from plotman import configuration

def test_default_get_validated_configs():
    """Check that get_validated_configs() works with default/example config.yaml file."""
    res = configuration.get_validated_configs()
    assert isinstance(res, configuration.PlotmanConfig)
