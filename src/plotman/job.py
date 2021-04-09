# TODO do we use all these?
import argparse
import contextlib
import logging
import os
import random
import re
import sys
import threading
import time
from datetime import datetime
from enum import Enum, auto
from subprocess import call

import psutil


def job_phases_for_tmpdir(d, all_jobs):
    '''Return phase 2-tuples for jobs running on tmpdir d'''
    return sorted([j.progress() for j in all_jobs if j.tmpdir == d])

def job_phases_for_dstdir(d, all_jobs):
    '''Return phase 2-tuples for jobs outputting to dstdir d'''
    return sorted([j.progress() for j in all_jobs if j.dstdir == d])

def is_plotting_cmdline(cmdline):
    return (
        len(cmdline) >= 4
        and 'python' in cmdline[0]
        and cmdline[1].endswith('/chia')
        and 'plots' == cmdline[2]
        and 'create' == cmdline[3]
    )

# This is a cmdline argument fix for https://github.com/ericaltendorf/plotman/issues/41
def cmdline_argfix(cmdline):
    known_keys = 'krbut2dne'
    for i in cmdline:
        # If the argument starts with dash and a known key and is longer than 2,
        # then an argument is passed with no space between its key and value.
        # This is POSIX compliant but the arg parser was tripping over it.
        # In these cases, splitting that item up in separate key and value
        # elements results in a `cmdline` list that is correctly formatted.
        if i[0]=='-' and i[1] in known_keys and len(i)>2:
            yield i[0:2]  # key
            yield i[2:]  # value
        else:
            yield i

# TODO: be more principled and explicit about what we cache vs. what we look up
# dynamically from the logfile
class Job:
    'Represents a plotter job'

    # These are constants, not updated during a run.
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
    plot_id = '--------'
    proc = None   # will get a psutil.Process
    help = False

    # These are dynamic, cached, and need to be udpated periodically
    phase = (None, None)   # Phase/subphase

    def get_running_jobs(logroot, cached_jobs=()):
        '''Return a list of running plot jobs.  If a cache of preexisting jobs is provided,
           reuse those previous jobs without updating their information.  Always look for
           new jobs not already in the cache.'''
        jobs = []
        cached_jobs_by_pid = { j.proc.pid: j for j in cached_jobs }

        for proc in psutil.process_iter(['pid', 'cmdline']):
            # Ignore processes which most likely have terminated between the time of
            # iteration and data access.
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                if is_plotting_cmdline(proc.cmdline()):
                    if proc.pid in cached_jobs_by_pid.keys():
                        jobs.append(cached_jobs_by_pid[proc.pid])  # Copy from cache
                    else:
                        job = Job(proc, logroot)
                        if not job.help:
                            jobs.append(job)

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
            args_iter = iter(cmdline_argfix(args[4:]))
            for arg in args_iter:
                val = None if arg in ['-e', '-h', '--help', '--override-k'] else next(args_iter)
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
                elif arg in {'-h', '--help'}:
                    self.help = True
                elif arg == '-e' or arg == '-f' or arg == '-p':
                    pass
                    # TODO: keep track of these
                elif arg == '--override-k':
                    pass
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

            if self.logfile:
                # Initialize data that needs to be loaded from the logfile
                self.init_from_logfile()
            else:
                print('Found plotting process PID {pid}, but could not find '
                        'logfile in its open files:'.format(pid = self.proc.pid))
                for f in self.proc.open_files():
                    print(f.path)



    def init_from_logfile(self):
        '''Read plot ID and job start time from logfile.  Return true if we
           find all the info as expected, false otherwise'''
        assert self.logfile
        # Try reading for a while; it can take a while for the job to get started as it scans
        # existing plot dirs (especially if they are NFS).
        found_id = False
        found_log = False
        for attempt_number in range(3):
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
                break  # Stop trying
            else:
                time.sleep(1)  # Sleep and try again

        # If we couldn't find the line in the logfile, the job is probably just getting started
        # (and being slow about it).  In this case, use the last metadata change as the start time.
        # TODO: we never come back to this; e.g. plot_id may remain uninitialized.
        # TODO: should we just use the process start time instead?
        if not found_log:
            self.start_time = datetime.fromtimestamp(os.path.getctime(self.logfile))

        # Load things from logfile that are dynamic
        self.update_from_logfile()

    def update_from_logfile(self):
        self.set_phase_from_logfile()

    def set_phase_from_logfile(self):
        assert self.logfile

        # Map from phase number to subphase number reached in that phase.
        # Phase 1 subphases are <started>, table1, table2, ...
        # Phase 2 subphases are <started>, table7, table6, ...
        # Phase 3 subphases are <started>, tables1&2, tables2&3, ...
        # Phase 4 subphases are <started>
        phase_subphases = {}

        with open(self.logfile, 'r') as f:
            for line in f:
                # "Starting phase 1/4: Forward Propagation into tmp files... Sat Oct 31 11:27:04 2020"
                m = re.match(r'^Starting phase (\d).*', line)
                if m:
                    phase = int(m.group(1))
                    phase_subphases[phase] = 0

                # Phase 1: "Computing table 2"
                m = re.match(r'^Computing table (\d).*', line)
                if m:
                    phase_subphases[1] = max(phase_subphases[1], int(m.group(1)))

                # Phase 2: "Backpropagating on table 2"
                m = re.match(r'^Backpropagating on table (\d).*', line)
                if m:
                    phase_subphases[2] = max(phase_subphases[2], 7 - int(m.group(1)))

                # Phase 3: "Compressing tables 4 and 5"
                m = re.match(r'^Compressing tables (\d) and (\d).*', line)
                if m:
                    phase_subphases[3] = max(phase_subphases[3], int(m.group(1)))

                # TODO also collect timing info:

                # "Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020"
                # for phase in ['1', '2', '3', '4']:
                    # m = re.match(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                        # data.setdefault....

                # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                # m = re.match(r'^Total time = (\d+.\d+) seconds.*', line)
                # if m:
                    # data.setdefault(key, {}).setdefault('total time', []).append(float(m.group(1)))

        if phase_subphases:
            phase = max(phase_subphases.keys())
            self.phase = (phase, phase_subphases[phase])
        else:
            self.phase = (0, 0)

    def progress(self):
        '''Return a 2-tuple with the job phase and subphase (by reading the logfile)'''
        return self.phase

    def plot_id_prefix(self):
        return self.plot_id[:8]

    # TODO: make this more useful and complete, and/or make it configurable
    def status_str_long(self):
        return '{plot_id}\nk={k} r={r} b={b} u={u}\npid:{pid}\ntmp:{tmp}\ntmp2:{tmp2}\ndst:{dst}\nlogfile:{logfile}'.format(
            plot_id = self.plot_id,
            k = self.k,
            r = self.r,
            b = self.b,
            u = self.u,
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
                    try:
                        total_bytes += entry.stat().st_size
                    except FileNotFoundError:
                        # The file might disappear; this being an estimate we don't care
                        pass
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
        create_time = datetime.fromtimestamp(self.proc.create_time())
        return int((datetime.now() - create_time).total_seconds())

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
        # Prevent duplicate file paths by using set.
        temp_files = set([])
        for f in self.proc.open_files():
            if self.tmpdir in f.path or self.tmp2dir in f.path or self.dstdir in f.path:
                temp_files.add(f.path)
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
