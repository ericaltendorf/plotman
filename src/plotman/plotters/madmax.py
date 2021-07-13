import collections
import os.path
import typing

import attr
import pendulum

import plotman.job
import plotman.madmax
import plotman.plotters


@plotman.plotters.ProtocolChecker[plotman.plotters.SpecificInfo]()
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
        return plotman.plotters.CommonInfo(phase=self.phase)


@plotman.plotters.ProtocolChecker[plotman.plotters.Plotter]()
@attr.mutable
class Plotter:
    decoder: plotman.plotters.LineDecoder = attr.ib(factory=plotman.plotters.LineDecoder)
    info: SpecificInfo = attr.ib(factory=SpecificInfo)
    parsed_command_line: typing.Optional[plotman.job.ParsedChiaPlotsCreateCommand] = None

    @classmethod
    def identify_log(cls, line: str) -> bool:
        return 'Multi-threaded pipelined Chia' in line

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        if len(command_line) == 0:
            return False

        return 'chia_plot' == os.path.basename(command_line[0]).lower()

    def parse_command_line(self, command_line: typing.List[str]) -> None:
        # drop the chia_plot
        arguments = command_line[1:]

        # TODO: We could at some point do chia version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = plotman.madmax.commands.latest_command()

        self.parsed_command_line = plotman.plotters.parse_command_line_with_click(
            command=command,
            arguments=arguments,
        )

    def update(self, chunk: bytes) -> SpecificInfo:
        new_lines = self.decoder.update(chunk=chunk)

        for line in new_lines:
            for pattern, handler_functions in handlers.mapping.items():
                match = pattern.search(line)

                if match is None:
                    continue

                for handler_function in handler_functions:
                    self.info = handler_function(match=match, info=self.info)

                break

        return self.info


handlers = plotman.plotters.RegexLineHandlers[SpecificInfo]()


@handlers.register(expression=r'^\[P1\] Table ([1-6])')
def phase_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P1] Table 1 took 39.8662 sec
    # [P1] Table 2 took 211.248 sec, found 4294987039 matches
    # [P1] Table 3 took 295.536 sec, found 4295003219 matches
    # [P1] Table 4 took 360.731 sec, found 4295083991 matches
    # [P1] Table 5 took 346.816 sec, found 4295198226 matches
    # [P1] Table 6 took 337.844 sec, found 4295283897 matches
    minor = int(match.group(1)) + 1
    return attr.evolve(info, phase=plotman.job.Phase(major=1, minor=minor))


@handlers.register(expression=r'^\[P2\] max_table_size')
def phase_2_start(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P2] max_table_size = 4295422716
    return attr.evolve(info, phase=plotman.job.Phase(major=2, minor=1))


@handlers.register(expression=r'^\[P2\] Table ([3-7]) rewrite')
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
    minor_in_log = int(match.group(1))
    active_minor = 8 - minor_in_log + 1
    return attr.evolve(info, phase=plotman.job.Phase(major=2, minor=active_minor))


@handlers.register(expression=r'^Wrote plot header')
def phase_3_start(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Wrote plot header with 252 bytes
    return attr.evolve(info, phase=plotman.job.Phase(major=3, minor=1))


@handlers.register(expression=r'^\[P3-2\] Table ([2-6]) took')
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


@handlers.register(expression=r'^\[P4\] Starting')
def phase_4_1(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P4] Starting to write C1 and C3 tables
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=1))


@handlers.register(expression=r'^\[P4\] Writing C2 table')
def phase_4(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # [P4] Writing C2 table
    return attr.evolve(info, phase=plotman.job.Phase(major=4, minor=2))


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


@handlers.register(expression=r"^Plot Name: (?P<name>plot-k(?P<size>\d+)-(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)-(?P<hour>\d+)-(?P<minute>\d+)-(\w+))$")
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
        plot_id="3a3872f5a124497a17fb917dfe027802aa1867f8b0a8cbac558ed12aa5b697b2",
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


@handlers.register(expression=r"^Phase 2 took (\d+(\.\d+)) sec")
def phase2_duration_raw(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 2 took 1344.24 sec
    return attr.evolve(info, phase2_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Phase 3 took (\d+(\.\d+)) sec")
def phase3_duration_raw(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 3 took 1002.89 sec, wrote 21877315926 entries to final plot
    return attr.evolve(info, phase3_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Phase 4 took (\d+(\.\d+)) sec")
def phase4_duration_raw(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Phase 4 took 77.9891 sec, final plot size is 108836186159 bytes
    return attr.evolve(info, phase4_duration_raw=float(match.group(1)))


@handlers.register(expression=r"^Total plot creation time was (\d+(\.\d+)) sec")
def total_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Total plot creation time was 4276.32 sec (71.272 min)
    return attr.evolve(info, total_time_raw=float(match.group(1)))


# @handlers.register(expression=r"")
# def (match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     return attr.evolve(info, )


# @handlers.register(expression=r'^\tBucket')
# def ignore_line(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Ignore lines starting with Bucket
#     # Bucket 0 uniform sort. Ram: 3.250GiB, u_sort min: 0.563GiB, qs min: 0.281GiB.
#     return info
#
#
# @handlers.register(expression=r'^ID: (.+)$')
# def plot_id(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # ID: 3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24
#     return attr.evolve(info, plot_id=match.group(1))
#
#
# @handlers.register(expression=r'^Renamed final file from ".+" to "(.+)"')
# def filename(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Renamed final file from "/farm/wagons/801/abc.plot.2.tmp" to "/farm/wagons/801/abc.plot"
#     return attr.evolve(info, filename=match.group(1))
#
#
# @handlers.register(expression=r"^Time for phase 1 = (\d+\.\d+) seconds")
# def phase1_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Time for phase 1 = 17571.981 seconds. CPU (178.600%) Sun Apr  4 23:53:42 2021
#     return attr.evolve(info, phase1_duration_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Time for phase 2 = (\d+\.\d+) seconds")
# def phase2_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Time for phase 2 = 6911.621 seconds. CPU (71.780%) Mon Apr  5 01:48:54 2021
#     return attr.evolve(info, phase2_duration_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Time for phase 3 = (\d+\.\d+) seconds")
# def phase3_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Time for phase 3 = 14537.188 seconds. CPU (82.730%) Mon Apr  5 05:51:11 2021
#     return attr.evolve(info, phase3_duration_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Time for phase 4 = (\d+\.\d+) seconds")
# def phase4_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Time for phase 4 = 924.288 seconds. CPU (86.810%) Mon Apr  5 06:06:35 2021
#     return attr.evolve(info, phase4_duration_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Total time = (\d+\.\d+) seconds")
# def total_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Total time = 39945.080 seconds. CPU (123.100%) Mon Apr  5 06:06:35 2021
#     return attr.evolve(info, total_time_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Copy time = (\d+\.\d+) seconds")
# def copy_time(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Copy time = 501.696 seconds. CPU (23.860%) Sun May  9 22:52:41 2021
#     return attr.evolve(info, copy_time_raw=float(match.group(1)))
#
#
# @handlers.register(expression=r"^Starting plotting progress into temporary dirs: (.+) and (.+)$")
# def plot_dirs(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Starting plotting progress into temporary dirs: /farm/yards/901 and /farm/yards/901
#     return attr.evolve(info, tmp_dir1=match.group(1), tmp_dir2=match.group(2))
#
#
# @handlers.register(expression=r"^Using (\d+) threads of stripe size (\d+)")
# def threads(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Using 4 threads of stripe size 65536
#     return attr.evolve(info, threads=int(match.group(1)))
#
#
# @handlers.register(expression=r"^Using (\d+) buckets")
# def buckets(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # "^Using (\\d+) buckets"
#     return attr.evolve(info, buckets=int(match.group(1)))
#
#
# @handlers.register(expression=r"^Buffer size is: (\d+)MiB")
# def buffer_size(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Buffer size is: 4000MiB
#     return attr.evolve(info, buffer=int(match.group(1)))
#
#
# @handlers.register(expression=r'^Plot size is: (\d+)')
# def plot_size(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Plot size is: 32
#     return attr.evolve(info, plot_size=int(match.group(1)))
#
#
# @handlers.register(expression=r'^Starting phase 1/4: Forward Propagation into tmp files\.\.\. (.+)')
# def plot_start_date(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
#     # Starting phase 1/4: Forward Propagation into tmp files... Sun May  9 17:36:12 2021
#     return attr.evolve(info, started_at=plotman.job.parse_chia_plot_time(s=match.group(1)))
