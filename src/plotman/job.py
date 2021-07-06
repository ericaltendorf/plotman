# TODO do we use all these?
import argparse
import contextlib
import functools
import logging
import os
import random
import re
import sys
import glob
import time
from datetime import datetime
from enum import Enum, auto
from subprocess import call
import typing

import attr
import click
import pendulum
import psutil

from plotman import chia, madmax


def job_phases_for_tmpdir(d: str, all_jobs: typing.List["Job"]) -> typing.List["Phase"]:
    '''Return phase 2-tuples for jobs running on tmpdir d'''
    return sorted([j.progress() for j in all_jobs if os.path.normpath(j.tmpdir) == os.path.normpath(d)])

def job_phases_for_dstdir(d: str, all_jobs: typing.List["Job"]) -> typing.List["Phase"]:
    '''Return phase 2-tuples for jobs outputting to dstdir d'''
    return sorted([j.progress() for j in all_jobs if os.path.normpath(j.dstdir) == os.path.normpath(d)])

def is_plotting_cmdline(cmdline: typing.List[str]) -> bool:
    if cmdline and 'python' in cmdline[0].lower():  # Stock Chia plotter
        cmdline = cmdline[1:]
        return (
            len(cmdline) >= 3
            and 'chia' in cmdline[0]
            and 'plots' == cmdline[1]
            and 'create' == cmdline[2]
        )
    elif cmdline and 'chia_plot' == os.path.basename(cmdline[0].lower()):  # Madmax plotter
        return True
    return False

def parse_chia_plot_time(s: str) -> pendulum.DateTime:
    # This will grow to try ISO8601 as well for when Chia logs that way
    # TODO: unignore once fixed upstream
    #       https://github.com/sdispater/pendulum/pull/548
    return pendulum.from_format(s, 'ddd MMM DD HH:mm:ss YYYY', locale='en', tz=None)  # type: ignore[arg-type]

def parse_chia_plots_create_command_line(
    command_line: typing.List[str],
) -> "ParsedChiaPlotsCreateCommand":
    command_line = list(command_line)
    # Parse command line args
    if 'python' in command_line[0].lower():  # Stock Chia plotter
        command_line = command_line[1:]
        assert len(command_line) >= 3
        assert 'chia' in command_line[0]
        assert 'plots' == command_line[1]
        assert 'create' == command_line[2]
        all_command_arguments = command_line[3:]
        # TODO: We could at some point do chia version detection and pick the
        #       associated command.  For now we'll just use the latest one we have
        #       copied.
        command = chia.commands.latest_command()
    elif 'chia_plot' in command_line[0].lower():  # Madmax plotter
        command_line = command_line[1:]
        all_command_arguments = command_line[2:]
        command = madmax._cli_c8121b9

    # nice idea, but this doesn't include -h
    # help_option_names = command.get_help_option_names(ctx=context)
    help_option_names = {'--help', '-h'}

    command_arguments = [
        argument
        for argument in all_command_arguments
        if argument not in help_option_names
    ]

    try:
        context = command.make_context(info_name='', args=list(command_arguments))
    except click.ClickException as e:
        error = e
        params = {}
    else:
        error = None
        params = context.params

    return ParsedChiaPlotsCreateCommand(
        error=error,
        help=len(all_command_arguments) > len(command_arguments),
        parameters=params,
    )

class ParsedChiaPlotsCreateCommand:
    def __init__(
        self,
        error: click.ClickException,
        help: bool,
        parameters: typing.Dict[str, object],
    ) -> None:
        self.error = error
        self.help = help
        self.parameters = parameters

@functools.total_ordering
@attr.frozen(order=False)
class Phase:
    major: int = 0
    minor: int = 0
    known: bool = True

    def __lt__(self, other: "Phase") -> bool:
        return (
            (not self.known, self.major, self.minor)
            < (not other.known, other.major, other.minor)
        )

    @classmethod
    def from_tuple(cls, t: typing.Tuple[typing.Optional[int], typing.Optional[int]]) -> "Phase":
        if len(t) != 2:
            raise Exception(f'phase must be created from 2-tuple: {t!r}')

        if None in t and not t[0] is t[1]:
            raise Exception(f'phase can not be partially known: {t!r}')

        if t[0] is None:
            return cls(known=False)

        return cls(major=t[0], minor=t[1])  # type: ignore[arg-type]

    @classmethod
    def list_from_tuples(
        cls,
        l: typing.Sequence[typing.Tuple[typing.Optional[int], typing.Optional[int]]],
    ) -> typing.List["Phase"]:
        return [cls.from_tuple(t) for t in l]

    def __str__(self) -> str:
        if not self.known:
            return '?:?'
        return f'{self.major}:{self.minor}'

# TODO: be more principled and explicit about what we cache vs. what we look up
# dynamically from the logfile
class Job:
    'Represents a plotter job'

    logfile: str = ''
    jobfile: str = ''
    job_id: int = 0
    plot_id: str = '--------'
    plotter: str = ''
    proc: psutil.Process
    k: int
    r: int
    u: int
    b: int
    n: int
    tmpdir: str
    tmp2dir: str
    dstdir: str

    @classmethod
    def get_running_jobs(
        cls,
        logroot: str,
        cached_jobs: typing.Sequence["Job"] = (),
    ) -> typing.List["Job"]:
        '''Return a list of running plot jobs.  If a cache of preexisting jobs is provided,
           reuse those previous jobs without updating their information.  Always look for
           new jobs not already in the cache.'''
        jobs: typing.List[Job] = []
        cached_jobs_by_pid = { j.proc.pid: j for j in cached_jobs }

        with contextlib.ExitStack() as exit_stack:
            processes = []

            pids = set()
            ppids = set()

            for process in psutil.process_iter():
                # Ignore processes which most likely have terminated between the time of
                # iteration and data access.
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    exit_stack.enter_context(process.oneshot())
                    if is_plotting_cmdline(process.cmdline()):
                        ppids.add(process.ppid())
                        pids.add(process.pid)
                        processes.append(process)

            # https://github.com/ericaltendorf/plotman/pull/418
            # The experimental Chia GUI .deb installer launches plots
            # in a manner that results in a parent and child process
            # that both share the same command line and, as such, are
            # both identified as plot processes.  Only the child is
            # really plotting.  Filter out the parent.

            wanted_pids = pids - ppids

            wanted_processes = [
                process
                for process in processes
                if process.pid in wanted_pids
            ]

            for proc in wanted_processes:
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    if proc.pid in cached_jobs_by_pid.keys():
                        jobs.append(cached_jobs_by_pid[proc.pid])  # Copy from cache
                    else:
                        with proc.oneshot():
                            command_line = list(proc.cmdline())
                            if len(command_line) == 0:
                                # https://github.com/ericaltendorf/plotman/issues/610
                                continue
                            parsed_command = parse_chia_plots_create_command_line(
                                command_line=command_line,
                            )
                            if parsed_command.error is not None:
                                continue
                            job = cls(
                                proc=proc,
                                parsed_command=parsed_command,
                                logroot=logroot,
                            )
                            if job.help:
                                continue
                            jobs.append(job)

        return jobs


    def __init__(
        self,
        proc: psutil.Process,
        parsed_command: ParsedChiaPlotsCreateCommand,
        logroot: str,
    ) -> None:
        '''Initialize from an existing psutil.Process object.  must know logroot in order to understand open files'''
        self.proc = proc
        # These are dynamic, cached, and need to be udpated periodically
        self.phase = Phase(known=False)

        self.help = parsed_command.help
        self.args = parsed_command.parameters

        # an example as of 1.0.5
        # {
        #     'size': 32,
        #     'num_threads': 4,
        #     'buckets': 128,
        #     'buffer': 6000,
        #     'tmp_dir': '/farm/yards/901',
        #     'final_dir': '/farm/wagons/801',
        #     'override_k': False,
        #     'num': 1,
        #     'alt_fingerprint': None,
        #     'pool_contract_address': None,
        #     'farmer_public_key': None,
        #     'pool_public_key': None,
        #     'tmp2_dir': None,
        #     'plotid': None,
        #     'memo': None,
        #     'nobitfield': False,
        #     'exclude_final_dir': False,
        # }
        if proc.name().startswith("chia_plot"): # MADMAX
            self.k = 32
            self.r = self.args['threads']  # type: ignore[assignment]
            self.u = self.args['buckets']  # type: ignore[assignment]
            self.b = 0
            self.n = self.args['count']  # type: ignore[assignment]
            self.tmpdir = self.args['tmpdir']  # type: ignore[assignment]
            self.tmp2dir = self.args['tmpdir2']  # type: ignore[assignment]
            self.dstdir = self.args['finaldir']  # type: ignore[assignment]
        else: # CHIA
            self.k = self.args['size']  # type: ignore[assignment]
            self.r = self.args['num_threads']  # type: ignore[assignment]
            self.u = self.args['buckets']  # type: ignore[assignment]
            self.b = self.args['buffer']  # type: ignore[assignment]
            self.n = self.args['num']  # type: ignore[assignment]
            self.tmpdir = self.args['tmp_dir']  # type: ignore[assignment]
            self.tmp2dir = self.args['tmp2_dir']  # type: ignore[assignment]
            self.dstdir = self.args['final_dir']  # type: ignore[assignment]

        plot_cwd: str = self.proc.cwd()
        self.tmpdir = os.path.join(plot_cwd, self.tmpdir)
        if self.tmp2dir is not None:
            self.tmp2dir = os.path.join(plot_cwd, self.tmp2dir)
        self.dstdir = os.path.join(plot_cwd, self.dstdir)

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
# TODO: turn this into logging or somesuch
#         else:
#             print('Found plotting process PID {pid}, but could not find '
#                     'logfile in its open files:'.format(pid = self.proc.pid))
#             for f in self.proc.open_files():
#                 print(f.path)



    def init_from_logfile(self) -> None:
        '''Read plot ID and job start time from logfile.  Return true if we
           find all the info as expected, false otherwise'''
        assert self.logfile
        # Try reading for a while; it can take a while for the job to get started as it scans
        # existing plot dirs (especially if they are NFS).
        found_id = False
        found_log = False
        for attempt_number in range(3):
            with open(self.logfile, 'r') as f:
                with contextlib.suppress(UnicodeDecodeError):
                    for line in f:
                        m = re.match('^ID: ([0-9a-f]*)', line)
                        if m: # CHIA
                            self.plot_id = m.group(1)
                            self.plotter = 'chia'
                            found_id = True
                        else: 
                            m = re.match(r"^Plot Name: plot-k(\d+)-(\d+)-(\d+)-(\d+)-(\d+)-(\d+)-(\w+)$", line)
                            if m: # MADMAX
                                self.plot_id = m.group(7)
                                self.plotter = 'madmax'
                                self.start_time = pendulum.from_timestamp(os.path.getctime(self.logfile))
                                found_id = True
                                found_log = True
                                break

                        m = re.match(r'^Starting phase 1/4:.*\.\.\. (.*)', line)
                        if m: # CHIA
                            # Mon Nov  2 08:39:53 2020
                            self.start_time = parse_chia_plot_time(m.group(1))
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
            self.start_time = pendulum.from_timestamp(os.path.getctime(self.logfile))

        # Load things from logfile that are dynamic
        self.update_from_logfile()

    def update_from_logfile(self) -> None:
        self.set_phase_from_logfile()

    def set_phase_from_logfile(self) -> None:
        assert self.logfile

        # Map from phase number to subphase number reached in that phase.
        # Phase 1 subphases are <started>, table1, table2, ...
        # Phase 2 subphases are <started>, table7, table6, ...
        # Phase 3 subphases are <started>, tables1&2, tables2&3, ...
        # Phase 4 subphases are <started>
        phase_subphases = {}

        with open(self.logfile, 'r') as f:
            with contextlib.suppress(UnicodeDecodeError):
                for line in f:
                    if self.plotter == "madmax":

                        # MADMAX reports after completion of phases so increment the reported subphases
                        # and assume that phase 1 has already started

                        # MADMAX: "[P1]" or "[P2]" or "[P4]"
                        m = re.match(r'^\[P(\d)\].*', line)
                        if m:
                            phase = int(m.group(1))
                            phase_subphases[phase] = 1

                        # MADMAX: "[P1] or [P2] Table 7"
                        m = re.match(r'^\[P(\d)\] Table (\d).*', line)
                        if m:
                            phase = int(m.group(1))
                            if phase == 1:
                                phase_subphases[1] = max(phase_subphases[1], (int(m.group(2))+1))

                            elif phase == 2:
                                if 'rewrite' in line:
                                    phase_subphases[2] = max(phase_subphases[2], (9 - int(m.group(2))))
                                else:
                                    phase_subphases[2] = max(phase_subphases[2], (8 - int(m.group(2))))

                        # MADMAX: Phase 3: "[P3-1] Table 4"
                        m = re.match(r'^\[P3\-(\d)\] Table (\d).*', line)
                        if m:
                            if 3 in phase_subphases:
                                if int(m.group(1)) == 2:
                                    phase_subphases[3] = max(phase_subphases[3], int(m.group(2)))
                                else:
                                    phase_subphases[3] = max(phase_subphases[3], int(m.group(2))-1)
                            else: 
                                phase_subphases[3] = 1

                    else:                    
                        # CHIA: "Starting phase 1/4: Forward Propagation into tmp files... Sat Oct 31 11:27:04 2020"
                        m = re.match(r'^Starting phase (\d).*', line)
                        if m:
                            phase = int(m.group(1))
                            phase_subphases[phase] = 0
                        
                        # CHIA: Phase 1: "Computing table 2"
                        m = re.match(r'^Computing table (\d).*', line)
                        if m:
                            phase_subphases[1] = max(phase_subphases[1], int(m.group(1)))
                        
                        # CHIA: Phase 2: "Backpropagating on table 2"
                        m = re.match(r'^Backpropagating on table (\d).*', line)
                        if m:
                            phase_subphases[2] = max(phase_subphases[2], 7 - int(m.group(1)))

                        # CHIA: Phase 3: "Compressing tables 4 and 5"
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
            self.phase = Phase(major=phase, minor=phase_subphases[phase])
        else:
            self.phase = Phase(major=0, minor=0)

    def progress(self) -> Phase:
        '''Return a 2-tuple with the job phase and subphase (by reading the logfile)'''
        return self.phase

    def plot_id_prefix(self) -> str:
        return self.plot_id[:8]

    # TODO: make this more useful and complete, and/or make it configurable
    def status_str_long(self) -> str:
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
            logfile = self.logfile
            )

    def print_logs(self, follow: bool = False) -> None:
        with open(self.logfile, 'r') as f:
            if follow:
                line = ''
                while True:
                    tmp = f.readline()
                    if tmp is not None:
                        line += tmp
                        if line.endswith("\n"):
                            print(line.rstrip('\n'))
                            line = ''
                    else:
                        time.sleep(0.1)
            else:
                print(f.read())

    def to_dict(self) -> typing.Dict[str, object]:
        '''Exports important information as dictionary.'''
        return dict(
            plot_id=self.plot_id[:8],
            k=self.k,
            tmp_dir=self.tmpdir,
            dst_dir=self.dstdir,
            progress=str(self.progress()),
            tmp_usage=self.get_tmp_usage(),
            pid=self.proc.pid,
            run_status=self.get_run_status(),
            mem_usage=self.get_mem_usage(),
            time_wall=self.get_time_wall(),
            time_user=self.get_time_user(),
            time_sys=self.get_time_sys(),
            time_iowait=self.get_time_iowait()
        )


    def get_mem_usage(self) -> int:
        # Total, inc swapped
        return self.proc.memory_info().vms  # type: ignore[no-any-return]

    def get_tmp_usage(self) -> int:
        total_bytes = 0
        with contextlib.suppress(FileNotFoundError):
            # The directory might not exist at this name, or at all, anymore
            with os.scandir(self.tmpdir) as it:
                for entry in it:
                    if self.plot_id in entry.name:
                        with contextlib.suppress(FileNotFoundError):
                            # The file might disappear; this being an estimate we don't care
                            total_bytes += entry.stat().st_size
        return total_bytes

    def get_run_status(self) -> str:
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
            return self.proc.status()  # type: ignore[no-any-return]

    def get_time_wall(self) -> int:
        create_time = datetime.fromtimestamp(self.proc.create_time())
        return int((datetime.now() - create_time).total_seconds())

    def get_time_user(self) -> int:
        return int(self.proc.cpu_times().user)

    def get_time_sys(self) -> int:
        return int(self.proc.cpu_times().system)

    def get_time_iowait(self) -> typing.Optional[int]:
        cpu_times = self.proc.cpu_times()
        iowait = getattr(cpu_times, 'iowait', None)
        if iowait is None:
            return None

        return int(iowait)

    def suspend(self, reason: str = '') -> None:
        self.proc.suspend()
        self.status_note = reason

    def resume(self) -> None:
        self.proc.resume()

    def get_temp_files(self) -> typing.Set[str]:
        # Prevent duplicate file paths by using set.
        temp_files = set([])

        for dir in [self.tmpdir, self.tmp2dir, self.dstdir]:
            if dir is not None:
                temp_files.update(glob.glob(os.path.join(dir, f"plot-*-{self.plot_id}.tmp")))

        return temp_files

    def cancel(self) -> None:
        'Cancel an already running job'
        # We typically suspend the job as the first action in killing it, so it
        # doesn't create more tmp files during death.  However, terminate() won't
        # complete if the job is supsended, so we also need to resume it.
        # TODO: check that this is best practice for killing a job.
        self.proc.resume()
        self.proc.terminate()
