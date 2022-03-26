# mypy: allow_untyped_decorators

import collections
import os.path
import pathlib
import subprocess
import typing

import attr
import click
import pendulum

import plotman.job
import plotman.plotters


@attr.frozen
class Options:
    executable: str = "chia_plot"
    executable_k34: str = "chia_plot_k34"
    k: int = 32
    n_threads: int = 4
    n_buckets: int = 256
    n_buckets3: int = 256
    n_rmulti2: int = 1

    def chosen_executable(self) -> str:
        if self.k > 32:
            return self.executable_k34

        return self.executable


def check_configuration(
    options: Options, pool_contract_address: typing.Optional[str]
) -> None:
    if pool_contract_address is not None:
        completed_process = subprocess.run(
            args=[options.chosen_executable(), "--help"],
            capture_output=True,
            check=True,
            encoding="utf-8",
        )
        if "--contract" not in completed_process.stdout:
            raise Exception(
                f"found madMAx version does not support the `--contract`"
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
        options.chosen_executable(),
        "-k",
        str(options.k),
        "-n",
        str(1),
        "-r",
        str(options.n_threads),
        "-u",
        str(options.n_buckets),
        "-t",
        tmpdir if tmpdir.endswith("/") else (tmpdir + "/"),
        "-d",
        dstdir if dstdir.endswith("/") else (dstdir + "/"),
    ]
    if tmp2dir is not None:
        args.append("-2")
        args.append(tmp2dir if tmp2dir.endswith("/") else (tmp2dir + "/"))
    if options.n_buckets3 is not None:
        args.append("-v")
        args.append(str(options.n_buckets3))
    if options.n_rmulti2 is not None:
        args.append("-K")
        args.append(str(options.n_rmulti2))

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


# @plotman.plotters.ProtocolChecker[plotman.plotters.SpecificInfo]()
@plotman.plotters.check_SpecificInfo
@attr.frozen
class SpecificInfo:
    process_id: typing.Optional[int] = None
    phase: plotman.job.Phase = plotman.job.Phase(known=False)

    started_at: typing.Optional[pendulum.DateTime] = None
    plot_id: str = ""
    p1_buckets: int = 0
    p34_buckets: int = 0
    threads: int = 0
    # buffer: int = 0
    plot_size: int = 0
    tmp_dir: str = ""
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
            type="madmax",
            dstdir=self.dst_dir,
            phase=self.phase,
            tmpdir=self.tmp_dir,
            tmp2dir=self.tmp2_dir,
            started_at=self.started_at,
            plot_id=self.plot_id,
            plot_size=self.plot_size,
            # TODO: handle p34_buckets as well somehow
            buckets=self.p1_buckets,
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
        return "Multi-threaded pipelined Chia" in line

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        if len(command_line) == 0:
            return False

        return os.path.basename(command_line[0]).lower() in {
            "chia_plot",
            "chia_plot_k34",
        }

    def common_info(self) -> plotman.plotters.CommonInfo:
        return self.info.common()

    def parse_command_line(self, command_line: typing.List[str], cwd: str) -> None:
        # drop the chia_plot
        arguments = command_line[1:]

        # TODO: We could at some point do chia version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = commands.latest_command()

        self.parsed_command_line = plotman.plotters.parse_command_line_with_click(
            command=command,
            arguments=arguments,
        )

        for key in ["tmpdir", "tmpdir2", "finaldir"]:
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


@handlers.register(expression=r"^\[P1\] Table ([1-6])")
def phase_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P1] Table 1 took 39.8662 sec
    # [P1] Table 2 took 211.248 sec, found 4294987039 matches
    # [P1] Table 3 took 295.536 sec, found 4295003219 matches
    # [P1] Table 4 took 360.731 sec, found 4295083991 matches
    # [P1] Table 5 took 346.816 sec, found 4295198226 matches
    # [P1] Table 6 took 337.844 sec, found 4295283897 matches
    minor = int(match.group(1)) + 1
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=minor))


@handlers.register(expression=r"^\[P2\] max_table_size")
def phase_2_start(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P2] max_table_size = 4295422716
    return attr.evolve(info, phase=plotman.job.Phase(major=2, minor=1))


@handlers.register(expression=r"^\[P2\] Table ([2-7]) rewrite")
def phase_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P2] Table 7 scan took 18.4493 sec
    # [P2] Table 7 rewrite took 60.7659 sec, dropped 0 entries (0 %)
    # [P2] Table 6 scan took 82.9818 sec
    # [P2] Table 6 rewrite took 142.287 sec, dropped 581464719 entries (13.5373 %)
    # [P2] Table 5 scan took 122.71 sec
    # [P2] Table 5 rewrite took 205.382 sec, dropped 762140364 entries (17.744 %)
    # [P2] Table 4 scan took 119.723 sec
    # [P2] Table 4 rewrite took 131.374 sec, dropped 828922032 entries (19.2993 %)
    # [P2] Table 3 scan took 87.8078 sec
    # [P2] Table 3 rewrite took 135.269 sec, dropped 855096923 entries (19.9091 %)
    # [P2] Table 2 scan took 103.825 sec
    # [P2] Table 2 rewrite took 159.486 sec, dropped 865588810 entries (20.1532 %)
    minor_in_log = int(match.group(1))
    active_minor = 8 - minor_in_log + 1
    return attr.evolve(info, phase=plotman.job.Phase(major=2, minor=active_minor))


@handlers.register(expression=r"^Phase 2 took (\d+(\.\d+)) sec")
def phase3_0(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 2 took 1344.24 sec
    return attr.evolve(
        info,
        phase=plotman.job.Phase(major=3, minor=0),
        phase2_duration_raw=float(match.group(1)),
    )


@handlers.register(expression=r"^Wrote plot header")
def phase_3_start(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Wrote plot header with 252 bytes
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=1))


@handlers.register(expression=r"^\[P3-2\] Table ([2-6]) took")
def phase_3(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P3-1] Table 2 took 80.1436 sec, wrote 3429403335 right entries
    # [P3-2] Table 2 took 69.0526 sec, wrote 3429403335 left entries, 3429403335 final
    # [P3-1] Table 3 took 104.477 sec, wrote 3439906296 right entries
    # [P3-2] Table 3 took 69.8111 sec, wrote 3439906296 left entries, 3439906296 final
    # [P3-1] Table 4 took 111.704 sec, wrote 3466161959 right entries
    # [P3-2] Table 4 took 68.1434 sec, wrote 3466161959 left entries, 3466161959 final
    # [P3-1] Table 5 took 106.097 sec, wrote 3533057862 right entries
    # [P3-2] Table 5 took 69.3742 sec, wrote 3533057862 left entries, 3533057862 final
    # [P3-1] Table 6 took 105.378 sec, wrote 3713819178 right entries
    # [P3-2] Table 6 took 60.371 sec, wrote 3713819178 left entries, 3713819178 final
    minor = int(match.group(1))
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=minor))


@handlers.register(expression=r"^Phase 3 took (\d+(\.\d+)) sec")
def phase4(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 3 took 1002.89 sec, wrote 21877315926 entries to final plot
    return attr.evolve(
        info,
        phase=plotman.job.Phase(major=4, minor=0),
        phase3_duration_raw=float(match.group(1)),
    )


@handlers.register(expression=r"^\[P4\] Starting")
def phase_4_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P4] Starting to write C1 and C3 tables
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=1))


@handlers.register(expression=r"^\[P4\] Writing C2 table")
def phase_4_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P4] Writing C2 table
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=2))


@handlers.register(expression=r"^Phase 4 took (\d+(\.\d+)) sec")
def phase5(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 4 took 77.9891 sec, final plot size is 108836186159 bytes
    return attr.evolve(
        info,
        phase=plotman.job.Phase(major=5, minor=0),
        phase4_duration_raw=float(match.group(1)),
    )


@handlers.register(expression=r"^Started copy to ")
def phase_5_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Started copy to /farm/yards/902/fake_dst/plot-k32-2021-07-14-21-56-522acbd6308af7e229281352f746449134126482cfabd51d38e0f89745d21698.plot
    return attr.evolve(info, phase=plotman.job.Phase(major=5, minor=1))


@handlers.register(expression=r"^Renamed final plot to ")
def phase_5_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Renamed final plot to /farm/yards/902/fake_dst/plot-k32-2021-07-14-21-56-522acbd6308af7e229281352f746449134126482cfabd51d38e0f89745d21698.plot
    return attr.evolve(info, phase=plotman.job.Phase(major=5, minor=2))


@handlers.register(expression=r"^Final Directory:\s*(.+)")
def dst_dir(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Final Directory: /farm/yards/907/
    return attr.evolve(info, dst_dir=match.group(1))


@handlers.register(expression=r"^Working Directory:\s*(.+)")
def tmp_dir(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Working Directory:   /farm/yards/907/
    return attr.evolve(info, tmp_dir=match.group(1))


@handlers.register(expression=r"^Working Directory 2:\s*(.+)")
def tmp2_dir(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Working Directory 2:   /farm/yards/907/
    return attr.evolve(info, tmp2_dir=match.group(1))


@handlers.register(
    expression=r"^Plot Name: (?P<name>plot-k(?P<size>\d+)-(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-(?P<hour>\d+)-(?P<minute>\d+)-(?P<plot_id>\w+))$"
)
def plot_name_line(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Plot Name: plot-k32-2021-07-11-16-52-3a3872f5a124497a17fb917dfe027802aa1867f8b0a8cbac558ed12aa5b697b2
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
        plot_id=match.group("plot_id"),
        phase=plotman.job.Phase(major=1, minor=1),
    )


@handlers.register(expression=r"^Number of Threads:\s*(\d+)")
def threads(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Number of Threads: 9
    return attr.evolve(info, threads=int(match.group(1)))


@handlers.register(expression=r"^Number of Buckets P1:.*\((\d+)\)")
def p1_buckets(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Number of Buckets P1:    2^8 (256)
    return attr.evolve(info, p1_buckets=int(match.group(1)))


@handlers.register(expression=r"^Number of Buckets P3\+P4:.*\((\d+)\)")
def p34_buckets(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Number of Buckets P3+P4: 2^8 (256)
    return attr.evolve(info, p34_buckets=int(match.group(1)))


@handlers.register(expression=r"^Phase 1 took (\d+(\.\d+)) sec")
def phase1_duration_raw(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 1 took 1851.12 sec
    return attr.evolve(info, phase1_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Total plot creation time was (\d+(\.\d+)) sec")
def total_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Total plot creation time was 4276.32 sec (71.272 min)
    return attr.evolve(info, total_time_raw=float(match.group(1)))


commands = plotman.plotters.core.Commands()


# Madmax Git on 2021-06-19 -> https://github.com/madMAx43v3r/chia-plotter/commit/c8121b987186c42c895b49818e6c13acecc51332
@commands.register(version=(0,))
@click.command()
# https://github.com/madMAx43v3r/chia-plotter/blob/c8121b987186c42c895b49818e6c13acecc51332/LICENSE
# https://github.com/madMAx43v3r/chia-plotter/blob/c8121b987186c42c895b49818e6c13acecc51332/src/chia_plot.cpp#L177-L188
@click.option(
    "-n",
    "--count",
    help="Number of plots to create (default = 1, -1 = infinite)",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-r",
    "--threads",
    help="Number of threads (default = 4)",
    type=int,
    default=4,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets (default = 256)",
    type=int,
    default=256,
    show_default=True,
)
@click.option(
    "-v",
    "--buckets3",
    help="Number of buckets for phase 3+4 (default = buckets)",
    type=int,
    default=256,
)
@click.option(
    "-t",
    "--tmpdir",
    help="Temporary directory, needs ~220 GiB (default = $PWD)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmpdir2",
    help="Temporary directory 2, needs ~110 GiB [RAM] (default = <tmpdir>)",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--finaldir",
    help="Final directory (default = <tmpdir>)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-p", "--poolkey", help="Pool Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-f", "--farmerkey", help="Farmer Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-G", "--tmptoggle", help="Alternate tmpdir/tmpdir2", type=str, default=None
)
def _cli_c8121b987186c42c895b49818e6c13acecc51332() -> None:
    pass


# Madmax Git on 2021-07-12 -> https://github.com/madMAx43v3r/chia-plotter/commit/974d6e5f1440f68c48492122ca33828a98864dfc
@commands.register(version=(1,))
@click.command()
# https://github.com/madMAx43v3r/chia-plotter/blob/974d6e5f1440f68c48492122ca33828a98864dfc/LICENSE
# https://github.com/madMAx43v3r/chia-plotter/blob/974d6e5f1440f68c48492122ca33828a98864dfc/src/chia_plot.cpp#L235-L249
@click.option(
    "-n",
    "--count",
    help="Number of plots to create (default = 1, -1 = infinite)",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-r",
    "--threads",
    help="Number of threads (default = 4)",
    type=int,
    default=4,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets (default = 256)",
    type=int,
    default=256,
    show_default=True,
)
@click.option(
    "-v",
    "--buckets3",
    help="Number of buckets for phase 3+4 (default = buckets)",
    type=int,
    default=256,
)
@click.option(
    "-t",
    "--tmpdir",
    help="Temporary directory, needs ~220 GiB (default = $PWD)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmpdir2",
    help="Temporary directory 2, needs ~110 GiB [RAM] (default = <tmpdir>)",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--finaldir",
    help="Final directory (default = <tmpdir>)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-w",
    "--waitforcopy",
    help="Wait for copy to start next plot",
    type=bool,
    default=False,
    show_default=True,
)
@click.option(
    "-p", "--poolkey", help="Pool Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-c", "--contract", help="Pool Contract Address (62 chars)", type=str, default=None
)
@click.option(
    "-f", "--farmerkey", help="Farmer Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-G", "--tmptoggle", help="Alternate tmpdir/tmpdir2", type=str, default=None
)
@click.option(
    "-K",
    "--rmulti2",
    help="Thread multiplier for P2 (default = 1)",
    type=int,
    default=1,
)
def _cli_974d6e5f1440f68c48492122ca33828a98864dfc() -> None:
    pass


# Madmax Git on 2021-08-22 -> https://github.com/madMAx43v3r/chia-plotter/commit/aaa3214d4abbd49bb99c2ec087e27c765424cd65
@commands.register(version=(2,))
@click.command()
# https://github.com/madMAx43v3r/chia-plotter/blob/aaa3214d4abbd49bb99c2ec087e27c765424cd65/LICENSE
# https://github.com/madMAx43v3r/chia-plotter/blob/aaa3214d4abbd49bb99c2ec087e27c765424cd65/src/chia_plot.cpp#L238-L253
@click.option(
    "-k",
    "--size",
    help="K size (default = 32, k <= 32)",
    type=int,
    default=32,
    show_default=True,
)
@click.option(
    "-n",
    "--count",
    help="Number of plots to create (default = 1, -1 = infinite)",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-r",
    "--threads",
    help="Number of threads (default = 4)",
    type=int,
    default=4,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets (default = 256)",
    type=int,
    default=256,
    show_default=True,
)
@click.option(
    "-v",
    "--buckets3",
    help="Number of buckets for phase 3+4 (default = buckets)",
    type=int,
    default=256,
)
@click.option(
    "-t",
    "--tmpdir",
    help="Temporary directory, needs ~220 GiB (default = $PWD)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmpdir2",
    help="Temporary directory 2, needs ~110 GiB [RAM] (default = <tmpdir>)",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--finaldir",
    help="Final directory (default = <tmpdir>)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-w",
    "--waitforcopy",
    help="Wait for copy to start next plot",
    type=bool,
    default=False,
    show_default=True,
)
@click.option(
    "-p", "--poolkey", help="Pool Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-c", "--contract", help="Pool Contract Address (62 chars)", type=str, default=None
)
@click.option(
    "-f", "--farmerkey", help="Farmer Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-G", "--tmptoggle", help="Alternate tmpdir/tmpdir2", type=str, default=None
)
@click.option(
    "-K",
    "--rmulti2",
    help="Thread multiplier for P2 (default = 1)",
    type=int,
    default=1,
)
def _cli_aaa3214d4abbd49bb99c2ec087e27c765424cd65() -> None:
    pass


# Madmax Git on 2022-03-26 -> https://github.com/madMAx43v3r/chia-plotter/commit/ecec17d25cd547fa4bb64b2eb7455b831c8a2882
@commands.register(version=(3,))
@click.command()
# https://github.com/madMAx43v3r/chia-plotter/blob/ecec17d25cd547fa4bb64b2eb7455b831c8a2882/LICENSE
# https://github.com/madMAx43v3r/chia-plotter/blob/ecec17d25cd547fa4bb64b2eb7455b831c8a2882/src/chia_plot.cpp#L257-L277
@click.option(
    "-k",
    "--size",
    help="K size (default = 32, k <= 34)",
    type=int,
    default=32,
    show_default=True,
)
@click.option(
    "-x",
    "--port",
    help="Network port (default = 8444, chives = 9699, mmx = 11337)",
    type=int,
    default=8444,
    show_default=True,
)
@click.option(
    "-n",
    "--count",
    help="Number of plots to create (default = 1, -1 = infinite)",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-r",
    "--threads",
    help="Number of threads (default = 4)",
    type=int,
    default=4,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets (default = 256)",
    type=int,
    default=256,
    show_default=True,
)
@click.option(
    "-v",
    "--buckets3",
    help="Number of buckets for phase 3+4 (default = buckets)",
    type=int,
    default=256,
)
@click.option(
    "-t",
    "--tmpdir",
    help="Temporary directory, needs ~220 GiB (default = $PWD)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmpdir2",
    help="Temporary directory 2, needs ~110 GiB [RAM] (default = <tmpdir>)",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--finaldir",
    help="Final directory (default = <tmpdir>)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-s",
    "--stagedir",
    help="Stage directory (default = <tmpdir>)",
    type=click.Path(),
    default=None,
    show_default=True,
)
@click.option(
    "-w",
    "--waitforcopy",
    help="Wait for copy to start next plot",
    type=bool,
    default=False,
    show_default=True,
)
@click.option(
    "-p", "--poolkey", help="Pool Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-c", "--contract", help="Pool Contract Address (62 chars)", type=str, default=None
)
@click.option(
    "-f", "--farmerkey", help="Farmer Public Key (48 bytes)", type=str, default=None
)
@click.option(
    "-G", "--tmptoggle", help="Alternate tmpdir/tmpdir2", type=str, default=None
)
@click.option(
    "-D",
    "--directout",
    help="Create plot directly in finaldir (default = false)",
    type=bool,
    default=False,
)
@click.option(
    "-Z",
    "--unique",
    help="Make unique plot (default = false)",
    type=bool,
    default=False,
)
@click.option(
    "-K",
    "--rmulti2",
    help="Thread multiplier for P2 (default = 1)",
    type=int,
    default=1,
)
def _cli_ecec17d25cd547fa4bb64b2eb7455b831c8a2882() -> None:
    pass
