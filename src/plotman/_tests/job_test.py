import importlib.resources
import pathlib

import pendulum
import pytest
from plotman._tests import resources


class FauxJobWithLogfile:
    # plotman.job.Job does too much in its .__init_() so we have this to let us
    # test its .init_from_logfile().

    start_time: pendulum.DateTime

    def __init__(self, logfile_path: str) -> None:
        self.logfile = logfile_path

    def update_from_logfile(self) -> None:
        pass


@pytest.fixture(name='logfile_path')
def logfile_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    log_name = 'chianetwork.plot.log'
    log_contents = importlib.resources.read_binary(resources, log_name)
    log_file_path = tmp_path.joinpath(log_name)
    log_file_path.write_bytes(log_contents)

    return log_file_path
