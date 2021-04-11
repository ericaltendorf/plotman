"""Tests for plotman/configuration.py"""
import importlib.resources

import marshmallow
import pytest
import yaml

from plotman import configuration
from plotman import resources as plotman_resources


@pytest.fixture(name='config_path')
def config_fixture(tmp_path):
    """Return direct path to plotman.yaml"""
    with importlib.resources.path(plotman_resources, "plotman.yaml") as path:
        return path


def test_get_validated_configs__default(mocker, config_path):
    """Check that get_validated_configs() works with default/example plotman.yaml file."""
    mocker.patch("plotman.configuration.get_path", return_value=config_path)
    res = configuration.get_validated_configs()
    assert isinstance(res, configuration.PlotmanConfig)


def test_get_validated_configs__malformed(mocker, config_path):
    """Check that get_validated_configs() raises exception with invalid plotman.yaml contents."""
    mocker.patch("plotman.configuration.get_path", return_value=config_path)
    with open(configuration.get_path(), "r") as file:
        loaded_yaml = yaml.load(file, Loader=yaml.SafeLoader)

    # Purposefully malform the contents of loaded_yaml by changing tmp from List[str] --> str
    loaded_yaml["directories"]["tmp"] = "/mnt/tmp/00"
    mocker.patch("yaml.load", return_value=loaded_yaml)

    with pytest.raises(marshmallow.exceptions.ValidationError):
        configuration.get_validated_configs()
