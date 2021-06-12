import csv
import sys
from dateutil.parser import parse as parse_date

import attr

from plotman.log_parser import PlotLogParser

def row_ib(name):
    return attr.ib(converter=str, metadata={'name': name})

@attr.frozen
class Row:
    plot_id: str = row_ib(name='Plot ID')
    started_at: str = row_ib(name='Started at')
    date: str = row_ib(name='Date')
    size: str = row_ib(name='Size')
    buffer: str = row_ib(name='Buffer')
    buckets: str = row_ib(name='Buckets')
    threads: str = row_ib(name='Threads')
    tmp_dir_1: str = row_ib(name='Tmp dir 1')
    tmp_dir_2: str = row_ib(name='Tmp dir 2')
    phase_1_duration_raw: str = row_ib(name='Phase 1 duration (raw)')
    phase_1_duration: str = row_ib(name='Phase 1 duration')
    phase_1_duration_minutes: str = row_ib(name='Phase 1 duration (minutes)')
    phase_1_duration_hours: str = row_ib(name='Phase 1 duration (hours)')
    phase_2_duration_raw: str = row_ib(name='Phase 2 duration (raw)')
    phase_2_duration: str = row_ib(name='Phase 2 duration')
    phase_2_duration_minutes: str = row_ib(name='Phase 2 duration (minutes)')
    phase_2_duration_hours: str = row_ib(name='Phase 2 duration (hours)')
    phase_3_duration_raw: str = row_ib(name='Phase 3 duration (raw)')
    phase_3_duration: str = row_ib(name='Phase 3 duration')
    phase_3_duration_minutes: str = row_ib(name='Phase 3 duration (minutes)')
    phase_3_duration_hours: str = row_ib(name='Phase 3 duration (hours)')
    phase_4_duration_raw: str = row_ib(name='Phase 4 duration (raw)')
    phase_4_duration: str = row_ib(name='Phase 4 duration')
    phase_4_duration_minutes: str = row_ib(name='Phase 4 duration (minutes)')
    phase_4_duration_hours: str = row_ib(name='Phase 4 duration (hours)')
    total_time_raw: str = row_ib(name='Total time (raw)')
    total_time: str = row_ib(name='Total time')
    total_time_minutes: str = row_ib(name='Total time (minutes)')
    total_time_hours: str = row_ib(name='Total time (hours)')
    copy_time_raw: str = row_ib(name='Copy time (raw)')
    copy_time: str = row_ib(name='Copy time')
    copy_time_minutes: str = row_ib(name='Copy time (minutes)')
    copy_time_hours: str = row_ib(name='Copy time (hours)')
    filename: str = row_ib(name='Filename')

    @classmethod
    def names(cls):
        return [field.metadata['name'] for field in attr.fields(cls)]

    @classmethod
    def from_info(cls, info):
        return cls(
            plot_id=info.plot_id,
            started_at=info.started_at.isoformat(),
            date=info.started_at.date().isoformat(),
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

    def name_dict(self):
        return {
            field.metadata['name']: value
            for field, value in zip(attr.fields(type(self)), attr.astuple(self))
        }

def parse_logs(logfilenames):
    parser = PlotLogParser()
    result = []

    for filename in logfilenames:
        with open(filename) as file:
            info = parser.parse(file)

        if not info.in_progress():
            result.append(info)

    result.sort(key=lambda element: element.started_at)
    return result


def generate(logfilenames, file):
    writer = csv.DictWriter(file, fieldnames=Row.names())
    writer.writeheader()

    logs = parse_logs(logfilenames)

    for info in logs:
        row = Row.from_info(info=info)
        writer.writerow(rowdict=row.name_dict())
