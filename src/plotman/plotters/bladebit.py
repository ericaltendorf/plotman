# mypy: allow_untyped_decorators

import collections
import os
import pathlib
import subprocess
import typing

import attr
import click
import packaging.version
import pendulum

import plotman.job
import plotman.plotters


@attr.frozen
class Options:
    executable: str = "bladebit"
    threads: typing.Optional[int] = None
    no_numa: bool = False


def check_configuration(
    options: Options, pool_contract_address: typing.Optional[str]
) -> None:
    if pool_contract_address is not None:
        completed_process = subprocess.run(
            args=[options.executable, "--help"],
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
        if "--pool-contract" not in completed_process.stdout:
            raise Exception(
                f"found BladeBit version does not support the `--pool-contract`"
                f" option for pools."
            )


def create_command_line(
    options: Options,
    tmpdir: str,
    tmp2dir: typing.Optional[str],
    dstdir: str,
    farmer_public_key: typing.Optional[str],
    pool_public_key: typing.Optional[str],
    pool_contract_address: typing.Optional[str],
) -> typing.List[str]:
    args = [
        options.executable,
        "-v",
        "-n",
        "1",
        dstdir,
    ]

    if options.threads is not None:
        args.append("-t")
        args.append(str(options.threads))

    if farmer_public_key is not None:
        args.append("-f")
        args.append(farmer_public_key)
    if pool_public_key is not None:
        args.append("-p")
        args.append(pool_public_key)
    if pool_contract_address is not None:
        args.append("-c")
        args.append(pool_contract_address)

    return args


@plotman.plotters.check_SpecificInfo
@attr.frozen
class SpecificInfo:
    process_id: typing.Optional[int] = None
    phase: plotman.job.Phase = plotman.job.Phase(known=False)

    started_at: typing.Optional[pendulum.DateTime] = None
    plot_id: str = ""
    threads: int = 0
    # buffer: int = 0
    plot_size: int = 0
    dst_dir: str = ""
    phase1_duration_raw: float = 0
    phase2_duration_raw: float = 0
    phase3_duration_raw: float = 0
    phase4_duration_raw: float = 0
    total_time_raw: float = 0
    # copy_time_raw: float = 0
    filename: str = ""
    plot_name: str = ""

    def common(self) -> plotman.plotters.CommonInfo:
        return plotman.plotters.CommonInfo(
            type="madmax",
            dstdir=self.dst_dir,
            phase=self.phase,
            tmpdir="",
            tmp2dir="",
            started_at=self.started_at,
            plot_id=self.plot_id,
            plot_size=self.plot_size,
            buckets=0,
            threads=self.threads,
            phase1_duration_raw=self.phase1_duration_raw,
            phase2_duration_raw=self.phase2_duration_raw,
            phase3_duration_raw=self.phase3_duration_raw,
            phase4_duration_raw=self.phase4_duration_raw,
            total_time_raw=self.total_time_raw,
            filename=self.filename,
        )


@plotman.plotters.check_Plotter
@attr.mutable
class Plotter:
    decoder: plotman.plotters.LineDecoder = attr.ib(
        factory=plotman.plotters.LineDecoder
    )
    info: SpecificInfo = attr.ib(factory=SpecificInfo)
    parsed_command_line: typing.Optional[
        plotman.job.ParsedChiaPlotsCreateCommand
    ] = None

    @classmethod
    def identify_log(cls, line: str) -> bool:
        return "Warm start enabled" in line

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        if len(command_line) == 0:
            return False

        return "bladebit" == os.path.basename(command_line[0]).lower()

    def common_info(self) -> plotman.plotters.CommonInfo:
        return self.info.common()

    def parse_command_line(self, command_line: typing.List[str], cwd: str) -> None:
        # drop the bladebit
        arguments = command_line[1:]

        # TODO: We could at some point do version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = commands.latest_command()

        self.parsed_command_line = plotman.plotters.parse_command_line_with_click(
            command=command,
            arguments=arguments,
        )

        for key in ["out_dir"]:
            original: os.PathLike[str] = self.parsed_command_line.parameters.get(key)  # type: ignore[assignment]
            if original is not None:
                self.parsed_command_line.parameters[key] = pathlib.Path(cwd).joinpath(
                    original
                )

    def update(self, chunk: bytes) -> SpecificInfo:
        new_lines = self.decoder.update(chunk=chunk)

        for line in new_lines:
            if not self.info.phase.known:
                self.info = attr.evolve(
                    self.info, phase=plotman.job.Phase(major=0, minor=0)
                )

            for pattern, handler_functions in handlers.mapping.items():
                match = pattern.search(line)

                if match is None:
                    continue

                for handler_function in handler_functions:
                    self.info = handler_function(match=match, info=self.info)

                break

        return self.info


handlers = plotman.plotters.RegexLineHandlers[SpecificInfo]()


@handlers.register(expression=r"^Running Phase (?P<phase>\d+)")
def running_phase(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Running Phase 1
    major = int(match.group("phase"))
    return attr.evolve(info, phase=plotman.job.Phase(major=major, minor=0))


@handlers.register(
    expression=r"^Finished Phase (?P<phase>\d+) in (?P<duration>[^ ]+) seconds."
)
def phase_finished(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished Phase 1 in 313.98 seconds.
    major = int(match.group("phase"))
    duration = float(match.group("duration"))
    duration_dict = {f"phase{major}_duration_raw": duration}
    return attr.evolve(
        info, phase=plotman.job.Phase(major=major + 1, minor=0), **duration_dict
    )


@handlers.register(expression=r"^Allocating buffers\.$")
def allocating_buffers(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Allocating buffers.
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=1))


@handlers.register(expression=r"^Finished F1 generation in")
def finished_f1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished F1 generation in 6.93 seconds.
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=1))


@handlers.register(expression=r"^Forward propagating to table (?P<table>\d+)")
def forward_propagating(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Forward propagating to table 2...
    minor = int(match.group("table"))
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=minor))


@handlers.register(expression=r"^ *Prunn?ing table (?P<table>\d+)")
def pruning_table(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #   Prunning table 6...
    table = int(match.group("table"))
    minor = 7 - table
    return attr.evolve(info, phase=plotman.job.Phase(major=2, minor=minor))


@handlers.register(expression=r"^ *Compressing tables (?P<table>\d+)")
def compressing_tables(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #   Compressing tables 1 and 2...
    minor = int(match.group("table"))
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=minor))


@handlers.register(expression=r"^ *Writing (?P<tag>(P7|C1|C2|C3))")
def phase_4_writing(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #   Writing P7.
    minors = {"P7": 1, "C1": 2, "C2": 3, "C3": 4}
    tag = match.group("tag")
    minor = minors[tag]
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=minor))


@handlers.register(expression=r"^Generating plot")
def generating_plot(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Generating plot 1 / 1: 1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=2))


@handlers.register(expression=r"^Writing final plot tables to disk$")
def writing_final(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Writing final plot tables to disk
    return attr.evolve(info, phase=plotman.job.Phase(major=5, minor=1))


@handlers.register(expression=r"^Finished plotting in (?P<duration>[^ ]+) seconds")
def total_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished plotting in 582.91 seconds (9.72 minutes).
    duration = float(match.group("duration"))
    return attr.evolve(info, total_time_raw=duration)


@handlers.register(expression=r"^ *Output path *: *(.+)")
def dst_dir(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #  Output path           : /mnt/tmp/01/manual-transfer/
    return attr.evolve(info, dst_dir=match.group(1))


@handlers.register(
    expression=r"^Plot .*/(?P<filename>(?P<name>plot-k(?P<size>\d+)-(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-(?P<hour>\d+)-(?P<minute>\d+)-(?P<plot_id>\w+)).plot) .*"
)
def plot_name_line(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Plot /mnt/tmp/01/manual-transfer/plot-k32-2021-08-29-22-22-1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3.plot finished writing to disk:
    return attr.evolve(
        info,
        plot_size=int(match.group("size")),
        plot_name=match.group("name"),
        started_at=pendulum.datetime(
            year=int(match.group("year")),
            month=int(match.group("month")),
            day=int(match.group("day")),
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            tz=None,
        ),
        filename=match.group("filename"),
        plot_id=match.group("plot_id"),
    )


@handlers.register(expression=r"^ *Thread count *: *(\d+)")
def threads(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #  Thread count          : 88
    return attr.evolve(info, threads=int(match.group(1)))


commands = plotman.plotters.core.Commands()


# BladeBit Git on 2021-08-29 -> https://github.com/harold-b/bladebit/commit/f3fbfff43ce493ec9e02db6f72c3b44f656ef137
@commands.register(version=(0,))
@click.command()
# https://github.com/harold-b/bladebit/blob/f3fbfff43ce493ec9e02db6f72c3b44f656ef137/LICENSE
# https://github.com/harold-b/bladebit/blob/f7cf06fa685c9b1811465ecd47129402bb7548a0/src/main.cpp#L75-L108
@click.option(
    "-t",
    "--threads",
    help=(
        "Maximum number of threads to use."
        "  For best performance, use all available threads (default behavior)."
        "  Values below 2 are not recommended."
    ),
    type=int,
    show_default=True,
)
@click.option(
    "-n",
    "--count",
    help="Number of plots to create. Default = 1.",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-f",
    "--farmer-key",
    help="Farmer public key, specified in hexadecimal format.",
    type=str,
)
@click.option(
    "-p",
    "--pool-key",
    help=(
        "Pool public key, specified in hexadecimal format."
        "  Either a pool public key or a pool contract address must be specified."
    ),
    type=str,
)
@click.option(
    "-c",
    "--pool-contract",
    help=(
        "Pool contract address, specified in hexadecimal format."
        "  Address where the pool reward will be sent to."
        "  Only used if pool public key is not specified."
    ),
    type=str,
)
@click.option(
    "-w",
    "--warm-start",
    help="Touch all pages of buffer allocations before starting to plot.",
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "-i",
    "--plot-id",
    help="Specify a plot id for debugging.",
    type=str,
)
@click.option(
    "-v",
    "--verbose",
    help="Enable verbose output.",
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "-m",
    "--no-numa",
    help=(
        "Disable automatic NUMA aware memory binding."
        "  If you set this parameter in a NUMA system you will likely get degraded performance."
    ),
    is_flag=True,
    type=bool,
    default=False,
)
@click.argument(
    "out_dir",
    # help=(
    #     "Output directory in which to output the plots." "  This directory must exist."
    # ),
    type=click.Path(),
    default=pathlib.Path("."),
    # show_default=True,
)
def _cli_f3fbfff43ce493ec9e02db6f72c3b44f656ef137() -> None:
    pass
