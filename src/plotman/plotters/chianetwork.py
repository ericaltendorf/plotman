# mypy: allow_untyped_decorators

import collections
import os
import pathlib
import typing

import attr
import click
import pendulum

import plotman.job
import plotman.plotters


def parse_chia_plot_time(s: str) -> pendulum.DateTime:
    # This will grow to try ISO8601 as well for when Chia logs that way
    # TODO: unignore once fixed upstream
    #       https://github.com/sdispater/pendulum/pull/548
    return pendulum.from_format(s, "ddd MMM DD HH:mm:ss YYYY", locale="en", tz=None)  # type: ignore[arg-type]


@plotman.plotters.check_SpecificInfo
@attr.frozen
class SpecificInfo:
    process_id: typing.Optional[int] = None
    phase: plotman.job.Phase = plotman.job.Phase(known=False)

    started_at: typing.Optional[pendulum.DateTime] = None
    plot_id: str = ""
    buckets: int = 0
    threads: int = 0
    buffer: int = 0
    plot_size: int = 0
    dst_dir: str = ""
    tmp_dir1: str = ""
    tmp_dir2: str = ""
    phase1_duration_raw: float = 0
    phase2_duration_raw: float = 0
    phase3_duration_raw: float = 0
    phase4_duration_raw: float = 0
    total_time_raw: float = 0
    copy_time_raw: float = 0
    filename: str = ""

    def common(self) -> plotman.plotters.CommonInfo:
        return plotman.plotters.CommonInfo(
            type="chia",
            dstdir=self.dst_dir,
            phase=self.phase,
            tmpdir=self.tmp_dir1,
            tmp2dir=self.tmp_dir2,
            completed=self.total_time_raw > 0,
            started_at=self.started_at,
            plot_id=self.plot_id,
            plot_size=self.plot_size,
            buffer=self.buffer,
            buckets=self.buckets,
            threads=self.threads,
            phase1_duration_raw=self.phase1_duration_raw,
            phase2_duration_raw=self.phase2_duration_raw,
            phase3_duration_raw=self.phase3_duration_raw,
            phase4_duration_raw=self.phase4_duration_raw,
            total_time_raw=self.total_time_raw,
            copy_time_raw=self.copy_time_raw,
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
        segments = [
            "chia.plotting.create_plots",
            "src.plotting.create_plots",
        ]
        return any(segment in line for segment in segments)

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        if len(command_line) == 0:
            return False

        if "python" == os.path.basename(command_line[0]).lower():
            command_line = command_line[1:]

        return (
            len(command_line) >= 3
            and "chia" in command_line[0]
            and "plots" == command_line[1]
            and "create" == command_line[2]
        )

    def common_info(self) -> plotman.plotters.CommonInfo:
        return self.info.common()

    def parse_command_line(self, command_line: typing.List[str], cwd: str) -> None:
        if "python" in os.path.basename(command_line[0]).casefold():
            # drop the python
            command_line = command_line[1:]

        # drop the chia plots create
        arguments = command_line[3:]

        # TODO: We could at some point do chia version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = commands.latest_command()

        self.parsed_command_line = plotman.plotters.parse_command_line_with_click(
            command=command,
            arguments=arguments,
        )

        for key in ["tmp_dir", "tmp2_dir", "final_dir"]:
            original: os.PathLike[str] = self.parsed_command_line.parameters.get(key)  # type: ignore[assignment]
            if original is not None:
                self.parsed_command_line.parameters[key] = pathlib.Path(cwd).joinpath(
                    original
                )

                if key == "final_dir":
                    # TODO: yep, this is goofy.  be consistent
                    self.parsed_command_line.parameters[key] = os.fspath(self.parsed_command_line.parameters[key])

        if self.parsed_command_line.error is None and not self.parsed_command_line.help:
            self.info = attr.evolve(
                self.info,
                dst_dir=self.parsed_command_line.parameters["final_dir"],
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


@handlers.register(expression=r"^\tBucket")
def ignore_line(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Ignore lines starting with Bucket
    # Bucket 0 uniform sort. Ram: 3.250GiB, u_sort min: 0.563GiB, qs min: 0.281GiB.
    return info


@handlers.register(expression=r"^ID: (.+)$")
def plot_id(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # ID: 3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24
    return attr.evolve(info, plot_id=match.group(1))


@handlers.register(
    expression=r"^Starting phase (\d+)/4: (Forward Propagation into tmp files\.\.\. (.+))?"
)
def phase_major(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Starting phase 1/4: Forward Propagation into tmp files... Wed Jul 14 22:33:24 2021
    major = int(match.group(1))
    timestamp = match.group(3)

    new_info = attr.evolve(info, phase=plotman.job.Phase(major=major, minor=0))

    if timestamp is None:
        return new_info

    return attr.evolve(
        new_info,
        started_at=parse_chia_plot_time(s=match.group(3)),
    )


@handlers.register(expression=r"^Starting phase (\d+)/")
def phase_2_3_4(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Starting phase 1/4: Forward Propagation into tmp files... Wed Jul 14 22:33:24 2021
    major = int(match.group(1))
    return attr.evolve(info, phase=plotman.job.Phase(major=major, minor=0))


@handlers.register(expression=r"^Computing table (\d+)$")
def subphase_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Computing table 1
    minor = int(match.group(1))
    phase = attr.evolve(info.phase, minor=minor)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^Backpropagating on table (\d+)$")
def subphase_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Backpropagating on table 7
    table = int(match.group(1))
    minor = 8 - table
    phase = attr.evolve(info.phase, minor=minor)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^Compressing tables (\d+) and")
def subphase_3(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Compressing tables 1 and 2
    minor = int(match.group(1))
    phase = attr.evolve(info.phase, minor=minor)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^table 1 new size: ")
def phase2_7(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # table 1 new size: 3425157261
    phase = attr.evolve(info.phase, minor=7)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^\tStarting to write C1 and C3 tables$")
def phase4_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # \tStarting to write C1 and C3 tables
    phase = attr.evolve(info.phase, minor=1)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^\tWriting C2 table$")
def phase4_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # \tWriting C2 table
    phase = attr.evolve(info.phase, minor=2)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^\tFinal table pointers:$")
def phase4_3(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # \tFinal table pointers:
    phase = attr.evolve(info.phase, minor=3)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^Approximate working space used")
def phase5(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Approximate working space used (without final file): 269.297 GiB
    phase = plotman.job.Phase(major=5, minor=0)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r"^Copied final file from ")
def phase5_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Copied final file from "/farm/yards/902/fake_tmp2/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot.2.tmp" to "/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot.2.tmp"
    phase = attr.evolve(info.phase, minor=1)
    return attr.evolve(info, phase=phase)


# @handlers.register(expression=r"^Copy time = (\d+\.\d+) seconds")
# def phase5_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Copy time = 178.438 seconds. CPU (41.390%) Thu Jul 15 03:42:44 2021
#     phase = attr.evolve(info.phase, minor=2)
#     return attr.evolve(info, phase=phase, copy_time_raw=float(match.group(1)))


@handlers.register(expression=r"^Removed temp2 file ")
def phase5_2(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Removed temp2 file "/farm/yards/902/fake_tmp2/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot.2.tmp"? 1
    phase = attr.evolve(info.phase, minor=2)
    return attr.evolve(info, phase=phase)


@handlers.register(expression=r'^Renamed final file from ".+" to "(.+)"')
def phase5_3(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Renamed final file from "/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot.2.tmp" to "/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot"
    phase = attr.evolve(info.phase, minor=3)
    return attr.evolve(info, phase=phase, filename=match.group(1))


@handlers.register(expression=r"^Time for phase 1 = (\d+\.\d+) seconds")
def phase1_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Time for phase 1 = 8134.660 seconds. CPU (194.060%) Thu Jul 15 00:48:59 2021
    return attr.evolve(info, phase1_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Time for phase 2 = (\d+\.\d+) seconds")
def phase2_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Time for phase 2 = 6911.621 seconds. CPU (71.780%) Mon Apr  5 01:48:54 2021
    return attr.evolve(info, phase2_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Time for phase 3 = (\d+\.\d+) seconds")
def phase3_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Time for phase 3 = 14537.188 seconds. CPU (82.730%) Mon Apr  5 05:51:11 2021
    return attr.evolve(info, phase3_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Time for phase 4 = (\d+\.\d+) seconds")
def phase4_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Time for phase 4 = 924.288 seconds. CPU (86.810%) Mon Apr  5 06:06:35 2021
    return attr.evolve(info, phase4_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Total time = (\d+\.\d+) seconds")
def total_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Total time = 39945.080 seconds. CPU (123.100%) Mon Apr  5 06:06:35 2021
    return attr.evolve(info, total_time_raw=float(match.group(1)))


@handlers.register(expression=r"^Copy time = (\d+\.\d+) seconds")
def copy_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Copy time = 501.696 seconds. CPU (23.860%) Sun May  9 22:52:41 2021
    return attr.evolve(info, copy_time_raw=float(match.group(1)))


@handlers.register(
    expression=r"^Starting plotting progress into temporary dirs: (.+) and (.+)$"
)
def plot_dirs(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Starting plotting progress into temporary dirs: /farm/yards/901 and /farm/yards/901
    return attr.evolve(info, tmp_dir1=match.group(1), tmp_dir2=match.group(2))


@handlers.register(expression=r"^Using (\d+) threads of stripe size (\d+)")
def threads(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Using 4 threads of stripe size 65536
    return attr.evolve(info, threads=int(match.group(1)))


@handlers.register(expression=r"^Using (\d+) buckets")
def buckets(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # "^Using (\\d+) buckets"
    return attr.evolve(info, buckets=int(match.group(1)))


@handlers.register(expression=r"^Buffer size is: (\d+)MiB")
def buffer_size(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Buffer size is: 4000MiB
    return attr.evolve(info, buffer=int(match.group(1)))


@handlers.register(expression=r"^Plot size is: (\d+)")
def plot_size(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Plot size is: 32
    return attr.evolve(info, plot_size=int(match.group(1)))


commands = plotman.plotters.core.Commands()


@commands.register(version=(1, 1, 2))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.2/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.2/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=4608,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_2() -> None:
    pass


@commands.register(version=(1, 1, 3))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.3/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.3/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=4608,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_3() -> None:
    pass


@commands.register(version=(1, 1, 4))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.4/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.4/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_4() -> None:
    pass


@commands.register(version=(1, 1, 5))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.5/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.5/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_5() -> None:
    pass


@commands.register(version=(1, 1, 6))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.6/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.6/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_6() -> None:
    pass


@commands.register(version=(1, 1, 7))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.7/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.1.7/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_1_7() -> None:
    pass


@commands.register(version=(1, 2, 0))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.0/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.0/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_2_0() -> None:
    pass


@commands.register(version=(1, 2, 1))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.1/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.1/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_2_1() -> None:
    pass


@commands.register(version=(1, 2, 2))
@click.command()
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.2/LICENSE
# https://github.com/Chia-Network/chia-blockchain/blob/1.2.2/chia/cmds/plots.py#L39-L83
# start copied code
@click.option("-k", "--size", help="Plot size", type=int, default=32, show_default=True)
@click.option(
    "--override-k",
    help="Force size smaller than 32",
    default=False,
    show_default=True,
    is_flag=True,
)
@click.option(
    "-n",
    "--num",
    help="Number of plots or challenges",
    type=int,
    default=1,
    show_default=True,
)
@click.option(
    "-b",
    "--buffer",
    help="Megabytes for sort/plot buffer",
    type=int,
    default=3389,
    show_default=True,
)
@click.option(
    "-r",
    "--num_threads",
    help="Number of threads to use",
    type=int,
    default=2,
    show_default=True,
)
@click.option(
    "-u",
    "--buckets",
    help="Number of buckets",
    type=int,
    default=128,
    show_default=True,
)
@click.option(
    "-a",
    "--alt_fingerprint",
    type=int,
    default=None,
    help="Enter the alternative fingerprint of the key you want to use",
)
@click.option(
    "-c",
    "--pool_contract_address",
    type=str,
    default=None,
    help="Address of where the pool reward will be sent to. Only used if alt_fingerprint and pool public key are None",
)
@click.option(
    "-f", "--farmer_public_key", help="Hex farmer public key", type=str, default=None
)
@click.option(
    "-p", "--pool_public_key", help="Hex public key of pool", type=str, default=None
)
@click.option(
    "-t",
    "--tmp_dir",
    help="Temporary directory for plotting files",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-2",
    "--tmp2_dir",
    help="Second temporary directory for plotting files",
    type=click.Path(),
    default=None,
)
@click.option(
    "-d",
    "--final_dir",
    help="Final directory for plots (relative or absolute)",
    type=click.Path(),
    default=pathlib.Path("."),
    show_default=True,
)
@click.option(
    "-i",
    "--plotid",
    help="PlotID in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-m",
    "--memo",
    help="Memo in hex for reproducing plots (debugging only)",
    type=str,
    default=None,
)
@click.option(
    "-e", "--nobitfield", help="Disable bitfield", default=False, is_flag=True
)
@click.option(
    "-x",
    "--exclude_final_dir",
    help="Skips adding [final dir] to harvester for farming",
    default=False,
    is_flag=True,
)
# end copied code
def _cli_1_2_2() -> None:
    pass
