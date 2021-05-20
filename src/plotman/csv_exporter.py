import csv
import sys
from dateutil.parser import parse as parse_date
from plotman.log_parser import PlotLogParser
from plotman.plotinfo import PlotInfo

def export(logfilenames, save_to = None):
    if save_to is None:
        send_to_stdout(logfilenames)
    else:
        save_to_file(logfilenames, save_to)

def save_to_file(logfilenames, filename: str):
    with open(filename, 'w') as file:
        generate(logfilenames, file)

def send_to_stdout(logfilenames):
    generate(logfilenames, sys.stdout)

def header(writer):
    writer.writerow([
        'Plot ID', 
        'Started at',
        'Date',
        'Size',
        'Buffer',
        'Buckets',
        'Threads',
        'Tmp dir 1',
        'Tmp dir 2',
        'Phase 1 duration (raw)',
        'Phase 1 duration',
        'Phase 1 duration (minutes)',
        'Phase 1 duration (hours)',
        'Phase 2 duration (raw)',
        'Phase 2 duration',
        'Phase 2 duration (minutes)',
        'Phase 2 duration (hours)',
        'Phase 3 duration (raw)',
        'Phase 3 duration',
        'Phase 3 duration (minutes)',
        'Phase 3 duration (hours)',
        'Phase 4 duration (raw)',
        'Phase 4 duration',
        'Phase 4 duration (minutes)',
        'Phase 4 duration (hours)',
        'Total time (raw)',
        'Total time',
        'Total time (minutes)',
        'Total time (hours)',
        'Copy time (raw)',
        'Copy time',
        'Copy time (minutes)',
        'Copy time (hours)',
        'Filename'
    ])

def parse_logs(logfilenames):
    parser = PlotLogParser()
    result = []

    for filename in logfilenames:
        info = parser.parse(filename)

        if not info.is_empty():
            result.append(info)

    result.sort(key=log_sort_key)
    return result

def log_sort_key(element: PlotInfo):
    return parse_date(element.started_at).replace(microsecond=0).isoformat()

def generate(logfilenames, out):
    writer = csv.writer(out)
    header(writer)
    logs = parse_logs(logfilenames)

    for info in logs:
        writer.writerow([
            info.plot_id,
            info.started_at,
            parse_date(info.started_at).strftime('%Y-%m-%d'),
            info.plot_size,
            info.buffer,
            info.buckets,
            info.threads,
            info.tmp_dir1,
            info.tmp_dir2,
            info.phase1_duration_raw,
            info.phase1_duration,
            info.phase1_duration_minutes,
            info.phase1_duration_hours,
            info.phase2_duration_raw,
            info.phase2_duration,
            info.phase2_duration_minutes,
            info.phase2_duration_hours,
            info.phase3_duration_raw,
            info.phase3_duration,
            info.phase3_duration_minutes,
            info.phase3_duration_hours,
            info.phase4_duration_raw,
            info.phase4_duration,
            info.phase4_duration_minutes,
            info.phase4_duration_hours,
            info.total_time_raw,
            info.total_time,
            info.total_time_minutes,
            info.total_time_hours,
            info.copy_time_raw,
            info.copy_time,
            info.copy_time_minutes,
            info.copy_time_hours,
            info.filename
        ])
