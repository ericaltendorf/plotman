import time
import json
import math
import os
import typing

import psutil
import texttable as tt  # from somewhere?
from itertools import groupby
from plotman import archive, configuration, job, manager, plot_util


def abbr_path(path: str, putative_prefix: str) -> str:
    if putative_prefix and path.startswith(putative_prefix):
        return os.path.relpath(path, putative_prefix)
    else:
        return path

def phases_str(phases: typing.List[job.Phase], max_num: typing.Optional[int] = None) -> str:
    '''Take a list of phase-subphase pairs and return them as a compact string'''
    if not max_num or len(phases) <= max_num:
        return ' '.join([str(pair) for pair in phases])
    else:
        n_first = math.floor(max_num / 2)
        n_last = max_num - n_first
        n_elided = len(phases) - (n_first + n_last)
        first = ' '.join([str(pair) for pair in phases[:n_first]])
        elided = " [+%d] " % n_elided
        last = ' '.join([str(pair) for pair in phases[n_first + n_elided:]])
        return first + elided + last

def n_at_ph(jobs: typing.List[job.Job], ph: job.Phase) -> int:
    return sum([1 for j in jobs if j.progress() == ph])

def n_to_char(n: int) -> str:
    n_to_char_map = dict(enumerate(" .:;!"))

    if n < 0:
        return 'X'  # Should never be negative
    elif n >= len(n_to_char_map):
        n = len(n_to_char_map) - 1

    return n_to_char_map[n]

def job_viz(jobs: typing.List[job.Job]) -> str:
    # TODO: Rewrite this in a way that ensures we count every job
    # even if the reported phases don't line up with expectations.
    result = ''
    result += '1'
    for i in range(0, 8):
        result += n_to_char(n_at_ph(jobs, job.Phase(1, i)))
    result += '2'
    for i in range(0, 8):
        result += n_to_char(n_at_ph(jobs, job.Phase(2, i)))
    result += '3'
    for i in range(0, 7):
        result += n_to_char(n_at_ph(jobs, job.Phase(3, i)))
    result += '4'
    result += n_to_char(n_at_ph(jobs, job.Phase(4, 0)))
    return result

# Command: plotman status
# Shows a general overview of all running jobs
def status_report(jobs: typing.List[job.Job], width: int, height: typing.Optional[int] = None, tmp_prefix: str = '', dst_prefix: str = '') -> str:
    '''height, if provided, will limit the number of rows in the table,
       showing first and last rows, row numbers and an elipsis in the middle.'''
    abbreviate_jobs_list = False
    n_begin_rows = 0
    n_end_rows = 0
    if height and height < len(jobs) + 1:  # One row for header
        abbreviate_jobs_list = True

        n_rows = height - 2  # Minus one for header, one for ellipsis
        n_begin_rows = int(n_rows / 2)
        n_end_rows = n_rows - n_begin_rows

    tab = tt.Texttable()
    headings = ['plot id', 'plotter', 'k', 'tmp', 'dst', 'wall', 'phase', 'tmp',
            'pid', 'stat', 'mem', 'user', 'sys', 'io']
    if height:
        headings.insert(0, '#')
    tab.header(headings)
    tab.set_cols_dtype('t' * len(headings))
    tab.set_cols_align('r' * len(headings))
    tab.set_header_align('r' * len(headings))

    for i, j in enumerate(sorted(jobs, key=job.Job.get_time_wall)):
        # Elipsis row
        if abbreviate_jobs_list and i == n_begin_rows:
            row = ['...'] + ([''] * (len(headings) - 1))
        # Omitted row
        elif abbreviate_jobs_list and i > n_begin_rows and i < (len(jobs) - n_end_rows):
            continue

        # Regular row
        else:
            try:
                with j.proc.oneshot():
                    row = [j.plot_id[:8], # Plot ID
                        str(j.plotter), # chia or madmax
                        str(j.k), # k size
                        abbr_path(j.tmpdir, tmp_prefix), # Temp directory
                        abbr_path(j.dstdir, dst_prefix), # Destination directory
                        plot_util.time_format(j.get_time_wall()), # Time wall
                        str(j.progress()), # Overall progress (major:minor)
                        plot_util.human_format(j.get_tmp_usage(), 0), # Current temp file size
                        j.proc.pid, # System pid
                        j.get_run_status(), # OS status for the job process
                        plot_util.human_format(j.get_mem_usage(), 1, True), # Memory usage
                        plot_util.time_format(j.get_time_user()), # user system time
                        plot_util.time_format(j.get_time_sys()), # system time
                        plot_util.time_format(j.get_time_iowait()) # io wait
                        ]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # In case the job has disappeared
                row = [j.plot_id[:8]] + (['--'] * (len(headings) - 2))

            if height:
                row.insert(0, '%3d' % i)

        tab.add_row(row)

    tab.set_max_width(width)
    tab.set_deco(0)  # No borders

    return tab.draw()  # type: ignore[no-any-return]

def to_prometheus_format(metrics: typing.Dict[str, str], prom_stati: typing.Sequence[typing.Tuple[str, typing.Mapping[str, typing.Optional[int]]]]) -> typing.List[str]:
    prom_str_list = []
    for metric_name, metric_desc in metrics.items():
        prom_str_list.append(f'# HELP {metric_name} {metric_desc}.')
        prom_str_list.append(f'# TYPE {metric_name} gauge')
        for label_str, values in prom_stati:
            prom_str_list.append('%s{%s} %s' % (metric_name, label_str, values[metric_name]))
    return prom_str_list

def prometheus_report(jobs: typing.List[job.Job], tmp_prefix: str = '', dst_prefix: str = '') -> str:
    metrics = {
        'plotman_plot_phase_major': 'The phase the plot is currently in',
        'plotman_plot_phase_minor': 'The part of the phase the plot is currently in',
        'plotman_plot_tmp_usage': 'Tmp dir usage in bytes',
        'plotman_plot_mem_usage': 'Memory usage in bytes',
        'plotman_plot_user_time': 'Processor time (user) in s',
        'plotman_plot_sys_time': 'Processor time (sys) in s',
        'plotman_plot_iowait_time': 'Processor time (iowait) in s',
    }
    prom_stati = []
    for j in jobs:
        labels = {
            'plot_id': j.plot_id[:8],
            'tmp_dir': abbr_path(j.tmpdir, tmp_prefix),
            'dst_dir': abbr_path(j.dstdir, dst_prefix),
            'run_status': j.get_run_status(),
            'phase': str(j.progress()),
        }
        label_str = ','.join([f'{k}="{v}"' for k, v in labels.items()])
        values = {
            'plotman_plot_phase_major': j.progress().major,
            'plotman_plot_phase_minor': j.progress().minor,
            'plotman_plot_tmp_usage': j.get_tmp_usage(),
            'plotman_plot_mem_usage': j.get_mem_usage(),
            'plotman_plot_user_time': j.get_time_user(),
            'plotman_plot_sys_time': j.get_time_sys(),
            'plotman_plot_iowait_time': j.get_time_iowait(),
        }
        prom_stati += [(label_str, values)]
    return '\n'.join(to_prometheus_format(metrics, prom_stati))

def summary(jobs: typing.List[job.Job], tmp_prefix: str = '') -> str:
    """Creates a small summary of running jobs"""

    summary = [
        'Total jobs: {0}'.format(len(jobs))
    ]

    # Number of jobs in each tmp disk
    tmp_dir_paths = sorted([abbr_path(job.tmpdir, tmp_prefix) for job in jobs])
    for key, group in groupby(tmp_dir_paths, lambda dir: dir):
        summary.append(
            'Jobs in {0}: {1}'.format(key, len(list(group)))
        )

    return '\n'.join(summary)

def tmp_dir_report(jobs: typing.List[job.Job], dir_cfg: configuration.Directories, sched_cfg: configuration.Scheduling, width: int, start_row: typing.Optional[int] = None, end_row: typing.Optional[int] = None, prefix: str = '') -> str:
    '''start_row, end_row let you split the table up if you want'''
    tab = tt.Texttable()
    headings = ['tmp', 'ready', 'phases']
    tab.header(headings)
    tab.set_cols_dtype('t' * len(headings))
    tab.set_cols_align('r' * (len(headings) - 1) + 'l')
    for i, d in enumerate(sorted(dir_cfg.tmp)):
        if (start_row and i < start_row) or (end_row and i >= end_row):
            continue
        phases = sorted(job.job_phases_for_tmpdir(d, jobs))
        ready = manager.phases_permit_new_job(phases, d, sched_cfg, dir_cfg)
        row = [abbr_path(d, prefix), 'OK' if ready else '--', phases_str(phases, 5)]
        tab.add_row(row)

    tab.set_max_width(width)
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER )
    tab.set_deco(0)  # No borders
    return tab.draw()  # type: ignore[no-any-return]

def dst_dir_report(jobs: typing.List[job.Job], dstdirs: typing.List[str], width: int, prefix: str='') -> str:
    tab = tt.Texttable()
    dir2oldphase = manager.dstdirs_to_furthest_phase(jobs)
    dir2newphase = manager.dstdirs_to_youngest_phase(jobs)
    headings = ['dst', 'plots', 'GBfree', 'inbnd phases', 'pri']
    tab.header(headings)
    tab.set_cols_dtype('t' * len(headings))

    for d in sorted(dstdirs):
        # TODO: This logic is replicated in archive.py's priority computation,
        # maybe by moving more of the logic in to directory.py
        eldest_ph = dir2oldphase.get(d, job.Phase(0, 0))
        phases = job.job_phases_for_dstdir(d, jobs)

        dir_plots = plot_util.list_plots(d)
        gb_free = int(plot_util.df_b(d) / plot_util.GB)
        n_plots = len(dir_plots)
        priority = archive.compute_priority(eldest_ph, gb_free, n_plots)
        row = [abbr_path(d, prefix), n_plots, gb_free,
                phases_str(phases, 5), priority]
        tab.add_row(row)
    tab.set_max_width(width)
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER )
    tab.set_deco(0)  # No borders
    return tab.draw()  # type: ignore[no-any-return]

def arch_dir_report(archdir_freebytes: typing.Dict[str, int], width: int, prefix: str = '') -> str:
    cells = ['%s:%5dG' % (abbr_path(d, prefix), int(int(space) / plot_util.GB))
            for (d, space) in sorted(archdir_freebytes.items())]
    if not cells:
        return ''

    n_columns = int(width / (len(max(cells, key=len)) + 3))
    tab = tt.Texttable()
    tab.set_max_width(width)
    for row in plot_util.column_wrap(cells, n_columns, filler=''):
        tab.add_row(row)
    tab.set_cols_align('r' * (n_columns))
    tab.set_deco(tt.Texttable.VLINES)
    return tab.draw()  # type: ignore[no-any-return]

# TODO: remove this
def dirs_report(jobs: typing.List[job.Job], dir_cfg: configuration.Directories, arch_cfg: typing.Optional[configuration.Archiving], sched_cfg: configuration.Scheduling, width: int) -> str:
    dst_dir = dir_cfg.get_dst_directories()
    reports = [
        tmp_dir_report(jobs, dir_cfg, sched_cfg, width),
        dst_dir_report(jobs, dst_dir, width),
    ]
    if arch_cfg is not None:
        freebytes, archive_log_messages = archive.get_archdir_freebytes(arch_cfg)
        reports.extend([
            'archive dirs free space:',
            arch_dir_report(freebytes, width),
            *archive_log_messages,
        ])

    return '\n'.join(reports) + '\n'

def json_report(jobs: typing.List[job.Job]) -> str:
    jobs_dicts = []
    for j in sorted(jobs, key=job.Job.get_time_wall):
        with j.proc.oneshot():
            jobs_dicts.append(j.to_dict())

    stuff = {
        "jobs": jobs_dicts,
        "total_jobs": len(jobs),
        "updated": time.time(),
    }

    return json.dumps(stuff)

