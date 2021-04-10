from dataclasses import dataclass
from typing import Dict, List, Optional

import desert
import yaml



def get_validated_configs():
    """Return a validated instance of the PlotmanConfig dataclass with data from config.yaml."""
    config_path = "config.yaml"
    schema = desert.schema(PlotmanConfig)
    with open(config_path, "r") as file:
        config_file = yaml.load(file, Loader=yaml.SafeLoader)
        return schema.load(config_file)

# Data models used to deserializing/formatting config.yaml files.

@dataclass
class Archive:
    rsyncd_module: str
    rsyncd_path: str
    rsyncd_bwlimit: int
    rsyncd_host: str
    rsyncd_user: str
    index: Optional[int] = 0  # If not explicit, "index" will default to 0

@dataclass
class Directories:
    log: str
    tmp: List[str]
    dst: List[str]
    tmp2: Optional[str] = None
    tmp_overrides: Optional[Dict[str, Dict[str, int]]] = None
    archive: Optional[Archive] = None

@dataclass
class Scheduling:
    global_max_jobs: int
    global_stagger_m: int
    polling_time_s: int
    tmpdir_max_jobs: int
    tmpdir_stagger_phase_major: int
    tmpdir_stagger_phase_minor: int
    tmpdir_stagger_phase_limit: Optional[int] = 1  # If not explicit, "tmpdir_stagger_phase_limit" will default to 1

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
