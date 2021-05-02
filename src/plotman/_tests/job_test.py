import contextlib
import datetime
import locale
import importlib.resources

import pytest
from plotman import job
from plotman._tests import resources


class FauxJobWithLogfile:
    # plotman.job.Job does too much in its .__init_() so we have this to let us
    # test its .init_from_logfile().

    def __init__(self, logfile_path):
        self.logfile = logfile_path

    def update_from_logfile(self):
        pass


@pytest.fixture(name='logfile_path')
def logfile_fixture(tmp_path):
    log_name = '2021-04-04T19_00_47.681088-0400.log'
    log_contents = importlib.resources.read_binary(resources, log_name)
    log_file_path = tmp_path.joinpath(log_name)
    log_file_path.write_bytes(log_contents)

    return log_file_path


@contextlib.contextmanager
def set_locale(name):
    # This is terrible and not thread safe.

    original = locale.setlocale(locale.LC_ALL)

    try:
        yield locale.setlocale(locale.LC_ALL, name)
    finally:
        locale.setlocale(locale.LC_ALL, original)

with set_locale('C'):
    log_file_time = datetime.datetime.strptime('Sun Apr  4 19:00:50 2021', '%a %b  %d %H:%M:%S %Y')

@pytest.mark.parametrize(
    argnames=['locale_name'],
    argvalues=[['C'], ['en_US.UTF-8'], ['de_DE.UTF-8']],
)
def test_job_parses_time_with_non_english_locale(logfile_path, locale_name):
    faux_job_with_logfile = FauxJobWithLogfile(logfile_path=logfile_path)

    with set_locale(locale_name):
        job.Job.init_from_logfile(self=faux_job_with_logfile)

    assert faux_job_with_logfile.start_time == log_file_time


@pytest.mark.parametrize(
    argnames=['arguments'],
    argvalues=[
        [['-h']],
        [['--help']],
        [['-k', '32']],
        [['-k32']],
        [['-k', '32', '--help']],
    ],
    ids=str,
)
def test_chia_plots_create_parsing_does_not_fail(arguments):
    job.parse_chia_plots_create_command_line(
        command_line=['python', 'chia', 'plots', 'create', *arguments],
    )


@pytest.mark.parametrize(
    argnames=['arguments'],
    argvalues=[
        [['-h']],
        [['--help']],
        [['-k', '32', '--help']],
    ],
    ids=str,
)
def test_chia_plots_create_parsing_detects_help(arguments):
    parsed = job.parse_chia_plots_create_command_line(
        command_line=['python', 'chia', 'plots', 'create', *arguments],
    )

    assert parsed.help


@pytest.mark.parametrize(
    argnames=['arguments'],
    argvalues=[
        [[]],
        [['-k32']],
        [['-k', '32']],
    ],
    ids=str,
)
def test_chia_plots_create_parsing_detects_not_help(arguments):
    parsed = job.parse_chia_plots_create_command_line(
        command_line=['python', 'chia', 'plots', 'create', *arguments],
    )

    assert not parsed.help


@pytest.mark.parametrize(
    argnames=['arguments'],
    argvalues=[
        [[]],
        [['-k32']],
        [['-k', '32']],
        [['--size', '32']],
    ],
    ids=str,
)
def test_chia_plots_create_parsing_handles_argument_forms(arguments):
    parsed = job.parse_chia_plots_create_command_line(
        command_line=['python', 'chia', 'plots', 'create', *arguments],
    )

    assert parsed.parameters['size'] == 32


@pytest.mark.parametrize(
    argnames=['arguments'],
    argvalues=[
        [['--size32']],
        [['--not-an-actual-option']],
    ],
    ids=str,
)
def test_chia_plots_create_parsing_identifies_errors(arguments):
    parsed = job.parse_chia_plots_create_command_line(
        command_line=['python', 'chia', 'plots', 'create', *arguments],
    )

    assert parsed.error is not None
