#!/usr/bin/python3

# TODO do we use all these?
from datetime import datetime
from enum import Enum, auto
from subprocess import call
import argparse

import logging
import os
import re
import threading
import time
import random
import sys

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

 
def daemon_thread():
    'Daemon thread for automatically starting jobs and monitoring job status'
    global all_jobs
    print('entering thread')
    while True:
        print('Plot initiator thread creating job')
        new_job = Job('/tmp/a', '/tmp/b', test_global)
        all_jobs = all_jobs + [ new_job ]
        for job in all_jobs:
            print(job.status_str())
        time.sleep(5)

def init_logdir(logdir):
    try:
        os.makedirs(logdir)
        latest_symlink = os.path.join(logroot, '0.latest')
        os.remove(latest_symlink)
        os.symlink(logdir, latest_symlink)
    except OSError as err:
        print('Failed to init logdirs: {0}'.format(err))
        sys.exit(1)

if __name__ == "__main__":
    random.seed()

    # Start plot initiator thread
    daemon_thread = threading.Thread(target=daemon_thread, args=(), daemon=True)
    daemon_thread.start()

    while True:
        cmd = input('> ')
        if cmd:
            test_global = cmd
            print(cmd)

    sys.exit(0)


if (not dryrun):
    init_logdir(logdir)
    # ensure we're in chia env
    # need to fix thsi one: chia init || exit 1

print('Running %d jobs per temp dir' % n_jobs_per_dir)
print('Temp dirs: { %s }' % ', '.join(tmpdirs) )
print('Dest dirs: %s + { %s }' % ( dstdir_root, ', '.join(dstdirs) ))
print('Logging to ' + logdir)

for tmpdir_idx in range(len(tmpdirs)):
    tmpdir = tmpdirs[tmpdir_idx]

    for job_idx in range(n_jobs_per_dir):
        delay = job_idx * job_stagger_s + tmpdir_idx * tmpdir_stagger_s

        dst_idx = (tmpdir_idx * n_jobs_per_dir + job_idx) % len(dstdirs)

        dstdir = os.path.join(dstdir_root, dstdirs[dst_idx])


# move to job.py:
        job_fname_base = ('tmp%02d-job%02d' % (tmpdir_idx, job_idx))
        logfile = os.path.join(logdir, '%s.log' % job_fname_base)
        cmdfile = os.path.join(logdir, '%s.cmd' % job_fname_base)

        plot_args = ['chia', 'plots', 'create',
                '-k', str(kval),
                '-n', str(n_sequential),
                '-r', str(n_threads),
                '-u', str(n_buckets),
                '-b', str(job_buffer),
                '-t', tmpdir,
                '-2', tmpdir2,
                '-d', dstdir
                ]

        plot_cmd_str = ' '.join(plot_args)
        full_cmd = 'sleep %d && %s > %s 2>&1 &' % (delay, plot_cmd_str, logfile)
        print('tmpdir %d job %d: %s' % (tmpdir_idx, job_idx, full_cmd))
        if not dryrun:
            with open(cmdfile, 'w') as f:
                f.write(plot_cmd_str + '\n')
            # Could do this better, I think
            call(full_cmd, shell=True)
