#!/usr/bin/python3

from datetime import datetime

import logging
import operator
import os
import re
import threading
import time
import random
import readline          # For nice CLI
import subprocess
import sys
import texttable as tt   # from somewhere?

# Plotman libraries
from job import Job

# Constants
MIN = 60    # Seconds
HR = 3600   # Seconds

MAX_AGE = 1000_000_000   # Arbitrary large number of seconds

def job_phases_for_dir(d, all_jobs):
    '''Return phase 2-tuples for jobs running on tmpdir d'''
    return sorted([j.progress() for j in all_jobs if j.tmpdir == d])

def phases_permit_new_job(phases):
    '''Scheduling logic: return True if it's OK to start a new job on a tmp dir
       with existing jobs in the provided phases.'''
    phases = [ ph for (ph, subph) in phases ]
    num_jobs = len(phases)

    # No more than 3 jobs total on the tmpdir
    if num_jobs > 3:
        return False

    # No more than one in phase 2
    if phases.count(2) > 1:
        return False

    # Zero in phase 1.
    if phases.count(1) > 0:
        return False

    return True

def tmpdir_phases_str(tmpdir_phases_pair):
    tmpdir = tmpdir_phases_pair[0]
    phases = tmpdir_phases_pair[1]
    phase_str = ', '.join(['%d:%d' % ph_subph for ph_subph in sorted(phases)])
    return ('%s: (%s)' % (tmpdir, phase_str))

def daemon_thread(dir_cfg, scheduling_cfg, plotting_cfg):
    'Daemon thread for automatically starting jobs and monitoring job status'

    while True:
        jobs = Job.get_running_jobs(dir_cfg['log'])

        wait_reason = None  # If we don't start a job this iteration, this says why.

        youngest_job_age = min(jobs, key=Job.get_time_wall, default=MAX_AGE).get_time_wall()
        global_stagger = int(scheduling_cfg['global_stagger_m'] * MIN)
        if (youngest_job_age < global_stagger):
            wait_reason = 'global stagger (age is %d, not yet %d)' % (
                    youngest_job_age, global_stagger)
        else:
            tmp_to_phases = [ (d, job_phases_for_dir(d, jobs)) for d in dir_cfg['tmp'] ]
            eligible = [ (d, ph) for (d, ph) in tmp_to_phases if phases_permit_new_job(ph) ]
            
            if not eligible:
                all_tmpdir_str = ', '.join(map(tmpdir_phases_str, tmp_to_phases))
                wait_reason = 'no eligible tempdirs: ' + all_tmpdir_str
            else:
                # Plot to oldest tmpdir
                tmpdir = max(eligible, key=operator.itemgetter(1))[0]
                print('Eligible tmpdirs: ' + str(eligible))
                print('Selected: ' + tmpdir)

                dstdir = random.choice(dir_cfg['dst'])  # TODO: Pick most empty drive?
                logfile = os.path.join(dir_cfg['log'],
                        datetime.now().strftime('%Y-%m-%d-%H:%M:%S.log'))

                plot_args = ['chia', 'plots', 'create',
                        '-k', str(plotting_cfg['k']),
                        '-r', str(plotting_cfg['n_threads']),
                        '-u', str(plotting_cfg['n_buckets']),
                        '-b', str(plotting_cfg['job_buffer']),
                        '-t', tmpdir,
                        '-2', dir_cfg['tmp2'],
                        '-d', dstdir ]

                print('\nDaemon starting new plot job:\n  %s\n  logging to %s' %
                        (' '.join(plot_args), logfile))

                # start_new_sessions to make the job independent of this controlling tty.
                subprocess.Popen(plot_args,
                    stdout=open(logfile, 'w'),
                    stderr=subprocess.STDOUT,
                    start_new_session=True)

        # TODO: report this via a channel that can be polled on demand, so we don't spam the console
        sleep_s = int(scheduling_cfg['polling_time_s'])
        if wait_reason:
            print('...sleeping %d s: %s' % (sleep_s, wait_reason))

        time.sleep(sleep_s)

def human_format(num, precision):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return (('%.' + str(precision) + 'f%s') % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude]))

def time_format(sec, precision):
    if sec < 60:
        return '%ds' % sec
    else:
        return '%d:%02d' % (int(sec / 3600), int((sec % 3600) / 60))

def status_report(jobs):
    tab = tt.Texttable()
    headings = ['plot id', 'k', 'tmp dir', 'wall', 'phase', 'tmp', 'pid', 'stat', 'mem', 'user', 'sys', 'io']
    tab.header(headings)
    tab.set_cols_align('r' * len(headings))
    for j in sorted(jobs, key=Job.get_time_wall):
        row = [j.plot_id[:8] + '...',
               j.k,
               j.tmpdir,
               time_format(j.get_time_wall(), 1),
               '%d:%d' % j.progress(),
               human_format(j.get_tmp_usage(), 0),
               j.proc.pid,
               j.get_run_status(),
               human_format(j.get_mem_usage(), 1),
               time_format(j.get_time_user(), 1),
               time_format(j.get_time_sys(), 1),
               time_format(j.get_time_iowait(), 1)
               ]
        tab.add_row(row)

    (rows, columns) = os.popen('stty size', 'r').read().split()
    tab.set_max_width(int(columns))
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER )
    return tab.draw()
 
def select_jobs_by_partial_id(jobs, partial_id):
    selected = []
    for j in jobs:
        if j.plot_id.startswith(partial_id):
            selected.append(j)
    return selected

