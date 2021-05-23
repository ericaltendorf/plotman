import contextlib
import os
import stat
import tempfile
import textwrap
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

    version = config_objects.get('version', (0,))

    expected_major_version = 1

    if version[0] != expected_major_version:
        message = textwrap.dedent(f"""\
            Expected major version {expected_major_version}, found version {version}
                See https://github.com/ericaltendorf/plotman/wiki/Configuration#versions
        """)

        raise Exception(message)

    try:
        loaded = schema.load(config_objects)
    except marshmallow.exceptions.ValidationError as e:
        raise ConfigurationException(
            f"Config file at: '{config_path}' is malformed"
        ) from e

    return loaded


# Data models used to deserializing/formatting plotman.yaml files.

# TODO: bah, mutable?  bah.
@attr.mutable
class Archive:
    transfer_process_name: str
    transfer_process_argument_prefix: str
    index: int = 0  # If not explicit, "index" will default to 0
    # TODO: mutable attribute...
    env: Dict[str, str] = attr.ib(factory=dict)
    disk_space_path: Optional[str] = None
    disk_space_script: Optional[str] = None
    transfer_path: Optional[str] = None
    transfer_script: Optional[str] = None

    def environment(
            self,
            # path=None,
            source=None,
            process_name=None,
            destination=None,
    ):
        complete = dict(self.env)

        variables = {**os.environ, **complete}
        complete['process_name'] = self.transfer_process_name.format(**variables)

        if source is not None:
            complete['source'] = source

        if destination is not None:
            complete['destination'] = destination

        return complete

    def maybe_create_scripts(self):
        rwx = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR

        if self.disk_space_path is None:
            disk_space_script_file = tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                prefix='plotman-disk-space-script',
                # TODO: but cleanup!
                delete=False,
            )
            disk_space_script_file.write(self.disk_space_script)
            disk_space_script_file.flush()
            disk_space_script_file.close()
            self.disk_space_path = disk_space_script_file.name
            os.chmod(self.disk_space_path, rwx)

        if self.transfer_path is None:
            transfer_script_file = tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                prefix='plotman-transfer-script',
                # TODO: but cleanup!
                delete=False,
            )
            transfer_script_file.write(self.transfer_script)
            transfer_script_file.flush()
            transfer_script_file.close()
            self.transfer_path = transfer_script_file.name
            os.chmod(self.transfer_path, rwx)

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
    # archive_mode: str = desert.ib(
    #     default='legacy',
    #     marshmallow_field=marshmallow.fields.String(
    #         validate=marshmallow.validate.OneOf(choices=['legacy', 'custom'])
    #     ),
    # )

    def dst_is_tmp(self):
        return self.dst is None

    def get_dst_directories(self):
        """Returns either <Directories.dst> or <Directories.tmp>. If
        Directories.dst is None, Use Directories.tmp as dst directory.
        """
        if self.dst_is_tmp():
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
    x: bool = False

@attr.frozen
class UserInterface:
    use_stty_size: bool = True

@attr.frozen
class PlotmanConfig:
    directories: Directories
    scheduling: Scheduling
    plotting: Plotting
    user_interface: UserInterface = attr.ib(factory=UserInterface)
    version: List[int] = [0]
