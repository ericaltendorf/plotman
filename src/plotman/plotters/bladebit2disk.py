# mypy: allow_untyped_decorators

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
class ThreadOptions:
    default: typing.Optional[int] = None
    f1: typing.Optional[int] = None
    fp: typing.Optional[int] = None
    c: typing.Optional[int] = None
    p2: typing.Optional[int] = None
    p3: typing.Optional[int] = None


@attr.frozen
class Options:
    executable: str = "bladebit"
    no_numa: bool = False
    no_cpu_affinity: bool = False
    # TODO: choices
    buckets: int = 256
    no_t1_direct: bool = False
    no_t2_direct: bool = False
    # TODO: is there default?  0?
    cache: typing.Optional[str] = None
    threads: ThreadOptions = ThreadOptions()


def check_configuration(
    options: Options, pool_contract_address: typing.Optional[str]
) -> None:
    completed_process = subprocess.run(
        args=[options.executable, "--version"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    )
    version = packaging.version.Version(completed_process.stdout)
    required_version = packaging.version.Version("2.0")
    if version < required_version:
        raise Exception(
            f"BladeBit version {required_version} required for monitoring logs but"
            f" found: {version}"
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
    ]

    if options.threads is not None:
        if options.threads.default is not None:
            args.append("-t")
            args.append(str(options.threads.default))

    if farmer_public_key is not None:
        args.append("-f")
        args.append(farmer_public_key)
    if pool_public_key is not None:
        args.append("-p")
        args.append(pool_public_key)
    if pool_contract_address is not None:
        args.append("-c")
        args.append(pool_contract_address)
    if options.no_numa:
        args.append("--no-numa")
    if options.no_cpu_affinity:
        args.append("--no-cpu-affinity")

    # TODO: handle all the generic options

    args.append("diskplot")

    # TODO: handle all the specific options

    args.append("-b")
    args.append(str(options.buckets))
    args.append("-t1")
    args.append(os.fspath(tmpdir))
    if tmp2dir is not None:
        args.append("-t2")
        args.append(os.fspath(tmp2dir))
    if options.no_t1_direct:
        args.append("--no-t1-direct")
    if options.no_t1_direct:
        args.append("--no-t2-direct")
    if options.cache is not None:
        args.append("--cache")
        args.append(options.cache)
    if options.threads.f1 is not None:
        args.append("--f1-threads")
        args.append(str(options.threads.f1))
    if options.threads.fp is not None:
        args.append("--fp-threads")
        args.append(str(options.threads.fp))
    if options.threads.c is not None:
        args.append("--c-threads")
        args.append(str(options.threads.c))
    if options.threads.p2 is not None:
        args.append("--p2-threads")
        args.append(str(options.threads.p2))
    if options.threads.p3 is not None:
        args.append("--p3-threads")
        args.append(str(options.threads.p3))

    args.append(dstdir)

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
    plot_size: int = 32
    tmp1_dir: str = ""
    tmp2_dir: str = ""
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
            type="bladebit2disk",
            dstdir=self.dst_dir,
            phase=self.phase,
            tmpdir=self.tmp1_dir,
            tmp2dir=self.tmp2_dir,
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

        return (
            "bladebit" == os.path.basename(command_line[0]).lower()
            and "diskplot" in command_line
        )

    def common_info(self) -> plotman.plotters.CommonInfo:
        return self.info.common()

    def parse_command_line(self, command_line: typing.List[str], cwd: str) -> None:
        # drop the bladebit
        arguments = command_line[1:]

        # TODO: We could at some point do version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = commands.latest_command()

        if not isinstance(command, click.Group):
            raise Exception("bladebit2 command object must be a group")

        self.parsed_command_line = plotman.plotters.parse_command_line_with_click(
            command=command,
            subcommand=command.commands["diskplot"],
            arguments=arguments,
        )

        if self.parsed_command_line.subcommand_name is None:
            return

        for key in ["out_dir", "temp1", "temp2"]:
            original: os.PathLike[str] = self.parsed_command_line.subparameters.get(key)  # type: ignore[assignment]
            if original is not None:
                cwd_path = pathlib.Path(cwd)
                joined = cwd_path.joinpath(original)
                self.parsed_command_line.subparameters[key] = joined

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
    expression=r"^Finished Phase (?P<phase>\d+) in (?P<duration>[^ ]+) seconds"
)
def phase_finished(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished Phase 1 in 313.98 seconds.
    major = int(match.group("phase"))
    duration = float(match.group("duration"))
    duration_dict = {f"phase{major}_duration_raw": duration}
    return attr.evolve(
        info, phase=plotman.job.Phase(major=major + 1, minor=0), **duration_dict
    )


@handlers.register(expression=r"^\s*Allocating memory$")
def allocating_memory(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Allocating buffers.
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=1))


@handlers.register(expression=r"^WARNING: *Forcing warm start for testing\.$")
def forcing_warm_start(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Allocating buffers.
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=2))


@handlers.register(expression=r"^\s*Memory initialized\.$")
def memory_initialized(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Allocating buffers.
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=3))


@handlers.register(expression=r"^Generating plot .*: (?P<plot_id>[^ ]+)")
def generating_plot(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Generating plot 1 / 1: 1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3
    return attr.evolve(
        info,
        phase=plotman.job.Phase(major=0, minor=4),
        plot_id=match.group("plot_id"),
    )


@handlers.register(expression=r"^Started plot\.$")
def started_plot(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Allocating buffers.
    return attr.evolve(info, phase=plotman.job.Phase(major=0, minor=5))


@handlers.register(expression=r"^Finished f1 generation in")
def finished_f1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished F1 generation in 6.93 seconds.
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=1))


@handlers.register(expression=r"^Table (?P<table>\d+)$")
def table(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Table 2
    minor = int(match.group("table"))
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=minor))


@handlers.register(expression=r"^\s+Phase (?P<phase>\d+) Total I/O wait time")
def phase_total_io_wait_time(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    # Phase 1 Total I/O wait time: 0.76
    major = int(match.group("phase"))
    minor = {
        1: 8,
        2: 5,
    }[major]
    return attr.evolve(info, phase=attr.evolve(info.phase, minor=minor))


@handlers.register(expression=r"^Forward propagating to table (?P<table>\d+)")
def forward_propagating(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    assert False
    # Forward propagating to table 2...
    minor = int(match.group("table"))
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=minor))


@handlers.register(
    expression=r"^Table (?P<table>\d+) I/O wait time: (?P<duration>[^ ]+) seconds",
)
def table_io_wait_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Table 6 I/O wait time: 0.00 seconds
    if info.phase.major != 2:
        # while this happens in several phases it only needs to trigger a new minor phase in phase 2
        return info

    table = int(match.group("table"))
    minor = 7 - table
    return attr.evolve(info, phase=attr.evolve(info.phase, minor=minor))


@handlers.register(expression=r"^ *Compressing tables (?P<table>\d+)")
def compressing_tables(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #   Compressing tables 1 and 2...
    minor = int(match.group("table"))
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=minor))


@handlers.register(expression=r"^Finished compressing tables (?P<table>\d+)")
def finished_compressing_tables(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    # Finished compressing tables 1 and 2 in 87.02 seconds.
    minor = int(match.group("table")) + 1
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=minor))


@handlers.register(expression=r"^Writing P7 parks.$")
def phase_4_writing_p7_parks(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    #   Writing P7 parks.
    return attr.evolve(info, phase=attr.evolve(info.phase, minor=7))


@handlers.register(expression=r"^P7 I/O wait time: ")
def phase_4_writing_p7_io_wait(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    # P7 I/O wait time: 1.81 seconds
    return attr.evolve(info, phase=attr.evolve(info.phase, minor=8))


@handlers.register(expression=r"^Waiting for plot file to complete pending writes...$")
def waiting_for_pending_writes(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    # Waiting for plot file to complete pending writes...
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=1))


@handlers.register(
    expression=r"^Completed pending writes in (?P<duration>[^ ]+) seconds.$"
)
def completed_pending_writes(
    match: typing.Match[str],
    info: SpecificInfo,
) -> SpecificInfo:
    # Completed pending writes in 0.00 seconds.
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=2))


@handlers.register(expression=r"^Finished plotting in (?P<duration>[^ ]+) seconds")
def total_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Finished plotting in 582.91 seconds (9.72 minutes).
    duration = float(match.group("duration"))
    return attr.evolve(info, total_time_raw=duration)


@handlers.register(
    expression=r"^Finished writing plot (?P<filename>(?P<name>plot-k(?P<size>\d+)-(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-(?P<hour>\d+)-(?P<minute>\d+)-(?P<plot_id>\w+)).*)\."
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


@handlers.register(expression=r"^ *Temp1 path *: *(.+)")
def temp1_path(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #  Temp1 path     : /farm/yards/907/1
    return attr.evolve(info, tmp1_dir=match.group(1))


@handlers.register(expression=r"^ *Temp2 path *: *(.+)")
def temp2_path(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #  Temp2 path     : /farm/yards/907/2
    return attr.evolve(info, tmp2_dir=match.group(1))


@handlers.register(expression=r"^ *Output path *: *(.+)")
def out_path(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    #  Output path     : /farm/yards/907/d
    return attr.evolve(info, dst_dir=match.group(1))


commands = plotman.plotters.core.Commands()


# BladeBit2 Disk Git (disk-plot branch) on 2022-05-04 -> https://github.com/Chia-Network/bladebit/commit/2d53d324d1910af9c2a3c324bf5e8d238f7541bd
# 2.0.0-alpha1
@commands.register(version=(2, 0, 0, 0, 1))
@click.group()
# https://github.com/Chia-Network/bladebit/blob/2d53d324d1910af9c2a3c324bf5e8d238f7541bd/LICENSE
# https://github.com/Chia-Network/bladebit/blob/2d53d324d1910af9c2a3c324bf5e8d238f7541bd/src/main.cpp#L403-L464
@click.option(
    "-t",
    "--threads",
    help=(
        "Maximum number of threads to use."
        "  By default, this is set to the maximum number of logical cpus present."
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
    help="Farmer public key, specified in hexadecimal format.  *REQUIRED*",
    type=str,
)
@click.option(
    "-c",
    "--pool-contract",
    help=(
        "Pool contract address."
        "  Use this if you are creating pool plots."
        "  *A pool contract address or a pool public key must be specified.*"
    ),
    type=str,
)
@click.option(
    "-p",
    "--pool-key",
    help=(
        "Pool public key, specified in hexadecimal format."
        "  Use this if you are creating OG plots."
        "  Only used if a pool contract address is not specified."
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
    "--memo",
    help="Specify a plot memo for debugging.",
    type=str,
)
@click.option(
    "--show-memo",
    help="Output the memo of the next plot the be plotted.",
    is_flag=True,
    type=bool,
    default=False,
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
@click.option(
    "--no-cpu-affinity",
    help=(
        "Disable assigning automatic thread affinity."
        "  This is useful when running multiple simultaneous instances of bladebit as you can manually assign thread affinity yourself when launching bladebit."
    ),
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "--memory",
    help=(
        "Display system memory available, in bytes, and the required memory to run Bladebit, in bytes."
    ),
    type=bool,
    default=False,
)
@click.option(
    "--memory-json",
    help="Same as --memory, but formats the output as json.",
    type=bool,
    default=False,
)
@click.option(
    "--version",
    help="Display current version.",
    type=bool,
    default=False,
)
def _cli_2d53d324d1910af9c2a3c324bf5e8d238f7541bd() -> None:
    pass


@_cli_2d53d324d1910af9c2a3c324bf5e8d238f7541bd.command(name="diskplot")
# https://github.com/Chia-Network/bladebit/blob/2d53d324d1910af9c2a3c324bf5e8d238f7541bd/src/plotdisk/DiskPlotter.cpp#L498-L560
@click.option(
    "-b",
    "--buckets",
    help=(
        "The number of buckets to use. The default is 256."
        "  You may specify one of: 128, 256, 512, 1024."
    ),
    type=int,
    default=256,
)
@click.option(
    "-t1",
    "--temp1",
    help="The temporary directory to use when plotting.  *REQUIRED*",
    type=click.Path(),
)
@click.option(
    "-t2",
    "--temp2",
    help=(
        "Specify a secondary temporary directory, which will be used for data that needs to be read/written from constantly."
        "  If nothing is specified, --temp will be used instead."
    ),
    type=click.Path(),
)
@click.option(
    "--no-t1-direct",
    help="Disable direct I/O on the temp 1 directory.",
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "--no-t2-direct",
    help="Disable direct I/O on the temp 2 directory.",
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "-s",
    "--sizes",
    help=(
        "Output the memory requirements for a specific bucket count."
        "  To change the bucket count from the default, pass a value to -b before using this argument."
        "  You may also pass a value to --temp and --temp2 to get file system block-aligned values when using direct IO."
    ),
    is_flag=True,
    type=bool,
    default=False,
)
@click.option(
    "--cache",
    help=(
        "Size of cache to reserve for I/O."
        "  This is memory reserved for files that incur frequent I/O."
        "  You need about 192GiB(+|-) for high-frequency I/O Phase 1 calculations to be completely in-memory."
    ),
    type=str,
    # TODO: is there default?  0?
)
@click.option(
    "--f1-threads",
    help="Override the thread count for F1 generation.",
    type=int,
)
@click.option(
    "--fp-threads",
    help="Override the thread count for forward propagation.",
    type=int,
)
@click.option(
    "--c-threads",
    help=(
        "Override the thread count for C table processing."
        "  (Equivalent to Phase 4 in chiapos, but performed at the end of Phase 1.)"
    ),
    type=int,
)
@click.option(
    "--p2-threads",
    help="Override the thread count for Phase 2.",
    type=int,
)
@click.option(
    "--p3-threads",
    help="Override the thread count for Phase 3.",
    type=int,
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
def _cli_diskplot_2d53d324d1910af9c2a3c324bf5e8d238f7541bd() -> None:
    pass


# TODO: do we need to add entries for other subcommands to avoid failure if such processes are found?
