import collections
import typing

import attr
import pendulum
import typing_extensions

import plotman.job
import plotman.plotters


@plotman.plotters.ProtocolChecker[plotman.plotters.SpecificInfo]()
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
        return plotman.plotters.CommonInfo(phase=self.phase)


@plotman.plotters.ProtocolChecker[plotman.plotters.Plotter]()
@attr.mutable
class Plotter:
    decoder: plotman.plotters.LineDecoder = attr.ib(factory=plotman.plotters.LineDecoder)
    info: SpecificInfo = attr.ib(factory=SpecificInfo)

    @classmethod
    def identify_log(cls, line: str) -> bool:
        return 'src.plotting.create_plots' in line

    # @classmethod
    # def identify_process(cls, command_line: typing.list[str]) -> bool:
    #     if 'python' not in command_line[0].lower():
    #         return False
    #
    #     command_line = command_line[1:]
    #
    #     return (
    #         len(command_line) >= 3
    #         and 'chia' in command_line[0]
    #         and 'plots' == command_line[1]
    #         and 'create' == command_line[2]
    #     )

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


@handlers.register(expression=r'^\tBucket')
def ignore_line(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Ignore lines starting with Bucket
    # Bucket 0 uniform sort. Ram: 3.250GiB, u_sort min: 0.563GiB, qs min: 0.281GiB.
    return info


@handlers.register(expression=r'^ID: (.+)$')
def plot_id(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # ID: 3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24
    return attr.evolve(info, plot_id=match.group(1))


@handlers.register(expression=r'^Renamed final file from ".+" to "(.+)"')
def filename(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Renamed final file from "/farm/wagons/801/abc.plot.2.tmp" to "/farm/wagons/801/abc.plot"
    return attr.evolve(info, filename=match.group(1))


@handlers.register(expression=r"^Time for phase 1 = (\d+\.\d+) seconds")
def phase1_duration(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Time for phase 1 = 17571.981 seconds. CPU (178.600%) Sun Apr  4 23:53:42 2021
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


@handlers.register(expression=r"^Starting plotting progress into temporary dirs: (.+) and (.+)$")
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


@handlers.register(expression=r'^Plot size is: (\d+)')
def plot_size(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Plot size is: 32
    return attr.evolve(info, plot_size=int(match.group(1)))


@handlers.register(expression=r'^Starting phase 1/4: Forward Propagation into tmp files\.\.\. (.+)')
def plot_start_date(match: typing.Match[str], info: SpecificInfo) -> SpecificInfo:
    # Starting phase 1/4: Forward Propagation into tmp files... Sun May  9 17:36:12 2021
    return attr.evolve(info, started_at=plotman.job.parse_chia_plot_time(s=match.group(1)))
