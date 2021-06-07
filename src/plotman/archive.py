import argparse
import contextlib
import logging
import math
import os
import posixpath
import random
import re
import subprocess
import sys
from datetime import datetime

import pendulum
import psutil
import texttable as tt

from plotman import configuration, job, manager, plot_util


logger = logging.getLogger(__name__)

_WINDOWS = sys.platform == 'win32'

# TODO : write-protect and delete-protect archived plots

def spawn_archive_process(dir_cfg, arch_cfg, log_cfg, all_jobs):
    '''Spawns a new archive process using the command created
    in the archive() function. Returns archiving status and a log message to print.'''

    log_messages = []
    archiving_status = None

    # Look for running archive jobs.  Be robust to finding more than one
    # even though the scheduler should only run one at a time.
    arch_jobs = get_running_archive_jobs(arch_cfg)

    if not arch_jobs:
        (should_start, status_or_cmd, archive_log_messages) = archive(dir_cfg, arch_cfg, all_jobs)
        log_messages.extend(archive_log_messages)
        if not should_start:
            archiving_status = status_or_cmd
        else:
            args = status_or_cmd

            log_file_path = log_cfg.create_transfer_log_path(time=pendulum.now())

            log_messages.append(f'Starting archive: {args["args"]} ; logging to {log_file_path}')
            # TODO: CAMPid 09840103109429840981397487498131
            try:
                open_log_file = open(log_file_path, 'x')
            except FileExistsError:
                log_messages.append(
                    f'Archiving log file already exists, skipping attempt to start a'
                    f' new archive transfer: {log_file_path!r}'
                )
                return (False, log_messages)
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

            with open_log_file:
                # start_new_sessions to make the job independent of this controlling tty.
                p = subprocess.Popen(**args,
                    shell=True,
                    stdout=open_log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    creationflags=0 if not _WINDOWS else subprocess.CREATE_NO_WINDOW)
            # At least for now it seems that even if we get a new running
            # archive jobs list it doesn't contain the new rsync process.
            # My guess is that this is because the bash in the middle due to
            # shell=True is still starting up and really hasn't launched the
            # new rsync process yet.  So, just put a placeholder here.  It
            # will get filled on the next cycle.
            arch_jobs.append('<pending>')

    if archiving_status is None:
        archiving_status = 'pid: ' + ', '.join(map(str, arch_jobs))

    return archiving_status, log_messages

def compute_priority(phase, gb_free, n_plots):
    # All these values are designed around dst buffer dirs of about
    # ~2TB size and containing k32 plots.  TODO: Generalize, and
    # rewrite as a sort function.

    priority = 50

    # To avoid concurrent IO, we should not touch drives that
    # are about to receive a new plot.  If we don't know the phase,
    # ignore.
    if (phase.known):
        if (phase == job.Phase(3, 4)):
            priority -= 4
        elif (phase == job.Phase(3, 5)):
            priority -= 8
        elif (phase == job.Phase(3, 6)):
            priority -= 16
        elif (phase >= job.Phase(3, 7)):
            priority -= 32

    # If a drive is getting full, we should prioritize it
    if (gb_free < 1000):
        priority += 1 + int((1000 - gb_free) / 100)
    if (gb_free < 500):
        priority += 1 + int((500 - gb_free) / 100)

    # Finally, least importantly, pick drives with more plots
    # over those with fewer.
    priority += n_plots

    return priority

def get_archdir_freebytes(arch_cfg):
    log_messages = []
    target = arch_cfg.target_definition()

    archdir_freebytes = {}
    timeout = 5
    try:
        completed_process = subprocess.run(
            [target.disk_space_path],
            env={**os.environ, **arch_cfg.environment()},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        log_messages.append(f'Disk space check timed out in {timeout} seconds')
        if e.stdout is None:
            stdout = ''
        else:
            stdout = e.stdout.decode('utf-8', errors='ignore').strip()
        if e.stderr is None:
            stderr = ''
        else:
            stderr = e.stderr.decode('utf-8', errors='ignore').strip()
    else:
        stdout = completed_process.stdout.decode('utf-8', errors='ignore').strip()
        stderr = completed_process.stderr.decode('utf-8', errors='ignore').strip()
        for line in stdout.splitlines():
            line = line.strip()
            split = line.split(':')
            if len(split) != 2:
                log_messages.append(f'Unable to parse disk script line: {line!r}')
                continue
            archdir, space = split
            freebytes = int(space)
            archdir_freebytes[archdir.strip()] = freebytes

    for line in log_messages:
        logger.info(line)

    logger.info('stdout from disk space script:')
    for line in stdout.splitlines():
        logger.info(f'    {line}')

    logger.info('stderr from disk space script:')
    for line in stderr.splitlines():
        logger.info(f'    {line}')

    return archdir_freebytes, log_messages

# TODO: maybe consolidate with similar code in job.py?
def get_running_archive_jobs(arch_cfg):
    '''Look for running rsync jobs that seem to match the pattern we use for archiving
       them.  Return a list of PIDs of matching jobs.'''
    jobs = []
    target = arch_cfg.target_definition()
    variables = {**os.environ, **arch_cfg.environment()}
    dest = target.transfer_process_argument_prefix.format(**variables)
    proc_name = target.transfer_process_name.format(**variables)
    for proc in psutil.process_iter():
        with contextlib.suppress(psutil.NoSuchProcess):
            with proc.oneshot():
                if proc.name() == proc_name:
                    args = proc.cmdline()
                    for arg in args:
                        if arg.startswith(dest):
                            jobs.append(proc.pid)
    return jobs

def archive(dir_cfg, arch_cfg, all_jobs):
    '''Configure one archive job.  Needs to know all jobs so it can avoid IO
    contention on the plotting dstdir drives.  Returns either (False, <reason>)
    if we should not execute an archive job or (True, <cmd>) with the archive
    command if we should.'''
    log_messages = []
    if arch_cfg is None:
        return (False, "No 'archive' settings declared in plotman.yaml", log_messages)

    dir2ph = manager.dstdirs_to_furthest_phase(all_jobs)
    best_priority = -100000000
    chosen_plot = None
    dst_dir = dir_cfg.get_dst_directories()
    for d in dst_dir:
        ph = dir2ph.get(d, job.Phase(0, 0))
        dir_plots = plot_util.list_k32_plots(d)
        gb_free = plot_util.df_b(d) / plot_util.GB
        n_plots = len(dir_plots)
        priority = compute_priority(ph, gb_free, n_plots)
        if priority >= best_priority and dir_plots:
            best_priority = priority
            chosen_plot = dir_plots[0]

    if not chosen_plot:
        return (False, 'No plots found', log_messages)

    # TODO: sanity check that archive machine is available
    # TODO: filter drives mounted RO

    #
    # Pick first archive dir with sufficient space
    #
    archdir_freebytes, freebytes_log_messages = get_archdir_freebytes(arch_cfg)
    log_messages.extend(freebytes_log_messages)
    if not archdir_freebytes:
        return(False, 'No free archive dirs found.', log_messages)

    archdir = ''
    chosen_plot_size = os.stat(chosen_plot).st_size
    # 10MB is big enough to outsize filesystem block sizes hopefully, but small
    # enough to make this a pretty tight corner for people to get stuck in.
    free_space_margin = 10_000_000
    available = [(d, space) for (d, space) in archdir_freebytes.items() if
                 space > (chosen_plot_size + free_space_margin)]
    if len(available) > 0:
        index = min(arch_cfg.index, len(available) - 1)
        (archdir, freespace) = sorted(available)[index]

    if not archdir:
        return(False, 'No archive directories found with enough free space', log_messages)

    env = arch_cfg.environment(
        source=chosen_plot,
        destination=archdir,
    )
    subprocess_arguments = {
        'args': arch_cfg.target_definition().transfer_path,
        'env': {**os.environ, **env}
    }

    return (True, subprocess_arguments, log_messages)
