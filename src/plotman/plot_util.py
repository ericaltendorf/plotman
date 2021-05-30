import math
import os
import re
import shutil
from plotman import chiapos

GB = 1_000_000_000

def df_b(d):
    'Return free space for directory (in bytes)'
    usage = shutil.disk_usage(d)
    return usage.free

def get_k32_plotsize():
    return get_plotsize(32)

def get_plotsize(k):
    return (int)(_get_plotsize_scaler(k) * k * pow(2, k))

def human_format(num, precision, powerOfTwo=False):
    divisor = 1024 if powerOfTwo else 1000
    
    magnitude = 0
    while abs(num) >= divisor:
        magnitude += 1
        num /= divisor        
    result = (('%.' + str(precision) + 'f%s') %
            (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude]))

    if powerOfTwo and magnitude > 0:
	    result += 'i'
    
    return result

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
        remainders = [ os.path.relpath(i, prefix) for i in items ]
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
        row_items = items[row : : n_rows]
        # Pad and truncate
        rows.append( (row_items + ([filler] * n_cols))[:n_cols] )
    return rows

# use k as index to get plotsize_scaler, note that 0 means the value is not calculated yet
# we can safely assume that k is never going to be greater than 100, due to the exponential nature of plot file size, this avoids using constants from chiapos
_plotsize_scaler_cache = [0.0 for _ in range(0, 101)]

def calc_average_size_of_entry(k, table_index):
    '''
    calculate the average size of entries in bytes, given k and table_index
    '''
    # assumes that chia uses constant park size for each table
    # it is approximately k/8, uses chia's actual park size calculation to get a more accurate estimation
    return chiapos.CalculateParkSize(k, table_index) / chiapos.kEntriesPerPark

def _get_probability_of_entries_kept(k, table_index):
    '''
    get the probibility of entries in table of table_index that is not dropped
    '''
    # the formula is derived from https://www.chia.net/assets/proof_of_space.pdf,  section Space Required, p5 and pt

    if table_index > 5:
        return 1

    pow_2_k = 2**k
    
    if table_index == 5:
        return 1 - (1 - 2 / pow_2_k) ** pow_2_k    # p5
    else:
        return 1 - (1 - 2 / pow_2_k) ** (_get_probability_of_entries_kept(k, table_index + 1) * pow_2_k) # pt

def _get_plotsize_scaler(k:int):
    '''
    get scaler for plot size so that the plot size can be calculated by scaler * k * 2 ** k
    '''    
    result = _plotsize_scaler_cache[k]
    if result > 0:
        return result
    result = _get_plotsize_scaler_impl(k)
    _plotsize_scaler_cache[k] = result
    return result

def _get_plotsize_scaler_impl(k):
    '''
    get scaler for plot size so that the plot size can be calculated by scaler * k * 2 ** k
    '''

    result = 0
    # there are 7 tables
    for i in range(1, 8):
        probability = _get_probability_of_entries_kept(k, i)
        average_size_of_entry = calc_average_size_of_entry(k, i)
        scaler_for_table = probability * average_size_of_entry / k
        result += scaler_for_table

    return result

