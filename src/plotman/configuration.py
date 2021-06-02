import contextlib
from typing import Dict, List, Optional

import appdirs
import attr
import desert
import marshmallow
import yaml


class ConfigurationException(Exception):
    """Raised when plotman.yaml configuration is missing or malformed."""


def get_path():
    """Return path to where plotman.yaml configuration file should exist."""
    return appdirs.user_config_dir("plotman") + "/plotman.yaml"


def read_configuration_text(config_path):
    try:
        with open(config_path, "r") as file:
            return file.read()
    except FileNotFoundError as e:
        raise ConfigurationException(
            f"No 'plotman.yaml' file exists at expected location: '{config_path}'. To generate "
            f"default config file, run: 'plotman config generate'"
        ) from e


def get_validated_configs(config_text, config_path):
    """Return a validated instance of PlotmanConfig with data from plotman.yaml

    :raises ConfigurationException: Raised when plotman.yaml is either missing or malformed
    """
    schema = desert.schema(PlotmanConfig)
    config_objects = yaml.load(config_text, Loader=yaml.SafeLoader)

    try:
        loaded = schema.load(config_objects)
    except marshmallow.exceptions.ValidationError as e:
        raise ConfigurationException(
            f"Config file at: '{config_path}' is malformed"
        ) from e

    return loaded


# Data models used to deserializing/formatting plotman.yaml files.

@attr.frozen
class Archive:
    rsyncd_module: str
    rsyncd_path: str
    rsyncd_bwlimit: int
    rsyncd_host: str
    rsyncd_user: str
    index: int = 0  # If not explicit, "index" will default to 0

@attr.frozen
class TmpOverrides:
    tmpdir_max_jobs: Optional[int] = None

@attr.frozen
class Directories:
    log: str
    tmp: List[str]
    dst: Optional[List[str]] = None
    tmp2: Optional[str] = None
    tmp_overrides: Optional[Dict[str, TmpOverrides]] = None
    archive: Optional[Archive] = None

    def dst_is_tmp(self):
        return self.dst is None and self.tmp2 is None

    def dst_is_tmp2(self):
        return self.dst is None and self.tmp2 is not None

    def get_dst_directories(self):
        """Returns either <Directories.dst> or <Directories.tmp>. If
        Directories.dst is None, Use Directories.tmp as dst directory.
        """
        if self.dst_is_tmp2():
            return [self.tmp2]
        elif self.dst_is_tmp():
            return self.tmp

        return self.dst


@attr.frozen
class Scheduling:
    global_max_jobs: int
    global_stagger_m: int
    polling_time_s: int
    tmpdir_max_jobs: int
    tmpdir_stagger_phase_major: int
    tmpdir_stagger_phase_minor: int
    tmpdir_stagger_phase_limit: int = 1  # If not explicit, "tmpdir_stagger_phase_limit" will default to 1

@attr.frozen
class Plotting:
    k: int
    e: bool
    n_threads: int
    n_buckets: int
    job_buffer: int
    farmer_pk: Optional[str] = None
    pool_pk: Optional[str] = None
    pool_contract_address: Optional[str] = None
    x: bool = False

@attr.frozen
class UserInterface:
    use_stty_size: bool = True

@attr.frozen
class Interactive:
    autostart_plotting: bool = True

@attr.frozen
class Commands:
    interactive: Interactive = attr.ib(factory=Interactive)

@attr.frozen
class PlotmanConfig:
    directories: Directories
    scheduling: Scheduling
    plotting: Plotting
    commands: Commands = attr.ib(factory=Commands)
    user_interface: UserInterface = attr.ib(factory=UserInterface)
