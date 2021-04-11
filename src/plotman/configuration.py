from dataclasses import dataclass
from typing import Dict, List, Optional

import desert
import yaml


def get_path():
    return "src/plotman/resources/plotman.yaml"


def get_validated_configs():
    """Return a validated instance of the PlotmanConfig dataclass with data from plotman.yaml."""
    schema = desert.schema(PlotmanConfig)
    try:
        with open(get_path(), "r") as file:
            config_file = yaml.load(file, Loader=yaml.SafeLoader)
            return schema.load(config_file)
    except FileNotFoundError:
        print("No plotman.yaml file present in current working directory")


# Data models used to deserializing/formatting plotman.yaml files.

@dataclass
class Archive:
    rsyncd_module: str
    rsyncd_path: str
    rsyncd_bwlimit: int
    rsyncd_host: str
    rsyncd_user: str
    index: int = 0  # If not explicit, "index" will default to 0

@dataclass
class TmpOverrides:
    tmpdir_max_jobs: Optional[int] = None

@dataclass
class Directories:
    log: str
    tmp: List[str]
    dst: List[str]
    tmp2: Optional[str] = None
    tmp_overrides: Optional[Dict[str, TmpOverrides]] = None
    archive: Optional[Archive] = None

@dataclass
class Scheduling:
    global_max_jobs: int
    global_stagger_m: int
    polling_time_s: int
    tmpdir_max_jobs: int
    tmpdir_stagger_phase_major: int
    tmpdir_stagger_phase_minor: int
    tmpdir_stagger_phase_limit: int = 1  # If not explicit, "tmpdir_stagger_phase_limit" will default to 1

@dataclass
class Plotting:
    k: int
    e: bool
    n_threads: int
    n_buckets: int
    job_buffer: int
    farmer_pk: Optional[int] = None
    pool_pk: Optional[int] = None

@dataclass
class UserInterface:
    use_stty_size: bool

@dataclass
class PlotmanConfig:
    user_interface: UserInterface
    directories: Directories
    scheduling: Scheduling
    plotting: Plotting
