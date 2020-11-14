#!/usr/bin/python3

from datetime import datetime

import logging
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

def daemon_thread(dir_cfg, scheduling_cfg, plotting_cfg):
    'Daemon thread for automatically starting jobs and monitoring job status'

    while True:
        jobs = Job.get_running_jobs(dir_cfg['log'])

        wait_reason = None  # If we don't start a job this iteration, this says why.

        # TODO: Factor out some of this complex logic, clean it up, add unit tests
        
        # Identify the most recent time a tmp had a job start (its "age")
        tmpdir_age = {}
        for d in dir_cfg['tmp']:
            d_jobs = [j for j in jobs if j.tmpdir == d]
            if d_jobs:
                tmpdir_age[d] = min(d_jobs, key=Job.get_time_wall, default=MAX_AGE).get_time_wall()
            else:
                tmpdir_age[d] = MAX_AGE

        # We should only plot if the youngest tmpdir is old enough
        min_tmpdir_age = min(tmpdir_age.values()) 
        global_stagger = int(scheduling_cfg['global_stagger_m'] * MIN)
        if (min_tmpdir_age < global_stagger):
            wait_reason = 'global stagger (age is %d, not yet %d)' % (min_tmpdir_age, global_stagger)
        else:
            # Filter too-young tmpdirs
            tmpdir_age = { k:v for k, v in tmpdir_age.items()
                if v > int(scheduling_cfg['tmpdir_stagger_m']) * MIN }

            if not tmpdir_age:
                wait_reason = 'tmpdir stagger period'
            else:
                # Plot to oldest tmpdir
                tmpdir = max(tmpdir_age, key=tmpdir_age.get)

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
        sleep_m = int(scheduling_cfg['polling_time_m'])
        if wait_reason:
            print('Daemon not starting job because: %s; sleeping %d m' % (wait_reason, sleep_m))

        time.sleep(sleep_m * MIN)

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

