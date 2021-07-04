import os
import subprocess
from pathlib import Path

from plotman import configuration


class JobPhases(object):
    '''Holds jobs last known phase progress with simple helper methods.'''
    _job_ph = dict()

    @classmethod
    def changed(cls, job):
        """Checks provided job's phase agains its last known phase.
        returns True if job's phase changed, or job was just created.
        returns False if job is known and phase matches phase on state."""
        if not job.progress():
            return False
        return not cls._job_ph.get(job.plot_id) or cls._job_ph[job.plot_id] != job.progress()

    @classmethod
    def update(cls, job_ph):
        """Updates internal state with new 'last known' job phases"""
        if job_ph:
            cls._job_ph = job_ph

    @classmethod
    def progress(cls, plot_id):
        """Returns job's last known Phase as provided by Job.progress()"""
        return cls._job_ph.get(plot_id)


def run_cmd(command, env):
    try:
        result = subprocess.run(command, capture_output=True, env=env)
    except Exception as ex:
        return 1, "", str(ex)

    return result.returncode, result.stdout, result.stderr


def try_run(jobs):
    """Iterates over jobs gathered during refresh, executes hooks.d
    if phase was changed and updates last known phase info for next iteration."""
    phases = dict()

    for job in jobs:
        if job.progress() is None:
            continue

        phases[job.plot_id] = job.progress()
        if not JobPhases().changed(job):
            continue

        run(job)

    JobPhases().update(phases)


def prepare_env(job, hooks_path):
    """Prepares env dict for the provided job"""

    environment = os.environ.copy()
    environment['PLOTMAN_HOOKS'] = hooks_path
    environment['PLOTMAN_PLOTID'] = job.plot_id
    environment['PLOTMAN_PID'] = str(job.proc.pid)
    environment['PLOTMAN_TMPDIR'] = environment['PLOTMAN_TMP2DIR'] = environment['PLOTMAN_DSTDIR'] = job.tmpdir
    if job.tmp2dir is not None and job.tmp2dir != '':
        environment['PLOTMAN_TMP2DIR'] = job.tmp2dir
    if job.dstdir is not None and job.dstdir != '':
        environment['PLOTMAN_DSTDIR'] = job.dstdir
    environment['PLOTMAN_LOGFILE'] = job.logfile
    environment['PLOTMAN_STATUS'] = job.get_run_status()
    environment['PLOTMAN_PHASE'] = str(job.progress().major) + ':' + str(job.progress().minor)

    old_phase = JobPhases().progress(job.plot_id)
    if old_phase:
        old_phase = str(JobPhases().progress(job.plot_id).major) + ':' + str(JobPhases().progress(job.plot_id).minor)
    else:
        old_phase = str(old_phase)
    environment['PLOTMAN_PHASE_PREV'] = old_phase

    return environment


def run(job, trigger="PHASE"):
    """Runs all scripts in alphabetical order from the hooks.d directory
    for the provided job.

    Job's internal state is added to the Plotman's own environment.
    Folowing env VARIABLES are exported:
    - PLOTMAN_PLOTID            (id of the plot)
    - PLOTMAN_PID               (pid of the process)
    - PLOTMAN_TMPDIR            (tmp dir [-t])
    - PLOTMAN_TMP2DIR           (tmp2 dir [-2])
    - PLOTMAN_DSTDIR            (dst dir [-d])
    - PLOTMAN_LOGFILE           (logfile)
    - PLOTMAN_STATUS            (current state of the process, e.g. RUN, STP - check job class for details)
    - PLOTMAN_PHASE             (phase, "major:minor" - two numbers, colon delimited)
    - PLOTMAN_PHASE_PREV        (phase, previous if known, or "None")
    - PLOTMAN_TRIGGER           (action, which triggered hooks. currently one of "PHASE"-change or "KILL")
    """

    hooks_path = configuration.get_path('hooks.d')

    if os.getenv('PLOTMAN_HOOKS') is not None:
        return

    environment = prepare_env(job, hooks_path)
    environment['PLOTMAN_TRIGGER'] = trigger

    for e in ['*.py','*.sh']:
        for script in Path(hooks_path).glob(e):
            rc, stdout, stderr = run_cmd([str(script)], environment)

