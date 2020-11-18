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

# TODO: be more principled and explicit about what we cache vs. what we look up
# dynamically from the logfile
class Job:
    'Represents a plotter job'
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
    initialized = False  # Set to true once data structures are fully initialized

    def get_running_jobs(logroot):
        jobs = []
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.name() == 'chia':
                args = proc.cmdline()
                # n.b.: args[0]=python, args[1]=chia
                if len(args) >= 4 and args[2] == 'plots' and args[3] == 'create':
                    jobs += [ Job(proc, logroot) ]
        return jobs

    def __init__(self, proc, logroot):
        '''Initialize from an existing psutil.Process object.  must know logroot in order to understand open files'''
        self.proc = proc

        with self.proc.oneshot():
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

            # Find logfile (whatever file is open under the log root).  The
            # file may be open more than once, e.g. for STDOUT and STDERR.
            for f in self.proc.open_files():
                if logroot in f.path:
                    if self.logfile:
                        assert self.logfile == f.path
                    else:
                        self.logfile = f.path
                    break

            # Find plot ID and start time.
            if not self.init_from_logfile():
                # This should rarely if ever happen, but if it does, this object is
                # left in an uninitialized state and will probably crash things later.
                # TODO: handle this error case better.
                print('WARNING: unable to initialize job info from logfile %s' % self.logfile)

            assert self.logfile
            with open(self.logfile, 'r') as f:
                found_id = False
                found_log = False
                for line in f:
                    m = re.match('^ID: ([0-9a-f]*)', line)
                    if m:
                        self.plot_id = m.group(1)
                        found_id = True
                    m = re.match(r'^Starting phase 1/4:.*\.\.\. (.*)', line)
                    if m:
                        # Mon Nov  2 08:39:53 2020
                        # TODO: If you read this logfile in the first 5 or so seconds of the job running,
                        # this line will not have been logged yet and we won't initialize the start time.
                        # Should correct this.
                        self.start_time = datetime.strptime(m.group(1), '%a %b  %d %H:%M:%S %Y')
                        found_log = True
                        break

    def init_from_logfile(self):
        '''Read plot ID and job start time from logfile.  Return true if we
           find the info, false otherwise'''
        assert self.logfile
        # Try reading for a while; it can take a while for the job to get started as it scans
        # existing plot dirs (especially if they are NFS).
        found_id = False
        found_log = False
        for attempt_number in range(60):
            with open(self.logfile, 'r') as f:
                for line in f:
                    m = re.match('^ID: ([0-9a-f]*)', line)
                    if m:
                        self.plot_id = m.group(1)
                        found_id = True
                    m = re.match(r'^Starting phase 1/4:.*\.\.\. (.*)', line)
                    if m:
                        # Mon Nov  2 08:39:53 2020
                        self.start_time = datetime.strptime(m.group(1), '%a %b  %d %H:%M:%S %Y')
                        found_log = True
                        break  # Stop reading lines in file

            if found_id and found_log:
                return True  # Stop trying
            else:
                print('Logfile not ready; retrying: %s' % self.logfile)
                time.sleep(5)  # Sleep and try again

        return False  # Give up!


    def progress(self):
        '''Return a 2-tuple with the job phase and subphase (by reading the logfile)'''
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
                m = re.match(r'^Starting phase (\d).*', line)
                if m:
                    phase = int(m.group(1))
                    phase_steps[phase] = 0

                # Phase 1: "Computing table 2"
                m = re.match(r'^Computing table (\d).*', line)
                if m:
                    phase_steps[1] = max(phase_steps[1], int(m.group(1)))

                # Phase 2: "Backpropagating on table 2"
                m = re.match(r'^Backpropagating on table (\d).*', line)
                if m:
                    phase_steps[2] = max(phase_steps[2], 7 - int(m.group(1)))

                # Phase 3: "Compressing tables 4 and 5"
                m = re.match(r'^Compressing tables (\d) and (\d).*', line)
                if m:
                    phase_steps[3] = max(phase_steps[3], int(m.group(1)))

                # TODO also collect timing info:

                # "Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020"
                # for phase in ['1', '2', '3', '4']:
                    # m = re.match(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                        # data.setdefault....

                # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                # m = re.match(r'^Total time = (\d+.\d+) seconds.*', line)
                # if m:
                    # data.setdefault(key, {}).setdefault('total time', []).append(float(m.group(1)))

        phase = max(phase_steps.keys())
        step = phase_steps[phase]
            
        return (phase, step)

    # TODO: make this more useful and complete, and/or make it configurable
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
        status = self.proc.status()
        if status == psutil.STATUS_RUNNING:
            return 'RUN'
        elif status == psutil.STATUS_SLEEPING:
            return 'SLP'
        elif status == psutil.STATUS_DISK_SLEEP:
            return 'DSK'
        elif status == psutil.STATUS_STOPPED:
            return 'STP'
        else:
            return self.proc.status()

    def get_time_wall(self):
        return int((datetime.now() - self.start_time).total_seconds())

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
        # We typically suspend the job as the first action in killing it, so it
        # doesn't create more tmp files during death.  However, terminate() won't
        # complete if the job is supsended, so we also need to resume it.
        # TODO: check that this is best practice for killing a job.
        self.proc.resume()
        self.proc.terminate()

    def check_status(self, expected_status):
        if (self.status == expected_status):
            return 1
        else:
            print('Expected status %s, actual %s', expected_status, self.status)
            return 0

