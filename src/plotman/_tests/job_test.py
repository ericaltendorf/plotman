import contextlib
import datetime
import locale
import importlib.resources
import os
import pathlib
import typing

import pendulum
import pytest
from plotman import job
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


@contextlib.contextmanager
def set_locale(name: str) -> typing.Generator[str, None, None]:
    # This is terrible and not thread safe.

    original = locale.setlocale(locale.LC_ALL)

    try:
        yield locale.setlocale(locale.LC_ALL, name)
    finally:
        locale.setlocale(locale.LC_ALL, original)

with set_locale('C'):
    log_file_time = datetime.datetime.strptime('Wed Jul 14 22:33:24 2021', '%a %b  %d %H:%M:%S %Y')

@pytest.mark.parametrize(
    argnames=['locale_name'],
    argvalues=[['C'], ['en_US.UTF-8'], ['de_DE.UTF-8']],
)
def test_job_parses_time_with_non_english_locale(logfile_path: pathlib.Path, locale_name: str) -> None:
    faux_job_with_logfile = FauxJobWithLogfile(logfile_path=os.fspath(logfile_path))

    with set_locale(locale_name):
        job.Job.init_from_logfile(self=faux_job_with_logfile)  # type: ignore[arg-type]

    assert faux_job_with_logfile.start_time == log_file_time
