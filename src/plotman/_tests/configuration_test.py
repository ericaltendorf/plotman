"""Tests for plotman/configuration.py"""
import marshmallow
import pytest
import yaml

from plotman import configuration

def test_get_validated_configs__default():
    """Check that get_validated_configs() works with default/example config.yaml file."""
    res = configuration.get_validated_configs()
    assert isinstance(res, configuration.PlotmanConfig)

def test_get_validated_configs__malformed(mocker):
    """Check that get_validated_configs() raises exception with invalid config.yaml contents."""
    with open("config.yaml", "r") as file:
        loaded_yaml = yaml.load(file, Loader=yaml.SafeLoader)

    # Purposefully malform the contents of loaded_yaml by changing tmp from List[str] --> str
    loaded_yaml["directories"]["tmp"] = "/mnt/tmp/00"
    mocker.patch("yaml.load", return_value=loaded_yaml)

    with pytest.raises(marshmallow.exceptions.ValidationError):
        configuration.get_validated_configs()
