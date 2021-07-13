import importlib.resources
import pathlib
import typing

import click
import pendulum
import pytest

import plotman.job
import plotman.plotters.madmax
import plotman._tests.resources


def test_byte_by_byte_full_load():
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="2021-07-11T16_52_48.637488+00_00.plot.log",
    )

    parser = plotman.plotters.madmax.Plotter()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.madmax.SpecificInfo(
        phase=plotman.job.Phase(major=4, minor=2),
        started_at=pendulum.datetime(2021, 7, 11, 16, 52, 00, tz=None),
        plot_id="3a3872f5a124497a17fb917dfe027802aa1867f8b0a8cbac558ed12aa5b697b2",
        p1_buckets=256,
        p34_buckets=256,
        threads=9,
        plot_size=32,
        tmp_dir="/farm/yards/907/",
        tmp2_dir="/farm/yards/907/",
        dst_dir="/farm/yards/907/",
        phase1_duration_raw=1851.12,
        phase2_duration_raw=1344.24,
        phase3_duration_raw=1002.89,
        phase4_duration_raw=77.9891,
        total_time_raw=4276.32,
        plot_name="plot-k32-2021-07-11-16-52-3a3872f5a124497a17fb917dfe027802aa1867f8b0a8cbac558ed12aa5b697b2",
    )


default_arguments = {
    "count": 1,
    "threads": 4,
    "buckets": 256,
    "buckets3": 256,
    "tmpdir": pathlib.Path("."),
    "tmpdir2": None,
    "finaldir": pathlib.Path("."),
    "poolkey": None,
    "farmerkey": None,
    "contract": None,
    "tmptoggle": None,
}


@pytest.mark.parametrize(
    argnames=["command_line", "correct_parsing"],
    argvalues=[
        [
            ["chia_plot"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={**default_arguments},
            ),
        ],
        [
            ["chia_plot", "-h"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=True,
                parameters={**default_arguments},
            ),
        ],
        [
            ["chia_plot", "--help"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=True,
                parameters={**default_arguments},
            ),
        ],
        [
            ["chia_plot", "--invalid-option"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=click.NoSuchOption("--invalid-option"),
                help=False,
                parameters={},
            ),
        ],
        [
            [
                "chia_plot",
                "--contract",
                "xch123abc",
                "--farmerkey",
                "abc123",
            ],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={
                    **default_arguments,
                    "contract": "xch123abc",
                    "farmerkey": "abc123",
                },
            ),
        ],
    ],
)
def test_plotter_parses_command_line(
    command_line: typing.List[str],
    correct_parsing: plotman.job.ParsedChiaPlotsCreateCommand,
) -> None:
    plotter = plotman.plotters.madmax.Plotter()
    plotter.parse_command_line(command_line=command_line)
    assert plotter.parsed_command_line == correct_parsing
