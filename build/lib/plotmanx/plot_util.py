import math
import os
import re

GB = 1_000_000_000


def df_b(d):
    'Return free space for directory (in bytes)'
    stat = os.statvfs(d)
    return stat.f_frsize * stat.f_bavail


def get_k32_plotsize():
    return 108 * GB


def human_format(num, precision):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return (('%.' + str(precision) + 'f%s') %
            (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude]))


def time_format(sec):
    if sec is None:
        return '-'
    if sec < 60:
        return '%ds' % sec
    else:
        return '%d:%02d' % (int(sec / 3600), int((sec % 3600) / 60))


def tmpdir_phases_str(tmpdir_phases_pair):
    tmpdir = tmpdir_phases_pair[0]
    phases = tmpdir_phases_pair[1]
    phase_str = ', '.join(['%d:%d' % ph_subph for ph_subph in sorted(phases)])
    return ('%s (%s)' % (tmpdir, phase_str))


def split_path_prefix(items):
    if not items:
        return ('', [])

    prefix = os.path.commonpath(items)
    if prefix == '/':
        return ('', items)
    else:
        remainders = [os.path.relpath(i, prefix) for i in items]
        return (prefix, remainders)


def list_k32_plots(d):
    'List completed k32 plots in a directory (not recursive)'
    plots = []
    for plot in os.listdir(d):
        if re.match(r'^plot-k32-.*plot$', plot):
            plot = os.path.join(d, plot)
            try:
                if os.stat(plot).st_size > (0.95 * get_k32_plotsize()):
                    plots.append(plot)
            except FileNotFoundError:
                continue

    return plots


def column_wrap(items, n_cols, filler=None):
    '''Take items, distribute among n_cols columns, and return a set
       of rows containing the slices of those columns.'''
    rows = []
    n_rows = math.ceil(len(items) / n_cols)
    for row in range(n_rows):
        row_items = items[row:: n_rows]
        # Pad and truncate
        rows.append((row_items + ([filler] * n_cols))[:n_cols])
    return rows


def is_freezed(job):
    return 'YES' if job.last_updated_time_in_min > 60 else 'NO'
