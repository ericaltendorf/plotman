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
        resource="2021-04-04T19_00_47.681088-0400.log",
    )

    parser = plotman.plotters.chianetwork.Plotter()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.chianetwork.SpecificInfo(
        process_id=None,
        phase=plotman.job.Phase(major=0, minor=0, known=False),
        started_at=pendulum.datetime(2021, 4, 4, 19, 0, 50, tz=None),
        plot_id="3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24",
        buckets=128,
        threads=4,
        buffer=4000,
        plot_size=32,
        tmp_dir1="/farm/yards/901",
        tmp_dir2="/farm/yards/901",
        phase1_duration_raw=17571.981,
        phase2_duration_raw=6911.621,
        phase3_duration_raw=14537.188,
        phase4_duration_raw=924.288,
        total_time_raw=39945.08,
        copy_time_raw=501.696,
        filename="/farm/wagons/801/plot-k32-2021-04-04-19-00-3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24.plot",
    )


default_arguments = {
    "size": 32,
    "override_k": False,
    "num": 1,
    "buffer": 3389,
    "num_threads": 2,
    "buckets": 128,
    "alt_fingerprint": None,
    "pool_contract_address": None,
    "farmer_public_key": None,
    "pool_public_key": None,
    "tmp_dir": pathlib.Path("."),
    "tmp2_dir": None,
    "final_dir": pathlib.Path("."),
    "plotid": None,
    "memo": None,
    "nobitfield": False,
    "exclude_final_dir": False,
}


@pytest.mark.parametrize(
    argnames=["command_line", "correct_parsing"],
    argvalues=[
        [
            ["python", "chia", "plots", "create"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={**default_arguments},
            ),
        ],
        [
            # macOS system python
            ["Python", "chia", "plots", "create"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={**default_arguments},
            ),
        ],
        [
            # binary installer
            ["chia", "plots", "create"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={**default_arguments},
            ),
        ],
        [
            ["python", "chia", "plots", "create", "-h"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=True,
                parameters={**default_arguments},
            ),
        ],
        [
            ["python", "chia", "plots", "create", "--help"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=True,
                parameters={**default_arguments},
            ),
        ],
        [
            ["python", "chia", "plots", "create", "--invalid-option"],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=click.NoSuchOption("--invalid-option"),
                help=False,
                parameters={},
            ),
        ],
        [
            [
                "python",
                "chia",
                "plots",
                "create",
                "--pool_contract_address",
                "xch123abc",
                "--farmer_public_key",
                "abc123",
            ],
            plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={
                    **default_arguments,
                    "pool_contract_address": "xch123abc",
                    "farmer_public_key": "abc123",
                },
            ),
        ],
    ],
)
def test_plotter_parses_command_line(
    command_line: typing.List[str],
    correct_parsing: plotman.job.ParsedChiaPlotsCreateCommand,
) -> None:
    plotter = plotman.plotters.chianetwork.Plotter()
    plotter.parse_command_line(command_line=command_line)
    assert plotter.parsed_command_line == correct_parsing
