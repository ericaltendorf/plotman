import operator
import os
import random
import subprocess
from datetime import datetime
import pendulum
import psutil

# Plotman libraries
from . import job

# Constants
MIN = 60  # Seconds
HR = 3600  # Seconds
MAX_PLOT_SIZE = 332  # Minimum gb required for k32 plot
MAX_AGE = 1000_000_000  # Arbitrary large number of seconds


def dstdirs_to_furthest_phase(all_jobs):
    '''Return a map from dst dir to a phase tuple for the most progressed job
       that is emitting to that dst dir.'''
    result = {}
    for j in all_jobs:
        if not j.dstdir in result.keys() or result[j.dstdir] < j.progress():
            result[j.dstdir] = j.progress()
    return result


def dstdirs_to_youngest_phase(all_jobs):
    '''Return a map from dst dir to a phase tuple for the least progressed job
       that is emitting to that dst dir.'''
    result = {}
    for j in all_jobs:
        if not j.dstdir in result.keys() or result[j.dstdir] > j.progress():
            result[j.dstdir] = j.progress()
    return result


def phases_permit_new_job(phases, d, sched_cfg, dir_cfg):
    '''Scheduling logic: return True if it's OK to start a new job on a tmp dir
       with existing jobs in the provided phases.'''
    # Filter unknown-phase jobs
    phases = [ph for ph in phases if ph[0] is not None and ph[1] is not None]

    if len(phases) == 0:
        return True

    milestone = (sched_cfg.tmpdir_stagger_phase_major, sched_cfg.tmpdir_stagger_phase_minor)
    # tmpdir_stagger_phase_limit default is 1, as declared in configuration.py
    if len([p for p in phases if p < milestone]) >= sched_cfg.tmpdir_stagger_phase_limit:
        return False

    # Limit the total number of jobs per tmp dir. Default to the overall max
    # jobs configuration, but restrict to any configured overrides.
    max_plots = sched_cfg.tmpdir_max_jobs
    if dir_cfg.tmp_overrides is not None and d in dir_cfg.tmp_overrides:
        curr_overrides = dir_cfg.tmp_overrides[d]
        if curr_overrides.tmpdir_max_jobs is not None:
            max_plots = curr_overrides.tmpdir_max_jobs
    if len(phases) >= max_plots:
        return False

    return True


def get_size(dir_cfg):
    dir = str(dir_cfg)
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += (os.path.getsize(fp)) / 1000000000

    return total_size


def select_jobs_by_partial_id(jobs, partial_id):
    selected = []
    for j in jobs:
        if j.plot_id.startswith(partial_id):
            selected.append(j)
    return selected


def maybe_start_new_plot(dir_cfg, sched_cfg, plotting_cfg):
    jobs = job.Job.get_running_jobs(dir_cfg.log)

    wait_reason = None  # If we don't start a job this iteration, this says why.

    youngest_job_age = min(jobs, key=job.Job.get_time_wall).get_time_wall() if jobs else MAX_AGE
    global_stagger = int(sched_cfg.global_stagger_m * MIN)
    if (youngest_job_age < global_stagger):
        wait_reason = 'stagger (%ds/%ds)' % (youngest_job_age, global_stagger)
    elif len(jobs) >= sched_cfg.global_max_jobs:
        wait_reason = 'max jobs (%d)' % sched_cfg.global_max_jobs
    elif (get_size(dir_cfg) < MAX_PLOT_SIZE):
        wait_reason = '(%s) gb size of (%d) < require size (%d)' % (dir_cfg, get_size(dir_cfg), MAX_PLOT_SIZE)
    else:
        tmp_to_all_phases = [(d, job.job_phases_for_tmpdir(d, jobs)) for d in dir_cfg.tmp]
        eligible = [(d, phases) for (d, phases) in tmp_to_all_phases
                    if phases_permit_new_job(phases, d, sched_cfg, dir_cfg)]
        rankable = [(d, phases[0]) if phases else (d, (999, 999)) for (d, phases) in eligible]

        if not eligible:
            wait_reason = 'no eligible tempdirs'
        else:
            # Plot to oldest tmpdir.
            tmpdir = max(rankable, key=operator.itemgetter(1))[0]

            # Select the dst dir least recently selected
            dir2ph = {d: ph for (d, ph) in dstdirs_to_youngest_phase(jobs).items()
                      if d in dir_cfg.dst}
            unused_dirs = [d for d in dir_cfg.dst if d not in dir2ph.keys()]
            dstdir = ''
            if unused_dirs:
                dstdir = random.choice(unused_dirs)
            else:
                dstdir = max(dir2ph, key=dir2ph.get)

            logfile = os.path.join(
#                dir_cfg.log, datetime.now().strftime('%Y-%m-%d-%H:%M:%S.log')
                 dir_cfg.log, pendulum.now().isoformat(timespec='microseconds').replace(':', '_') + '.log'
            )

            plot_args = ['chia', 'plots', 'create',
                         '-k', str(plotting_cfg.k),
                         '-r', str(plotting_cfg.n_threads),
                         '-u', str(plotting_cfg.n_buckets),
                         '-b', str(plotting_cfg.job_buffer),
                         '-t', tmpdir,
                         '-d', dstdir]
            if plotting_cfg.e:
                plot_args.append('-e')
            if plotting_cfg.farmer_pk is not None:
                plot_args.append('-f')
                plot_args.append(plotting_cfg.farmer_pk)
            if plotting_cfg.pool_pk is not None:
                plot_args.append('-p')
                plot_args.append(plotting_cfg.pool_pk)
            if dir_cfg.tmp2 is not None:
                plot_args.append('-2')
                plot_args.append(dir_cfg.tmp2)

            logmsg = ('Starting plot job: %s ; logging to %s' % (' '.join(plot_args), logfile))

            try:
                open_log_file = open(logfile, 'x')
            except FileExistsError:
                # The desired log file name already exists.  Most likely another
                # plotman process already launched a new process in response to
                # the same scenario that triggered us.  Let's at least not
                # confuse things further by having two plotting processes
                # logging to the same file.  If we really should launch another
                # plotting process, we'll get it at the next check cycle anyways.
                message = (
                    f'Plot log file already exists, skipping attempt to start a'
                    f' new plot: {logfile!r}'
                )
                return (False, logmsg)

            # start_new_sessions to make the job independent of this controlling tty.
            p = subprocess.Popen(plot_args,
                                 stdout=open_log_file,
                                 stderr=subprocess.STDOUT,
                                 start_new_session=True)

            psutil.Process(p.pid).nice(15)
            return (True, logmsg)

    return (False, wait_reason)
