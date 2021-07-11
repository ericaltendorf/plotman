import io
import re
import typing

import attr
import pendulum

import plotman.job
import plotman.plotters


@plotman.plotters.ProtocolChecker[plotman.plotters.SpecificInfo]()
@attr.frozen
class SpecificInfo:
    process_id: typing.Optional[int] = None
    phase: typing.Optional[plotman.job.Phase] = None

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


@plotman.plotters.ProtocolChecker[plotman.plotters.Parser]()
@attr.mutable
class Parser:
    decoder: plotman.plotters.LineDecoder = attr.ib(factory=plotman.plotters.LineDecoder)
    info: SpecificInfo = attr.ib(factory=SpecificInfo)


    def update(self, chunk: bytes) -> None:
        new_lines = self.decoder.update(chunk=chunk)

        matchers: typing.List[
            typing.Callable[[str], typing.Optional[SpecificInfo]]
        ] = [
            ignore_line,
            plot_id,
            # self.plot_start_date,
            # self.plot_size,
            # self.buffer_size,
            # self.buckets,
            # self.threads,
            # self.plot_dirs,
            # self.phase1_duration,
            # self.phase2_duration,
            # self.phase3_duration,
            # self.phase4_duration,
            # self.total_time,
            # self.copy_time,
            # self.filename
        ]

        for line in new_lines:
            for matcher in matchers:
                maybe_info = matcher(line=line, info=self.info)
                if maybe_info is not None:
                    self.info = maybe_info
                    break


def ignore_line(line: str, info: SpecificInfo) -> typing.Optional[SpecificInfo]:
    # Ignore lines starting with Bucket
    # Bucket 0 uniform sort. Ram: 3.250GiB, u_sort min: 0.563GiB, qs min: 0.281GiB.
    m = re.search(r'^\tBucket', line)
    if m:
        return info
    return None

def plot_id(line: str, info: SpecificInfo) -> typing.Optional[SpecificInfo]:
    # ID: 3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24
    m = re.search(r'^ID: (.+)$', line)
    if m:
        return attr.evolve(info, plot_id=m.group(1))
    return None
