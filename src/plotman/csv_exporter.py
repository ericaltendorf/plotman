import csv
import sys
import typing

import attr
import attr._make
import pendulum

from plotman.log_parser import PlotLogParser
import plotman.plotinfo


@attr.frozen
class Row:
    plot_id: str = attr.ib(converter=str, metadata={'name': 'Plot ID'})
    started_at: str = attr.ib(converter=str, metadata={'name': 'Started at'})
    date: str = attr.ib(converter=str, metadata={'name': 'Date'})
    size: str = attr.ib(converter=str, metadata={'name': 'Size'})
    buffer: str = attr.ib(converter=str, metadata={'name': 'Buffer'})
    buckets: str = attr.ib(converter=str, metadata={'name': 'Buckets'})
    threads: str = attr.ib(converter=str, metadata={'name': 'Threads'})
    tmp_dir_1: str = attr.ib(converter=str, metadata={'name': 'Tmp dir 1'})
    tmp_dir_2: str = attr.ib(converter=str, metadata={'name': 'Tmp dir 2'})
    phase_1_duration_raw: str = attr.ib(converter=str, metadata={'name': 'Phase 1 duration (raw)'})
    phase_1_duration: str = attr.ib(converter=str, metadata={'name': 'Phase 1 duration'})
    phase_1_duration_minutes: str = attr.ib(converter=str, metadata={'name': 'Phase 1 duration (minutes)'})
    phase_1_duration_hours: str = attr.ib(converter=str, metadata={'name': 'Phase 1 duration (hours)'})
    phase_2_duration_raw: str = attr.ib(converter=str, metadata={'name': 'Phase 2 duration (raw)'})
    phase_2_duration: str = attr.ib(converter=str, metadata={'name': 'Phase 2 duration'})
    phase_2_duration_minutes: str = attr.ib(converter=str, metadata={'name': 'Phase 2 duration (minutes)'})
    phase_2_duration_hours: str = attr.ib(converter=str, metadata={'name': 'Phase 2 duration (hours)'})
    phase_3_duration_raw: str = attr.ib(converter=str, metadata={'name': 'Phase 3 duration (raw)'})
    phase_3_duration: str = attr.ib(converter=str, metadata={'name': 'Phase 3 duration'})
    phase_3_duration_minutes: str = attr.ib(converter=str, metadata={'name': 'Phase 3 duration (minutes)'})
    phase_3_duration_hours: str = attr.ib(converter=str, metadata={'name': 'Phase 3 duration (hours)'})
    phase_4_duration_raw: str = attr.ib(converter=str, metadata={'name': 'Phase 4 duration (raw)'})
    phase_4_duration: str = attr.ib(converter=str, metadata={'name': 'Phase 4 duration'})
    phase_4_duration_minutes: str = attr.ib(converter=str, metadata={'name': 'Phase 4 duration (minutes)'})
    phase_4_duration_hours: str = attr.ib(converter=str, metadata={'name': 'Phase 4 duration (hours)'})
    total_time_raw: str = attr.ib(converter=str, metadata={'name': 'Total time (raw)'})
    total_time: str = attr.ib(converter=str, metadata={'name': 'Total time'})
    total_time_minutes: str = attr.ib(converter=str, metadata={'name': 'Total time (minutes)'})
    total_time_hours: str = attr.ib(converter=str, metadata={'name': 'Total time (hours)'})
    copy_time_raw: str = attr.ib(converter=str, metadata={'name': 'Copy time (raw)'})
    copy_time: str = attr.ib(converter=str, metadata={'name': 'Copy time'})
    copy_time_minutes: str = attr.ib(converter=str, metadata={'name': 'Copy time (minutes)'})
    copy_time_hours: str = attr.ib(converter=str, metadata={'name': 'Copy time (hours)'})
    filename: str = attr.ib(converter=str, metadata={'name': 'Filename'})

    @classmethod
    def names(cls) -> typing.List[str]:
        return [field.metadata['name'] for field in attr.fields(cls)]

    @classmethod
    def from_info(cls, info: plotman.plotinfo.PlotInfo) -> "Row":
        if info.started_at is None:
            raise Exception(f'Unexpected None start time for file: {info.filename}')

        return cls(
            plot_id=info.plot_id,
            started_at=info.started_at.isoformat(),
            date=info.started_at.date().isoformat(),  # type: ignore[no-untyped-call]
            size=info.plot_size,
            buffer=info.buffer,
            buckets=info.buckets,
            threads=info.threads,
            tmp_dir_1=info.tmp_dir1,
            tmp_dir_2=info.tmp_dir2,
            phase_1_duration_raw=info.phase1_duration_raw,
            phase_1_duration=info.phase1_duration,
            phase_1_duration_minutes=info.phase1_duration_minutes,
            phase_1_duration_hours=info.phase1_duration_hours,
            phase_2_duration_raw=info.phase2_duration_raw,
            phase_2_duration=info.phase2_duration,
            phase_2_duration_minutes=info.phase2_duration_minutes,
            phase_2_duration_hours=info.phase2_duration_hours,
            phase_3_duration_raw=info.phase3_duration_raw,
            phase_3_duration=info.phase3_duration,
            phase_3_duration_minutes=info.phase3_duration_minutes,
            phase_3_duration_hours=info.phase3_duration_hours,
            phase_4_duration_raw=info.phase4_duration_raw,
            phase_4_duration=info.phase4_duration,
            phase_4_duration_minutes=info.phase4_duration_minutes,
            phase_4_duration_hours=info.phase4_duration_hours,
            total_time_raw=info.total_time_raw,
            total_time=info.total_time,
            total_time_minutes=info.total_time_minutes,
            total_time_hours=info.total_time_hours,
            copy_time_raw=info.copy_time_raw,
            copy_time=info.copy_time,
            copy_time_minutes=info.copy_time_minutes,
            copy_time_hours=info.copy_time_hours,
            filename=info.filename,
        )

    def name_dict(self) -> typing.Dict[str, object]:
        return {
            field.metadata['name']: value
            for field, value in zip(attr.fields(type(self)), attr.astuple(self))
        }


def key_on_plot_info_started_at(element: plotman.plotinfo.PlotInfo) -> pendulum.DateTime:
    if element.started_at is None:
        return pendulum.now().add(years=9999)

    return element.started_at


def parse_logs(logfilenames: typing.Sequence[str]) -> typing.List[plotman.plotinfo.PlotInfo]:
    parser = PlotLogParser()
    result = []

    for filename in logfilenames:
        with open(filename) as file:
            info = parser.parse(file)

        if not info.in_progress():
            result.append(info)

    result.sort(key=key_on_plot_info_started_at)

    return result


def generate(logfilenames: typing.List[str], file: typing.TextIO) -> None:
    writer = csv.DictWriter(file, fieldnames=Row.names())
    writer.writeheader()

    logs = parse_logs(logfilenames)

    for info in logs:
        row = Row.from_info(info=info)
        writer.writerow(rowdict=row.name_dict())
