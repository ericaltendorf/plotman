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

class JobStatus(Enum):
    UNSTARTED = auto()
    RUNNING = auto()
    SUSPENDED = auto()
    CANCELING = auto()
    CANCELED = auto()
    COMPLETED = auto()

class Job:
    'Represents a plotter job'
    started = False
    tmpdir = ''
    tmp2dir = ''
    dstdir = ''
    logfile = ''
    jobfile = ''
    status = JobStatus.UNSTARTED
    status_note = ''  # extra info as to why status (e.g. suspended) was entered
    job_id = 0
    plot_id = 0
    proc = None   # will get a subprocess

    def __init__(self, tmpdir, tmp2dir, dstdir):
        self.tmpdir = tmpdir
        self.tmp2dir = tmp2dir
        self.dstdir = dstdir
        status = JobStatus.UNSTARTED
        self.job_id = hex(random.getrandbits(32))

    def status_str(self):
        return '%s pid:%s %s (%s): %s, %s, %s' % (self.job_id, self.proc.pid, self.status, self.status_note, self.tmpdir, self.tmp2dir, self.dstdir)

    def get_mem_usage(self):
        # resource.getrusage()  # TODO this isn't right, need more research
        return 0

    def get_tmp_usage(self):
        total_bytes = 0
        with os.scandir(self.tmpdir) as it:
            for entry in it:
                if self.plot_id in entry.name:
                    total_bytes += entry.stat().st_size
        return total_bytes

    def start(self, logdir):
        check_status(JobStatus.UNSTARTED) || return -1;

        job_fname_base = datetime.now().strftime('%Y-%m-%d-%H-%M') + '.' +
            os.path.basename(tmpdir) + '.' +
            self.job_id

        self.logfile = os.path.join(logdir, '%s.log' % job_fname_base)
        self.jobfile = os.path.join(logdir, '%s.cmd' % job_fname_base)

        # params
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

        # Define process
        self.proc = subprocess.Popen(['chia'] + plot_args)   # try ', shell=True)' if problems

        # TODO
        # Fork process
        # Write job metainfo
        # Start job
        self.status = JobStatus.RUNNING

        if not dryrun:
            with open(self.jobfile, 'w') as f:
                # TODO: write more of the params etc.
                f.write('Command executed:\n')
                f.write(plot_cmd_str + '\n')
            # Could do this better, I think
            call(full_cmd, shell=True)

    def suspend(self, reason=''):
        # TODO learn about python 'assert'
        check_status(JobStatus.RUNNING) || return -1;
        self.proc.send_signal(signal.SIGSTOP)
        self.status = JobStatus.SUSPENDED
        self.status_note = reason

    def resume(self):
        check_status(JobStatus.SUSPENDED) || return -1;
        self.proc.send_signal(signal.SIGCONT)

    def cancel(self):
        'Cancel an already running job'
        self.proc.terminate()
        self.status = JobStatus.CANCELED

    def check_status(self, expected_status):
        if (self.status == expected_status):
            return 1
        else:
            print('Expected status %s, actual %s', expected_status, self.status)
            return 0

