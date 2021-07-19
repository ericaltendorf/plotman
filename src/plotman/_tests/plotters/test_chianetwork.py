import importlib.resources
import pathlib
import typing

import click
import pendulum
import pytest

import plotman.job
import plotman.plotters.chianetwork
import plotman._tests.resources


clean_specific_info = plotman.plotters.chianetwork.SpecificInfo()


def test_byte_by_byte_full_load():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="chianetwork.plot.log",
    )

    parser = plotman.plotters.chianetwork.Plotter()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.chianetwork.SpecificInfo(
        process_id=None,
        phase=plotman.job.Phase(major=0, minor=0, known=False),
        started_at=pendulum.datetime(2021, 7, 14, 22, 33, 24, tz=None),
        plot_id='d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4',
        buckets=128,
        threads=4,
        buffer=5000,
        plot_size=32,
        tmp_dir1='/farm/yards/902',
        tmp_dir2='/farm/yards/902/fake_tmp2',
        phase1_duration_raw=8134.66,
        phase2_duration_raw=3304.86,
        phase3_duration_raw=6515.266,
        phase4_duration_raw=425.637,
        total_time_raw=18380.426,
        copy_time_raw=178.438,
        filename='/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot',
    )
