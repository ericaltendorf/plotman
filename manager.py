#!/usr/bin/python3

# TODO do we use all these?
from datetime import datetime
from datetime import timedelta
from enum import Enum, auto
from subprocess import call
import argparse

import logging
import os
import re
import threading
import time
import random
import readline          # For nice CLI
import sys
import texttable as tt   # from somewhere?

# Plotman libraries
from job import Job

parser = argparse.ArgumentParser(description='Initiate Chia plotting jobs.')
parser.add_argument('--dryrun', default=False, action='store_true',
        help='Show plotting actions but do not execute them.')
args = parser.parse_args()
dryrun = args.dryrun

MIN = 60    # Seconds
HR = 3600   # Seconds

kval = 32
n_jobs_per_dir = 4 * 2            # Number of jobs to run per temp dir
job_stagger_s = 3.5 * HR          # Seconds to wait between jobs on same tmpdir
n_sequential = 1                  # Number of plots for each job to create
tmpdir_stagger_s = 30 * MIN       # Seconds to offset jobs on different tmpdirs
n_threads = 12                    # Threads per job
n_buckets = 128                   # Number of buckets to split data into

# Directories
dstdir_root = '/home/eric/chia/plots'
dstdirs = [ '002', '003', '004', '005' ]
# tmpdir_root = '/mnt/tmp'
tmpdirs = [ '/mnt/tmp/' + d for d in [ '00', '01', '02', '03' ] ]
tmpdir2 = '/mnt/tmp/a/'
logroot = '/home/eric/chia/logs'
logdir = os.path.join(logroot, datetime.now().strftime('%Y-%m-%d-%H-%M'))

# Per job memory
total_buffer = 60000              # MB to dedicate to plotting buffers 
job_buffer = int(total_buffer / (len(tmpdirs) * n_jobs_per_dir))
job_buffer = 4550   # Force to just over the 3250 magic cutoff .. dangerous if you have too many jobs

# Globals
all_jobs = []
test_global = 'initial value'

 
#def daemon_thread():
    #'Daemon thread for automatically starting jobs and monitoring job status'
    #global all_jobs
    #print('entering thread')
    #while True:
        #print('Plot initiator thread creating job')
        #new_job = Job('/tmp/a', '/tmp/b', test_global)
        #all_jobs = all_jobs + [ new_job ]
        #for job in all_jobs:
            #print(job.status_str_short())
        #time.sleep(5)

def init_logdir(logdir):
    try:
        os.makedirs(logdir)
        latest_symlink = os.path.join(logroot, '0.latest')
        os.remove(latest_symlink)
        os.symlink(logdir, latest_symlink)
    except OSError as err:
        print('Failed to init logdirs: {0}'.format(err))
        sys.exit(1)

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
    headings = ['plot id', 'status', 'phase', 'k', 'r', 'tmp dir', 'tmp', 'wall', 'pid', 'mem', 'user', 'sys', 'io']
    tab.header(headings)
    for j in jobs:
        row = [j.plot_id[:8] + '...',
               j.get_run_status(),
               '%d:%d' % j.progress(),
               j.k,
               j.r,
               j.tmpdir,
               human_format(j.get_tmp_usage(), 0),
               time_format(j.get_time_wall(), 1),
               j.proc.pid,
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

if __name__ == "__main__":
    random.seed()

    print('...scanning process tables')
    jobs = Job.get_running_jobs(logroot)
    print('Welcome to PlotMan.  Detected %d active plot jobs.  Type \'h\' for help.' % len(jobs))

    # This is a really cheapo CLI.  Would be better to use some standard library.
    while True:
        cmd_line = input('plotman> ')
        if cmd_line:
            # Re-read active jobs
            jobs = Job.get_running_jobs(logroot)

            cmd_line = cmd_line.split()
            cmd = cmd_line[0]
            args = cmd_line[1:]

            if cmd == 'h':
                print('Commands which reference a job require an unambiguous prefix of the plot id')
                print('  l            : list current jobs')
                print('  d <idprefix> : show details for a plot job')
                print('  f <idprefix> : show temp files for a job')
                print('  k <idprefix> : kill and cleanup a plot job')
                print('  p <idprefix> : pause (suspend) a plot job')
                print('  r <idprefix> : resume a plot job')
                print('  h            : help info (this message)')
                print('  x            : exit')
                continue

            elif cmd == 'l':
                print(status_report(jobs))
                continue

            elif cmd == 'x':
                break

            elif cmd == 'd' or cmd == 'f' or cmd == 'k' or cmd == 'p' or cmd == 'r':
                if (len(args) != 1):
                    print('Need to supply job id spec')
                    continue

                id_spec = args[0]
                selected = select_jobs_by_partial_id(jobs, id_spec)
                if (len(selected) == 0):
                    print('Error: %s matched no jobs.')
                    continue
                elif len(selected) > 1:
                    print('Error: "%s" matched multiple jobs:' % id_spec)
                    for j in selected:
                        print('  %s' % j.plot_id)
                    continue
                else:
                    job = selected[0]

                    # Do the real command
                    if cmd == 'd':
                        print(job.status_str_long())

                    elif cmd == 'f':
                        temp_files = job.get_temp_files()
                        for f in temp_files:
                            print('  %s' % f)

                    elif cmd == 'k':
                        # First suspend so job doesn't create new files
                        print('Pausing PID %d, plot id %s' % (job.proc.pid, job.plot_id))
                        job.suspend()

                        temp_files = job.get_temp_files()
                        print('Will kill pid %d, plot id %s' % (job.proc.pid, job.plot_id))
                        print('Will delete %d temp files' % len(temp_files))
                        conf = input('Are you sure? ("y" to confirm): ')
                        if (conf != 'y'):
                            print('canceled.  If you wish to resume the job, do so manually.')
                        else:
                            print('killing...')
                            job.cancel()
                            print('cleaing up temp files...')
                            for f in temp_files:
                                os.remove(f)

                    elif cmd == 'p':
                        print('Pausing ' + job.plot_id)
                        job.suspend()
                    elif cmd == 'r':
                        print('Resuming ' + job.plot_id)
                        job.resume()

            else:
                print('Unknown command: %s' % cmd)
                continue 

    sys.exit(0)

