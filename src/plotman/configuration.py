import contextlib
import importlib
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

from plotman import resources as plotman_resources


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

    # TODO: get this IO out
    preset_target_definitions_text = importlib.resources.read_text(
        plotman_resources, "target_definitions.yaml",
    )
    preset_target_objects = yaml.safe_load(preset_target_definitions_text)
    preset_target_schema = desert.schema(PresetTargetDefinitions)
    preset_target_definitions = preset_target_schema.load(preset_target_objects)

    loaded.archiving.target_definitions = {
        **preset_target_definitions.target_definitions,
        **loaded.archiving.target_definitions,
    }

    return loaded


# Data models used to deserializing/formatting plotman.yaml files.

# TODO: bah, mutable?  bah.
@attr.mutable
class ArchivingTarget:
    transfer_process_name: str
    transfer_process_argument_prefix: str
    # TODO: mutable attribute...
    env: Dict[str, Optional[str]] = attr.ib(factory=dict)
    disk_space_path: Optional[str] = None
    disk_space_script: Optional[str] = None
    transfer_path: Optional[str] = None
    transfer_script: Optional[str] = None

# local_rsync_archiving_target = ArchivingTarget(
#     transfer_process_name='{site_root}',
#     transfer_process_argument_prefix='{command}',
#     env={
#         'command': 'rsync',
#         'options': '--preallocate --remove-source-files --skip-compress plot --whole-file',
#         'site_root': None,
#     },
#     disk_space_script=textwrap.dedent('''\
#         #!/bin/bash
#         df -BK | grep " ${site_root}/" | awk '{ gsub(/K$/,"",$4); print $6 ":" $4*1024 }'
#     '''),
#     transfer_script=textwrap.dedent('''\
#
#     ''')
# )

@attr.frozen
class PresetTargetDefinitions:
    target_definitions: Dict[str, ArchivingTarget] = attr.ib(factory=dict)

# TODO: bah, mutable?  bah.
@attr.mutable
class Archiving:
    target: str
    # TODO: mutable attribute...
    env: Dict[str, str]
    index: int = 0  # If not explicit, "index" will default to 0
    target_definitions: Dict[str, ArchivingTarget] = attr.ib(factory=dict)

    def target_definition(self):
        return self.target_definitions[self.target]

    def environment(
            self,
            source=None,
            destination=None,
    ):
        target = self.target_definition()
        complete = {**target.env, **self.env}

        missing_mandatory_keys = [
            key
            for key, value in complete.items()
            if value is None
        ]

        if len(missing_mandatory_keys) > 0:
            target = repr(self.target)
            missing = ', '.join(repr(key) for key in missing_mandatory_keys)
            message = f'Missing env options for archival target {target}: {missing}'
            raise Exception(message)

        variables = {**os.environ, **complete}
        complete['process_name'] = target.transfer_process_name.format(**variables)

        if source is not None:
            complete['source'] = source

        if destination is not None:
            complete['destination'] = destination

        return complete

    def maybe_create_scripts(self, temp):
        rwx = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
        target = self.target_definition()

        if target.disk_space_path is None:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                prefix='plotman-disk-space-script',
                delete=False,
                dir=temp,
            ) as disk_space_script_file:
                disk_space_script_file.write(target.disk_space_script)

            target.disk_space_path = disk_space_script_file.name
            os.chmod(target.disk_space_path, rwx)

        if target.transfer_path is None:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                prefix='plotman-transfer-script',
                delete=False,
                dir=temp,
            ) as transfer_script_file:
                transfer_script_file.write(target.transfer_script)

            target.transfer_path = transfer_script_file.name
            os.chmod(target.transfer_path, rwx)

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
    archiving: Optional[Archiving] = None
    user_interface: UserInterface = attr.ib(factory=UserInterface)
    version: List[int] = [0]

    @contextlib.contextmanager
    def setup(self):
        prefix = f'plotman-pid_{os.getpid()}-'

        with tempfile.TemporaryDirectory(prefix=prefix) as temp:
            if self.archiving is not None:
                self.archiving.maybe_create_scripts(temp=temp)

            yield
