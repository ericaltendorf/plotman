import logging
import operator
import os
import random
import re
import subprocess
import sys
import time
import typing
from datetime import datetime

import pendulum
import psutil

# Plotman libraries
from plotman import \
    archive  # for get_archdir_freebytes(). TODO: move to avoid import loop
from plotman import job, plot_util
import plotman.configuration

# Constants
MIN = 60    # Seconds
HR = 3600   # Seconds

MAX_AGE = 1000_000_000   # Arbitrary large number of seconds

def dstdirs_to_furthest_phase(all_jobs: typing.List[job.Job]) -> typing.Dict[str, job.Phase]:
    '''Return a map from dst dir to a phase tuple for the most progressed job
       that is emitting to that dst dir.'''
    result: typing.Dict[str, job.Phase] = {}
    for j in all_jobs:
        if not j.dstdir in result.keys() or result[j.dstdir] < j.progress():
            result[j.dstdir] = j.progress()
    return result

def dstdirs_to_youngest_phase(all_jobs: typing.List[job.Job]) -> typing.Dict[str, job.Phase]:
    '''Return a map from dst dir to a phase tuple for the least progressed job
       that is emitting to that dst dir.'''
    result: typing.Dict[str, job.Phase] = {}
    for j in all_jobs:
        if j.dstdir is None:
            continue
        if not j.dstdir in result.keys() or result[j.dstdir] > j.progress():
            result[j.dstdir] = j.progress()
    return result

def phases_permit_new_job(phases: typing.List[job.Phase], d: str, sched_cfg: plotman.configuration.Scheduling, dir_cfg: plotman.configuration.Directories) -> bool:
    '''Scheduling logic: return True if it's OK to start a new job on a tmp dir
       with existing jobs in the provided phases.'''
    # Filter unknown-phase jobs
    phases = [ph for ph in phases if ph.known]

    if len(phases) == 0:
        return True

    # Assign variables
    major = sched_cfg.tmpdir_stagger_phase_major
    minor = sched_cfg.tmpdir_stagger_phase_minor
    # tmpdir_stagger_phase_limit default is 1, as declared in configuration.py
    stagger_phase_limit = sched_cfg.tmpdir_stagger_phase_limit
    
    # Limit the total number of jobs per tmp dir. Default to overall max
    # jobs configuration, but restrict to any configured overrides.
    max_plots = sched_cfg.tmpdir_max_jobs
    
    # Check if any overrides exist for the current job
    if sched_cfg.tmp_overrides is not None and d in sched_cfg.tmp_overrides:
        curr_overrides = sched_cfg.tmp_overrides[d]
    
        # Check for and assign major & minor phase overrides
        if curr_overrides.tmpdir_stagger_phase_major is not None:
            major = curr_overrides.tmpdir_stagger_phase_major
        if curr_overrides.tmpdir_stagger_phase_minor is not None:
            minor = curr_overrides.tmpdir_stagger_phase_minor
        # Check for and assign stagger phase limit override
        if curr_overrides.tmpdir_stagger_phase_limit is not None:
            stagger_phase_limit = curr_overrides.tmpdir_stagger_phase_limit
        # Check for and assign stagger phase limit override
        if curr_overrides.tmpdir_max_jobs is not None:
            max_plots = curr_overrides.tmpdir_max_jobs
        
    milestone = job.Phase(major,minor)
    
    # Check if phases pass the criteria
    if len([p for p in phases if p < milestone]) >= stagger_phase_limit:
        return False

    if len(phases) >= max_plots:
        return False

    return True

def maybe_start_new_plot(dir_cfg: plotman.configuration.Directories, sched_cfg: plotman.configuration.Scheduling, plotting_cfg: plotman.configuration.Plotting, log_cfg: plotman.configuration.Logging) -> typing.Tuple[bool, str]:
    jobs = job.Job.get_running_jobs(log_cfg.plots)

    wait_reason = None  # If we don't start a job this iteration, this says why.

    youngest_job_age = min(jobs, key=job.Job.get_time_wall).get_time_wall() if jobs else MAX_AGE
    global_stagger = int(sched_cfg.global_stagger_m * MIN)
    if (youngest_job_age < global_stagger):
        wait_reason = 'stagger (%ds/%ds)' % (youngest_job_age, global_stagger)
    elif len(jobs) >= sched_cfg.global_max_jobs:
        wait_reason = 'max jobs (%d) - (%ds/%ds)' % (sched_cfg.global_max_jobs, youngest_job_age, global_stagger)
    else:
        tmp_to_all_phases = [(d, job.job_phases_for_tmpdir(d, jobs)) for d in dir_cfg.tmp]
        eligible = [ (d, phases) for (d, phases) in tmp_to_all_phases
                if phases_permit_new_job(phases, d, sched_cfg, dir_cfg) ]
        rankable = [ (d, phases[0]) if phases else (d, job.Phase(known=False))
                for (d, phases) in eligible ]

        if not eligible:
            wait_reason = 'no eligible tempdirs (%ds/%ds)' % (youngest_job_age, global_stagger)
        else:
            # Plot to oldest tmpdir.
            tmpdir = max(rankable, key=operator.itemgetter(1))[0]

            dst_dirs = dir_cfg.get_dst_directories()

            dstdir: str
            if dir_cfg.dst_is_tmp2():
                dstdir = dir_cfg.tmp2  # type: ignore[assignment]
            elif tmpdir in dst_dirs:
                dstdir = tmpdir
            elif dir_cfg.dst_is_tmp():
                dstdir = tmpdir
            else:
                # Select the dst dir least recently selected
                dir2ph = { d:ph for (d, ph) in dstdirs_to_youngest_phase(jobs).items()
                        if d in dst_dirs and ph is not None}
                unused_dirs = [d for d in dst_dirs if d not in dir2ph.keys()]
                dstdir = ''
                if unused_dirs:
                    dstdir = random.choice(unused_dirs)
                else:
                    def key(key: str) -> job.Phase:
                        return dir2ph[key]
                    dstdir = max(dir2ph, key=key)

            log_file_path = log_cfg.create_plot_log_path(time=pendulum.now())

            plot_args: typing.List[str]
            if plotting_cfg.type == "madmax":
                if plotting_cfg.madmax is None:
                    raise Exception(
                        "madmax plotter selected but not configured, report this as a plotman bug",
                    )
                plot_args = ['chia_plot',
                    '-n', str(1),
                    '-r', str(plotting_cfg.madmax.n_threads),
                    '-u', str(plotting_cfg.madmax.n_buckets),
                    '-t', tmpdir if tmpdir.endswith('/') else (tmpdir + '/'),
                    '-d', dstdir if dstdir.endswith('/') else (dstdir + '/') ]
                if dir_cfg.tmp2 is not None:
                    plot_args.append('-2')
                    plot_args.append(dir_cfg.tmp2 if dir_cfg.tmp2.endswith('/') else (dir_cfg.tmp2 + '/'))
            else:
                if plotting_cfg.chia is None:
                    raise Exception(
                        "chia plotter selected but not configured, report this as a plotman bug",
                    )
                plot_args = ['chia', 'plots', 'create',
                    '-k', str(plotting_cfg.chia.k),
                    '-r', str(plotting_cfg.chia.n_threads),
                    '-u', str(plotting_cfg.chia.n_buckets),
                    '-b', str(plotting_cfg.chia.job_buffer),
                    '-t', tmpdir,
                    '-d', dstdir ]
                if plotting_cfg.chia.e:
                    plot_args.append('-e')
                if plotting_cfg.chia.x:
                    plot_args.append('-x')  
                if dir_cfg.tmp2 is not None:
                    plot_args.append('-2')
                    plot_args.append(dir_cfg.tmp2)
            if plotting_cfg.farmer_pk is not None:
                plot_args.append('-f')
                plot_args.append(plotting_cfg.farmer_pk)
            if plotting_cfg.pool_pk is not None:
                plot_args.append('-p')
                plot_args.append(plotting_cfg.pool_pk)
            if plotting_cfg.pool_contract_address is not None:
                plot_args.append('-c')
                plot_args.append(plotting_cfg.pool_contract_address)



            logmsg = ('Starting plot job: %s ; logging to %s' % (' '.join(plot_args), log_file_path))

            # TODO: CAMPid 09840103109429840981397487498131
            try:
                open_log_file = open(log_file_path, 'x')
            except FileExistsError:
                # The desired log file name already exists.  Most likely another
                # plotman process already launched a new process in response to
                # the same scenario that triggered us.  Let's at least not
                # confuse things further by having two plotting processes
                # logging to the same file.  If we really should launch another
                # plotting process, we'll get it at the next check cycle anyways.
                message = (
                    f'Plot log file already exists, skipping attempt to start a'
                    f' new plot: {log_file_path!r}'
                )
                return (False, logmsg)
            except FileNotFoundError as e:
                message = (
                    f'Unable to open log file.  Verify that the directory exists'
                    f' and has proper write permissions: {log_file_path!r}'
                )
                raise Exception(message) from e

            # Preferably, do not add any code between the try block above
            # and the with block below.  IOW, this space intentionally left
            # blank...  As is, this provides a good chance that our handle
            # of the log file will get closed explicitly while still
            # allowing handling of just the log file opening error.

            if sys.platform == 'win32':
                creationflags = subprocess.CREATE_NO_WINDOW
                nice = psutil.BELOW_NORMAL_PRIORITY_CLASS
            else:
                creationflags = 0
                nice = 15

            with open_log_file:
                # start_new_sessions to make the job independent of this controlling tty (POSIX only).
                # subprocess.CREATE_NO_WINDOW to make the process independent of this controlling tty and have no console window on Windows.
                p = subprocess.Popen(plot_args,
                    stdout=open_log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    creationflags=creationflags)

            psutil.Process(p.pid).nice(nice)
            return (True, logmsg)

    return (False, wait_reason)

def select_jobs_by_partial_id(jobs: typing.List[job.Job], partial_id: str) -> typing.List[job.Job]:
    selected = []
    for j in jobs:
        if j.plot_id.startswith(partial_id):
            selected.append(j)
    return selected
