import contextlib
import datetime
import importlib.resources
import locale
import pathlib
import typing

import click
import pendulum
import pytest
import _pytest.fixtures

import plotman.job
import plotman.plotters.chianetwork
import plotman._tests.resources


clean_specific_info = plotman.plotters.chianetwork.SpecificInfo()


@pytest.fixture(name="with_a_locale", params=["C", "en_US.UTF-8", "de_DE.UTF-8"])
def with_a_locale_fixture(request: _pytest.fixtures.SubRequest):
    with set_locale(request.param):
        yield


def test_byte_by_byte_full_load(with_a_locale):
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="chianetwork.plot.log",
    )

    parser = plotman.plotters.chianetwork.Plotter(cwd="/", dstdir="", tmpdir="")

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.chianetwork.SpecificInfo(
        process_id=None,
        phase=plotman.job.Phase(major=5, minor=3),
        started_at=pendulum.datetime(2021, 7, 14, 22, 33, 24, tz=None),
        plot_id="d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4",
        buckets=128,
        threads=4,
        buffer=5000,
        plot_size=32,
        tmp_dir1="/farm/yards/902",
        tmp_dir2="/farm/yards/902/fake_tmp2",
        phase1_duration_raw=8134.66,
        phase2_duration_raw=3304.86,
        phase3_duration_raw=6515.266,
        phase4_duration_raw=425.637,
        total_time_raw=18380.426,
        copy_time_raw=178.438,
        filename="/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot",
    )


@contextlib.contextmanager
def set_locale(name: str) -> typing.Generator[str, None, None]:
    # This is terrible and not thread safe.

    original = locale.setlocale(locale.LC_ALL)

    try:
        yield locale.setlocale(locale.LC_ALL, name)
    finally:
        locale.setlocale(locale.LC_ALL, original)


with set_locale("C"):
    log_file_time = datetime.datetime.strptime(
        "Wed Jul 14 22:33:24 2021", "%a %b  %d %H:%M:%S %Y"
    )


def test_log_phases():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="chianetwork.marked",
    )

    parser = plotman.plotters.chianetwork.Plotter(cwd="/", dstdir="", tmpdir="")

    wrong = []

    for marked_line in read_bytes.splitlines(keepends=True):
        phase_bytes, _, line_bytes = marked_line.partition(b",")
        phases_elements = tuple(int(p) for p in phase_bytes.decode("utf-8").split(":"))
        phase = plotman.job.Phase.from_tuple(t=phases_elements)

        parser.update(chunk=line_bytes)

        if parser.info.phase != phase:
            wrong.append([parser.info.phase, phase, line_bytes.decode("utf-8")])

    assert wrong == []


def test_marked_log_matches():
    marked_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="chianetwork.marked",
    )
    log_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="chianetwork.plot.log",
    )

    for marked_line, log_line in zip(marked_bytes.splitlines(keepends=True), log_bytes.splitlines(keepends=True)):
        _, _, marked_just_line = marked_line.partition(b",")
        assert marked_just_line == log_line
