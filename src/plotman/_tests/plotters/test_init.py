import importlib.resources
import pathlib
import typing

import attr
import click
import pytest
import _pytest

import plotman.errors
import plotman.job
import plotman.plotters
import plotman.plotters.bladebit
import plotman.plotters.bladebit2disk
import plotman.plotters.chianetwork
import plotman.plotters.madmax
import plotman._tests.resources


@pytest.fixture(name="line_decoder")
def line_decoder_fixture() -> typing.Iterator[plotman.plotters.LineDecoder]:
    decoder = plotman.plotters.LineDecoder()
    yield decoder
    # assert decoder.buffer == ""


def test_decoder_single_chunk(line_decoder: plotman.plotters.LineDecoder) -> None:
    lines = line_decoder.update(b"abc\n123\n\xc3\xa4\xc3\xab\xc3\xaf\n")

    assert lines == ["abc", "123", "äëï"]


def test_decoder_individual_byte_chunks(
    line_decoder: plotman.plotters.LineDecoder,
) -> None:
    lines = []
    for byte in b"abc\n123\n\xc3\xa4\xc3\xab\xc3\xaf\n":
        lines.extend(line_decoder.update(bytes([byte])))

    assert lines == ["abc", "123", "äëï"]


def test_decoder_partial_line_with_final(
    line_decoder: plotman.plotters.LineDecoder,
) -> None:
    lines = []
    lines.extend(line_decoder.update(b"abc\n123\n\xc3\xa4\xc3\xab"))
    lines.extend(line_decoder.update(b"\xc3\xaf", final=True))

    assert lines == ["abc", "123", "äëï"]


def test_decoder_partial_line_without_final(
    line_decoder: plotman.plotters.LineDecoder,
) -> None:
    lines = []
    lines.extend(line_decoder.update(b"abc\n123\n\xc3\xa4\xc3\xab"))
    lines.extend(line_decoder.update(b"\xc3\xaf"))

    assert lines == ["abc", "123"]


@pytest.mark.parametrize(
    argnames=["resource_name", "correct_plotter"],
    argvalues=[
        ["chianetwork.plot.log", plotman.plotters.chianetwork.Plotter],
        ["madmax.plot.log", plotman.plotters.madmax.Plotter],
    ],
)
def test_plotter_identifies_log(
    resource_name: str,
    correct_plotter: typing.Type[plotman.plotters.Plotter],
) -> None:
    with importlib.resources.open_text(
        package=plotman._tests.resources,
        resource=resource_name,
        encoding="utf-8",
    ) as f:
        plotter = plotman.plotters.get_plotter_from_log(lines=f)

    assert plotter == correct_plotter


def test_plotter_not_identified() -> None:
    with pytest.raises(plotman.errors.UnableToIdentifyPlotterFromLogError):
        plotman.plotters.get_plotter_from_log(lines=["a", "b"])


@attr.frozen
class CommandLineExample:
    line: typing.List[str]
    plotter: typing.Optional[typing.Type[plotman.plotters.Plotter]]
    parsed: typing.Optional[plotman.job.ParsedChiaPlotsCreateCommand] = None
    cwd: str = ""


default_bladebit_arguments = dict(
    sorted(
        {
            "threads": None,
            "count": 1,
            "farmer_key": None,
            "pool_key": None,
            "pool_contract": None,
            "warm_start": False,
            "plot_id": None,
            "memo": None,
            "show_memo": False,
            "verbose": False,
            "no_numa": False,
            "no_cpu_affinity": False,
            "out_dir": pathlib.PosixPath("."),
        }.items()
    )
)


default_bladebit2disk_arguments = dict(
    sorted(
        {
            # general
            "threads": None,
            "count": 1,
            "farmer_key": None,
            "pool_contract": None,
            "pool_key": None,
            "warm_start": False,
            "plot_id": None,
            "memo": None,
            "show_memo": False,
            "verbose": False,
            "no_numa": False,
            "no_cpu_affinity": False,
            "memory": False,
            "memory_json": False,
            "version": False,
        }.items()
    )
)


default_bladebit2disk_subcommand_arguments = dict(
    sorted(
        {
            # diskplot
            "buckets": 256,
            "temp1": None,
            "temp2": None,
            "no_t1_direct": False,
            "no_t2_direct": False,
            "sizes": False,
            "cache": None,
            "f1_threads": None,
            "fp_threads": None,
            "c_threads": None,
            "p2_threads": None,
            "p3_threads": None,
            # TODO: is this really the default
            "out_dir": pathlib.Path("."),
        }.items()
    )
)


default_chia_network_arguments = dict(
    sorted(
        {
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
            "tmp_dir": ".",
            "tmp2_dir": None,
            "final_dir": ".",
            "plotid": None,
            "memo": None,
            "nobitfield": False,
            "exclude_final_dir": False,
        }.items()
    )
)


default_madmax_arguments = dict(
    sorted(
        {
            "size": 32,
            "port": 8444,
            "count": 1,
            "threads": 4,
            "buckets": 256,
            "buckets3": 256,
            "tmpdir": pathlib.PosixPath("."),
            "tmpdir2": None,
            "finaldir": pathlib.PosixPath("."),
            "stagedir": None,
            "waitforcopy": False,
            "poolkey": None,
            "contract": None,
            "farmerkey": None,
            "tmptoggle": None,
            "directout": False,
            "unique": False,
            "rmulti2": 1,
        }.items()
    )
)


bladebit_command_line_examples: typing.List[CommandLineExample] = [
    CommandLineExample(
        line=["bladebit"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_bladebit_arguments},
        ),
    ),
    CommandLineExample(
        line=["bladebit", "-h"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_bladebit_arguments},
        ),
    ),
    CommandLineExample(
        line=["bladebit", "--help"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_bladebit_arguments},
        ),
    ),
    CommandLineExample(
        line=["bladebit", "--invalid-option"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=click.NoSuchOption("--invalid-option"),
            help=False,
            parameters={},
        ),
    ),
    CommandLineExample(
        line=["bladebit", "--pool-contract", "xch123abc", "--farmer-key", "abc123"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit_arguments,
                "pool_contract": "xch123abc",
                "farmer_key": "abc123",
            },
        ),
    ),
    CommandLineExample(
        line=["here/there/bladebit"],
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_bladebit_arguments},
        ),
    ),
    CommandLineExample(
        line=[
            "bladebit",
            "final/dir",
        ],
        cwd="/cwd",
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit_arguments,
                "out_dir": pathlib.Path("/", "cwd", "final", "dir"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.bladebit.create_command_line(
            options=plotman.plotters.bladebit.Options(),
            tmpdir="",
            tmp2dir=None,
            dstdir="/farm/dst/dir",
            farmer_public_key=None,
            pool_public_key=None,
            pool_contract_address=None,
        ),
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit_arguments,
                "verbose": True,
                "out_dir": pathlib.Path("/farm/dst/dir"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.bladebit.create_command_line(
            options=plotman.plotters.bladebit.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir="/farm/tmp2/dir",
            dstdir="/farm/dst/dir",
            farmer_public_key="farmerpublickey",
            pool_public_key="poolpublickey",
            pool_contract_address="poolcontractaddress",
        ),
        plotter=plotman.plotters.bladebit.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit_arguments,
                "farmer_key": "farmerpublickey",
                "pool_key": "poolpublickey",
                "pool_contract": "poolcontractaddress",
                "verbose": True,
                "out_dir": pathlib.Path("/farm/dst/dir"),
            },
        ),
    ),
]


bladebit2disk_command_line_examples: typing.List[CommandLineExample] = [
    CommandLineExample(
        line=["bladebit", "diskplot", "an_output_directory/"],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit2disk_arguments,
            },
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
                "out_dir": pathlib.Path("an_output_directory"),
            },
        ),
    ),
    CommandLineExample(
        line=["bladebit", "diskplot", "-h"],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_bladebit2disk_arguments},
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
            },
        ),
    ),
    CommandLineExample(
        line=["bladebit", "diskplot", "--help"],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_bladebit2disk_arguments},
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
            },
        ),
    ),
    CommandLineExample(
        line=["bladebit", "diskplot", "--invalid-option"],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=click.NoSuchOption("--invalid-option"),
            help=False,
            parameters={**default_bladebit2disk_arguments},
            subcommand_name="diskplot",
            subparameters={},
        ),
    ),
    CommandLineExample(
        line=[
            "bladebit",
            "--pool-contract",
            "xch123abc",
            "--farmer-key",
            "abc123",
            "diskplot",
        ],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit2disk_arguments,
                "pool_contract": "xch123abc",
                "farmer_key": "abc123",
            },
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
            },
        ),
    ),
    CommandLineExample(
        line=["here/there/bladebit", "diskplot"],
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_bladebit2disk_arguments},
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
            },
        ),
    ),
    CommandLineExample(
        line=["bladebit", "diskplot", "final/dir"],
        cwd="/cwd",
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit2disk_arguments,
            },
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
                "out_dir": pathlib.Path("/", "cwd", "final", "dir"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.bladebit2disk.create_command_line(
            options=plotman.plotters.bladebit2disk.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir=None,
            dstdir="/farm/dst/dir",
            farmer_public_key=None,
            pool_public_key=None,
            pool_contract_address=None,
        ),
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit2disk_arguments,
                "verbose": True,
            },
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
                "temp1": pathlib.Path("/farm/tmp/dir"),
                "out_dir": pathlib.Path("/farm/dst/dir"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.bladebit2disk.create_command_line(
            options=plotman.plotters.bladebit2disk.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir="/farm/tmp2/dir",
            dstdir="/farm/dst/dir",
            farmer_public_key="farmerpublickey",
            pool_public_key="poolpublickey",
            pool_contract_address="poolcontractaddress",
        ),
        plotter=plotman.plotters.bladebit2disk.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_bladebit2disk_arguments,
                "farmer_key": "farmerpublickey",
                "pool_key": "poolpublickey",
                "pool_contract": "poolcontractaddress",
                "verbose": True,
            },
            subcommand_name="diskplot",
            subparameters={
                **default_bladebit2disk_subcommand_arguments,
                "temp1": pathlib.Path("/farm/tmp/dir"),
                "temp2": pathlib.Path("/farm/tmp2/dir"),
                "out_dir": pathlib.Path("/farm/dst/dir"),
            },
        ),
    ),
]


chianetwork_command_line_examples: typing.List[CommandLineExample] = [
    CommandLineExample(
        line=["python", "chia", "plots", "create"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "-k", "32"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments, "size": 32},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "-k32"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments, "size": 32},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "--size", "32"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments, "size": 32},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "--size=32"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments, "size": 32},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "--size32"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=click.NoSuchOption("--size32"),
            help=False,
            parameters={},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "-h"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_chia_network_arguments},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "--help"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_chia_network_arguments},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "-k", "32", "--help"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_chia_network_arguments},
        ),
    ),
    CommandLineExample(
        line=["python", "chia", "plots", "create", "--invalid-option"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=click.NoSuchOption("--invalid-option"),
            help=False,
            parameters={},
        ),
    ),
    CommandLineExample(
        line=[
            "python",
            "chia",
            "plots",
            "create",
            "--pool_contract_address",
            "xch123abc",
            "--farmer_public_key",
            "abc123",
        ],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_chia_network_arguments,
                "pool_contract_address": "xch123abc",
                "farmer_public_key": "abc123",
            },
        ),
    ),
    # macOS system python
    CommandLineExample(
        line=["Python", "chia", "plots", "create"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_chia_network_arguments},
        ),
    ),
    # binary installer
    CommandLineExample(
        line=["chia", "plots", "create", "--final_dir", "/blue/red"],
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_chia_network_arguments,
                "final_dir": "/blue/red",
            },
        ),
    ),
    CommandLineExample(
        line=[
            "python",
            "chia",
            "plots",
            "create",
            "--final_dir",
            "final/dir",
            "--tmp_dir",
            "tmp/dir",
            "--tmp2_dir",
            "tmp2/dir",
        ],
        cwd="/cwd",
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_chia_network_arguments,
                "final_dir": "/cwd/final/dir",
                "tmp_dir": "/cwd/tmp/dir",
                "tmp2_dir": "/cwd/tmp2/dir",
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.chianetwork.create_command_line(
            options=plotman.plotters.chianetwork.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir=None,
            dstdir="/farm/dst/dir",
            farmer_public_key=None,
            pool_public_key=None,
            pool_contract_address=None,
        ),
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_chia_network_arguments,
                "final_dir": "/farm/dst/dir",
                "tmp_dir": "/farm/tmp/dir",
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.chianetwork.create_command_line(
            options=plotman.plotters.chianetwork.Options(
                e=True,
                x=True,
            ),
            tmpdir="/farm/tmp/dir",
            tmp2dir="/farm/tmp2/dir",
            dstdir="/farm/dst/dir",
            farmer_public_key="farmerpublickey",
            pool_public_key="poolpublickey",
            pool_contract_address="poolcontractaddress",
        ),
        plotter=plotman.plotters.chianetwork.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_chia_network_arguments,
                "exclude_final_dir": True,
                "nobitfield": True,
                "farmer_public_key": "farmerpublickey",
                "pool_public_key": "poolpublickey",
                "pool_contract_address": "poolcontractaddress",
                "final_dir": "/farm/dst/dir",
                "tmp_dir": "/farm/tmp/dir",
                "tmp2_dir": "/farm/tmp2/dir",
            },
        ),
    ),
]


madmax_command_line_examples: typing.List[CommandLineExample] = [
    CommandLineExample(
        line=["chia_plot"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=["chia_plot_k34"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=["chia_plot"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=["chia_plot", "-h"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=["chia_plot", "--help"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=True,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=["chia_plot", "--invalid-option"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=click.NoSuchOption("--invalid-option"),
            help=False,
            parameters={},
        ),
    ),
    CommandLineExample(
        line=["chia_plot", "--contract", "xch123abc", "--farmerkey", "abc123"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_madmax_arguments,
                "contract": "xch123abc",
                "farmerkey": "abc123",
            },
        ),
    ),
    CommandLineExample(
        line=["here/there/chia_plot"],
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={**default_madmax_arguments},
        ),
    ),
    CommandLineExample(
        line=[
            "chia_plot",
            "--finaldir",
            "final/dir",
            "--tmpdir",
            "tmp/dir",
            "--tmpdir2",
            "tmp/dir2",
        ],
        cwd="/cwd",
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_madmax_arguments,
                "finaldir": pathlib.Path("/", "cwd", "final", "dir"),
                "tmpdir": pathlib.Path("/", "cwd", "tmp", "dir"),
                "tmpdir2": pathlib.Path("/", "cwd", "tmp", "dir2"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.madmax.create_command_line(
            options=plotman.plotters.madmax.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir=None,
            dstdir="/farm/dst/dir",
            farmer_public_key=None,
            pool_public_key=None,
            pool_contract_address=None,
        ),
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_madmax_arguments,
                "finaldir": pathlib.Path("/farm/dst/dir"),
                "tmpdir": pathlib.Path("/farm/tmp/dir"),
            },
        ),
    ),
    CommandLineExample(
        line=plotman.plotters.madmax.create_command_line(
            options=plotman.plotters.madmax.Options(),
            tmpdir="/farm/tmp/dir",
            tmp2dir="/farm/tmp2/dir",
            dstdir="/farm/dst/dir",
            farmer_public_key="farmerpublickey",
            pool_public_key="poolpublickey",
            pool_contract_address="poolcontractaddress",
        ),
        plotter=plotman.plotters.madmax.Plotter,
        parsed=plotman.job.ParsedChiaPlotsCreateCommand(
            error=None,
            help=False,
            parameters={
                **default_madmax_arguments,
                "farmerkey": "farmerpublickey",
                "poolkey": "poolpublickey",
                "contract": "poolcontractaddress",
                "finaldir": pathlib.Path("/farm/dst/dir"),
                "tmpdir": pathlib.Path("/farm/tmp/dir"),
                "tmpdir2": pathlib.Path("/farm/tmp2/dir"),
            },
        ),
    ),
    *(
        CommandLineExample(
            line=[executable, "-k", str(k)],
            plotter=plotman.plotters.madmax.Plotter,
            parsed=plotman.job.ParsedChiaPlotsCreateCommand(
                error=None,
                help=False,
                parameters={**default_madmax_arguments, "size": k},
            ),
        )
        for executable in ["chia_plot", "chia_plot_k34"]
        for k in [32, 33, 34]
    ),
]


command_line_examples: typing.List[CommandLineExample] = [
    *bladebit_command_line_examples,
    *bladebit2disk_command_line_examples,
    *chianetwork_command_line_examples,
    *madmax_command_line_examples,
]

not_command_line_examples: typing.List[CommandLineExample] = [
    CommandLineExample(line=["something/else"], plotter=None),
    CommandLineExample(line=["another"], plotter=None),
    CommandLineExample(line=["some/chia/not"], plotter=None),
    CommandLineExample(line=["chia", "other"], plotter=None),
    CommandLineExample(line=["chia_plot/blue"], plotter=None),
    CommandLineExample(line=[], plotter=None, parsed=None),
]


@pytest.fixture(
    name="command_line_example",
    params=command_line_examples,
    ids=lambda param: repr(param.line),
)
def command_line_example_fixture(
    request: _pytest.fixtures.SubRequest,
) -> typing.Iterator[CommandLineExample]:
    return request.param  # type: ignore[no-any-return]


@pytest.fixture(
    name="not_command_line_example",
    params=not_command_line_examples,
    ids=lambda param: repr(param.line),
)
def not_command_line_example_fixture(
    request: _pytest.fixtures.SubRequest,
) -> typing.Iterator[CommandLineExample]:
    return request.param  # type: ignore[no-any-return]


def test_plotter_identifies_command_line(
    command_line_example: CommandLineExample,
) -> None:
    plotter = plotman.plotters.get_plotter_from_command_line(
        command_line=command_line_example.line,
    )

    assert plotter == command_line_example.plotter


def test_plotter_fails_to_identify_command_line(
    not_command_line_example: CommandLineExample,
) -> None:
    with pytest.raises(plotman.plotters.UnableToIdentifyCommandLineError):
        plotman.plotters.get_plotter_from_command_line(
            command_line=not_command_line_example.line,
        )


def test_is_plotting_command_line(command_line_example: CommandLineExample) -> None:
    assert plotman.plotters.is_plotting_command_line(
        command_line=command_line_example.line,
    )


def test_is_not_plotting_command_line(
    not_command_line_example: CommandLineExample,
) -> None:
    assert not plotman.plotters.is_plotting_command_line(
        command_line=not_command_line_example.line,
    )


def test_command_line_parsed_correctly(
    command_line_example: CommandLineExample,
) -> None:
    assert command_line_example.plotter is not None

    plotter = command_line_example.plotter()
    plotter.parse_command_line(
        command_line=command_line_example.line,
        cwd=command_line_example.cwd,
    )
    assert plotter.parsed_command_line == command_line_example.parsed
