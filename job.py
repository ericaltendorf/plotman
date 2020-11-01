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
import psutil      # apt-get install python-psutil
import random
import sys

class Job:
    'Represents a plotter job'
    started = False
    k = 0
    r = 0
    u = 0
    b = 0
    n = 0  # probably not used
    tmpdir = ''
    tmp2dir = ''
    dstdir = ''
    logfile = ''
    jobfile = ''
    job_id = 0
    plot_id = 0
    proc = None   # will get a psutil.Process

    def get_running_jobs(logroot):
        jobs = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.name() == 'chia':
                args = proc.cmdline()
                # args[0]=python, args[1]=chia
                if args[2] == 'plots' and args[3] == 'create':
                    jobs += [ Job(proc, logroot) ]
        return jobs

    def __init__(self, proc, logroot):
        '''Initialize from an existing psutil.Process object.  must know logroot in order to understand open files'''
        self.proc = proc

        with self.proc.oneshot():

            print('Initializing Job object for chia process %d' % self.proc.pid)

            # Parse command line args
            args = self.proc.cmdline()
            assert len(args) > 4
            assert 'python' in args[0]
            assert 'chia' in args[1]
            assert 'plots' == args[2]
            assert 'create' == args[3]
            for i in range(4, len(args), 2):
                arg = args[i]
                val = args[i + 1]
                if arg == '-k':
                    self.k = val
                elif arg == '-r':
                    self.r = val
                elif arg == '-b':
                    self.b = val
                elif arg == '-u':
                    self.u = val
                elif arg == '-t':
                    self.tmpdir = val
                elif arg == '-2':
                    self.tmp2dir = val
                elif arg == '-d':
                    self.dstdir = val
                elif arg == '-n':
                    self.n = val
                else:
                    print('Warning: unrecognized args: %s %s' % (arg, val))

            # Find logfile.  May be open more than once.
            print('finding logfile')
            for f in self.proc.open_files():
                print('looking at %s' % f.path)
                if logroot in f.path:
                    print('looks like a logfile')
                    if self.logfile:
                        assert self.logfile == f.path
                    else:
                        self.logfile = f.path
                    break

            # Find plot ID.
            print('finding plot ID from log file %s' % self.logfile)
            assert self.logfile
            with open(self.logfile, 'r') as f:
                for line in f:
                    m = re.match('^ID: ([0-9a-f]*)', line)
                    if m:
                        self.plot_id = m.group(1)
                        break

    def progress(self):
        assert self.logfile

        # Map from phase number to step number reached in that phase.
        # Phase 1 steps are <started>, table1, table2, ...
        # Phase 2 steps are <started>, table7, table6, ...
        # Phase 3 steps are <started>, tables1&2, tables2&3, ...
        # Phase 4 steps are <started>
        phase_steps = {}

        with open(self.logfile, 'r') as f:
            for line in f:
                # "Starting phase 1/4: Forward Propagation into tmp files... Sat Oct 31 11:27:04 2020"
                m = re.search(r'^Starting phase (\d).*', line)
                if m:
                    phase = int(m.group(1))
                    phase_steps[phase] = 0

                # Phase 1: "Computing table 2"
                m = re.search(r'^Computing table (\d).*', line)
                if m:
                    phase_steps[1] = max(phase_steps[1], int(m.group(1)))

                # Phase 2: "Backpropagating on table 2"
                m = re.search(r'^Backpropagating on table (\d).*', line)
                if m:
                    phase_steps[2] = max(phase_steps[2], 7 - int(m.group(1)))

                # Phase 3: "Compressing tables 4 and 5"
                m = re.search(r'^Compressing tables (\d) and (\d).*', line)
                if m:
                    phase_steps[3] = max(phase_steps[3], int(m.group(1)))

                # TODO also collect timing info:

                # "Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020"
                # for phase in ['1', '2', '3', '4']:
                    # m = re.search(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                    # if m:
                        # data.setdefault(key, {}).setdefault('phase ' + phase, []).append(float(m.group(1)))

                # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                # m = re.search(r'^Total time = (\d+.\d+) seconds.*', line)
                # if m:
                    # data.setdefault(key, {}).setdefault('total time', []).append(float(m.group(1)))

        phase = max(phase_steps.keys())
        step = phase_steps[phase]
            
        return (phase, step)

    def status_str_short(self):
        return 'pid:{pid} tmp:{tmp}, {tmp2} dst:{dst} ID:{plotid}'.format(
            pid = self.proc.pid,
            tmp = self.tmpdir,
            tmp2 = self.tmp2dir,
            dst = self.dstdir,
            plotid = self.plot_id
            )

    def status_str_long(self):
        return '{plot_id}\npid:{pid}\ntmp:{tmp}\ntmp2:{tmp2}\ndst:{dst}\nlogfile:{logfile}'.format(
            plot_id = self.plot_id,
            pid = self.proc.pid,
            tmp = self.tmpdir,
            tmp2 = self.tmp2dir,
            dst = self.dstdir,
            plotid = self.plot_id,
            logfile = self.logfile
            )

    def get_mem_usage(self):
        return self.proc.memory_info().vms  # Total, inc swapped

    def get_tmp_usage(self):
        total_bytes = 0
        with os.scandir(self.tmpdir) as it:
            for entry in it:
                if self.plot_id in entry.name:
                    total_bytes += entry.stat().st_size
        return total_bytes

    def get_run_status(self):
        '''Running, suspended, etc.'''
        return self.proc.status()

    def get_time_wall(self):
        # This doesn't seem to be working.  TODO
        return int(time.time() - self.proc.create_time())

    def get_time_user(self):
        return int(self.proc.cpu_times().user)

    def get_time_sys(self):
        return int(self.proc.cpu_times().system)

    def get_time_iowait(self):
        return int(self.proc.cpu_times().iowait)

    def suspend(self, reason=''):
        self.proc.suspend()
        self.status_note = reason

    def resume(self):
        self.proc.resume()

    def get_temp_files(self):
        temp_files = []
        for f in self.proc.open_files():
            if self.tmpdir in f.path or self.tmp2dir in f.path or self.dstdir in f.path:
                temp_files.append(f.path)
        return temp_files

    def cancel(self):
        'Cancel an already running job'
        self.proc.terminate()

    def check_status(self, expected_status):
        if (self.status == expected_status):
            return 1
        else:
            print('Expected status %s, actual %s', expected_status, self.status)
            return 0

