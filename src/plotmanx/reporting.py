import math
import os

import psutil
import texttable as tt  # from somewhere?

from . import archive, job, manager, plot_util


def abbr_path(path, putative_prefix):
    if putative_prefix and path.startswith(putative_prefix):
        return os.path.relpath(path, putative_prefix)
    else:
        return path


def phase_str(phase_pair):
    (ph, subph) = phase_pair
    return ((str(ph) if ph is not None else '?') + ':'
            + (str(subph) if subph is not None else '?'))


def phases_str(phases, max_num=None):
    """
    Take a list of phase-subphase pairs and return them as a compact string
    """
    if not max_num or len(phases) <= max_num:
        return ' '.join([phase_str(pair) for pair in phases])
    else:
        n_first = math.floor(max_num / 2)
        n_last = max_num - n_first
        n_elided = len(phases) - (n_first + n_last)
        first = ' '.join([phase_str(pair) for pair in phases[:n_first]])
        elided = " [+%d] " % n_elided
        last = ' '.join([phase_str(pair) for pair in phases[n_first + n_elided:]])
        return first + elided + last


def n_at_ph(jobs, ph):
    return sum([1 for j in jobs if j.progress() == ph])


def n_to_char(n):
    n_to_char_map = dict(enumerate(" .:;!"))

    if n < 0:
        return 'X'  # Should never be negative
    elif n >= len(n_to_char_map):
        n = len(n_to_char_map) - 1

    return n_to_char_map[n]


def n_to_char_emo(n):
    n_to_char_map = dict(enumerate("Z12345"))

    if n < 0:
        return 'X️'  # Should never be negative
    elif n >= len(n_to_char_map):
        n = len(n_to_char_map) - 1

    return n_to_char_map[n]


def job_viz(jobs):
    # TODO: Rewrite this in a way that ensures we count every job
    # even if the reported phases don't line up with expectations.
    result = ''
    result += '1'
    for i in range(0, 8):
        result += n_to_char_emo(n_at_ph(jobs, (1, i)))
    result += '2'
    for i in range(0, 8):
        result += n_to_char_emo(n_at_ph(jobs, (2, i)))
    result += '3'
    for i in range(0, 7):
        result += n_to_char_emo(n_at_ph(jobs, (3, i)))
    result += '4'
    result += n_to_char_emo(n_at_ph(jobs, (4, 0)))
    return result


def status_report(jobs, width, height=None, tmp_prefix='', dst_prefix=''):
    """
        Height, if provided, will limit the number of rows in the table,
       showing first and last rows, row numbers and an elipsis in the middle.
    """
    abbreviate_jobs_list = False
    n_begin_rows = 0
    n_end_rows = 0
    if height and height < len(jobs) + 1:  # One row for header
        abbreviate_jobs_list = True

    if abbreviate_jobs_list:
        n_rows = height - 2  # Minus one for header, one for ellipsis
        n_begin_rows = int(n_rows / 2)
        n_end_rows = n_rows - n_begin_rows

    tab = tt.Texttable()
    headings = ['plot id', 'k', 'tmp', 'dst', 'wall', 'phase', 'tmp', 'pid', 'stat', 'mem', 'user', 'sys', 'io', 'freezed', 'logfile']
    if height:
        headings.insert(0, '#')
    tab.header(headings)
    tab.set_cols_dtype('t' * len(headings))
    tab.set_cols_align('r' * len(headings))
    tab.set_header_align('r' * len(headings))
    for i, j in enumerate(sorted(jobs, key=job.Job.get_time_wall)):
        # Elipsis row
        if abbreviate_jobs_list and i == n_begin_rows:
            row = ['...'] + ([''] * 13)
        # Omitted row
        elif abbreviate_jobs_list and i > n_begin_rows and i < (len(jobs) - n_end_rows):
            continue

        # Regular row
        else:
            try:
                with j.proc.oneshot():
                    row = [j.plot_id[:8],
                           j.k,
                           abbr_path(j.tmpdir, tmp_prefix),
                           abbr_path(j.dstdir, dst_prefix),
                           plot_util.time_format(j.get_time_wall()),
                           phase_str(j.progress()),
                           plot_util.human_format(j.get_tmp_usage(), 0),
                           j.proc.pid,
                           j.get_run_status(),
                           plot_util.human_format(j.get_mem_usage(), 1),
                           plot_util.time_format(j.get_time_user()),
                           plot_util.time_format(j.get_time_sys()),
                           plot_util.time_format(j.get_time_iowait()),
                           plot_util.is_freezed(j),
                           os.path.basename(j.logfile)
                           ]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # In case the job has disappeared
                row = [j.plot_id[:8]] + (['--'] * 12)

            if height:
                row.insert(0, '%3d' % i)

        tab.add_row(row)

    tab.set_max_width(width)
    tab.set_deco(0)  # No borders
    # return ('tmp dir prefix: %s ; dst dir prefix: %s\n' % (tmp_prefix, dst_prefix)
    return tab.draw()


def tmp_dir_report(jobs, dir_cfg, sched_cfg, width, start_row=None, end_row=None, prefix=''):
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
        row = [abbr_path(d, prefix), 'OK' if ready else '--', phases_str(phases)]
        tab.add_row(row)

    tab.set_max_width(width)
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER)
    tab.set_deco(0)  # No borders
    return tab.draw()


def dst_dir_report(jobs, dstdirs, width, prefix=''):
    tab = tt.Texttable()
    dir2oldphase = manager.dstdirs_to_furthest_phase(jobs)
    dir2newphase = manager.dstdirs_to_youngest_phase(jobs)
    headings = ['dst', 'plots', 'GBfree', 'inbnd phases', 'pri']
    tab.header(headings)
    tab.set_cols_dtype('t' * len(headings))

    for d in sorted(dstdirs):
        # TODO: This logic is replicated in archive.py's priority computation,
        # maybe by moving more of the logic in to directory.py
        eldest_ph = dir2oldphase.get(d, (0, 0))
        phases = job.job_phases_for_dstdir(d, jobs)

        dir_plots = plot_util.list_k32_plots(d)
        gb_free = int(plot_util.df_b(d) / plot_util.GB)
        n_plots = len(dir_plots)
        priority = archive.compute_priority(eldest_ph, gb_free, n_plots)
        row = [abbr_path(d, prefix), n_plots, gb_free,
               phases_str(phases, 5), priority]
        tab.add_row(row)
    tab.set_max_width(width)
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER)
    tab.set_deco(0)  # No borders
    return tab.draw()


def arch_dir_report(archdir_freebytes, width, prefix=''):
    cells = ['%s:%5dGB' % (abbr_path(d, prefix), int(int(space) / plot_util.GB))
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
    return tab.draw()


# TODO: remove this
def dirs_report(jobs, dir_cfg, sched_cfg, width):
    reports = [
        tmp_dir_report(jobs, dir_cfg, sched_cfg, width),
        dst_dir_report(jobs, dir_cfg.dst, width),
    ]
    if dir_cfg.archive is not None:
        reports.extend([
            'archive dirs free space:',
            arch_dir_report(archive.get_archdir_freebytes(dir_cfg.archive), width),
        ])

    return '\n'.join(reports) + '\n'


def status_report_api(jobs, width, height=None, tmp_prefix='', dst_prefix=''):
    '''height, if provided, will limit the number of rows in the table,
       showing first and last rows, row numbers and an elipsis in the middle.'''
    abbreviate_jobs_list = False
    n_begin_rows = 0
    n_end_rows = 0
    if height and height < len(jobs) + 1:  # One row for header
        abbreviate_jobs_list = True

    if abbreviate_jobs_list:
        n_rows = height - 2  # Minus one for header, one for ellipsis
        n_begin_rows = int(n_rows / 2)
        n_end_rows = n_rows - n_begin_rows

    tab = tt.Texttable()
    headings = ['plot id', 'k', 'tmp', 'dst', 'wall', 'phase', 'tmp',
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
            row = ['...'] + ([''] * 13)
        # Omitted row
        elif abbreviate_jobs_list and i > n_begin_rows and i < (len(jobs) - n_end_rows):
            continue

        # Regular row
        else:
            try:
                with j.proc.oneshot():
                    row = [j.plot_id[:8],
                           j.k,
                           abbr_path(j.tmpdir, tmp_prefix),
                           abbr_path(j.dstdir, dst_prefix),
                           plot_util.time_format(j.get_time_wall()),
                           phase_str(j.progress()),
                           plot_util.human_format(j.get_tmp_usage(), 0),
                           j.proc.pid,
                           j.get_run_status(),
                           plot_util.human_format(j.get_mem_usage(), 1),
                           plot_util.time_format(j.get_time_user()),
                           plot_util.time_format(j.get_time_sys()),
                           plot_util.time_format(j.get_time_iowait())
                           ]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # In case the job has disappeared
                row = [j.plot_id[:8]] + (['--'] * 12)

            if height:
                row.insert(0, '%3d' % i)

        tab.add_row(row)

    tab.set_max_width(width)
    tab.set_deco(0)  # No borders
    # return ('tmp dir prefix: %s ; dst dir prefix: %s\n' % (tmp_prefix, dst_prefix)
    return tab.draw()
