import argparse
import contextlib
import math
import os
import posixpath
import random
import re
import subprocess
import sys
from datetime import datetime

import psutil
import texttable as tt

from plotman import configuration, job, manager, plot_util

# TODO : write-protect and delete-protect archived plots

def spawn_archive_process(dir_cfg, all_jobs):
    '''Spawns a new archive process using the command created
    in the archive() function. Returns archiving status and a log message to print.'''

    log_messages = []
    archiving_status = None

    # Look for running archive jobs.  Be robust to finding more than one
    # even though the scheduler should only run one at a time.
    arch_jobs = get_running_archive_jobs(dir_cfg.archive)

    if not arch_jobs:
        (should_start, status_or_cmd, archive_log_messages) = archive(dir_cfg, all_jobs)
        log_messages.extend(archive_log_messages)
        if not should_start:
            archiving_status = status_or_cmd
        else:
            args = status_or_cmd
            # TODO: do something useful with output instead of DEVNULL
            p = subprocess.Popen(**args,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    start_new_session=True)
            log_messages.append('Starting archive: ' + args['args'])
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

    archdir_freebytes = {}
    completed_process = subprocess.run(
        [arch_cfg.disk_space_path],
        encoding='utf-8',
        env={**os.environ, **arch_cfg.environment()},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for line in completed_process.stdout.strip().splitlines():
        line = line.strip()
        split = line.split(':')
        if len(split) != 2:
            log_messages.append(f'Unable to parse disk script line: {line!r}')
            continue
        archdir, space = split
        freebytes = int(space)
        archdir_freebytes[archdir.strip()] = freebytes

    stderr = completed_process.stderr.strip()
    if len(stderr) > 0:
        log_messages.append('stderr from archive script:')
        for line in stderr.splitlines():
            log_messages.append(f'    {line}')

    return archdir_freebytes, log_messages

# TODO: maybe consolidate with similar code in job.py?
def get_running_archive_jobs(arch_cfg):
    '''Look for running rsync jobs that seem to match the pattern we use for archiving
       them.  Return a list of PIDs of matching jobs.'''
    jobs = []
    for proc in psutil.process_iter():
        with contextlib.suppress(psutil.NoSuchProcess):
            with proc.oneshot():
                variables = {**os.environ, **arch_cfg.environment()}
                dest = arch_cfg.transfer_process_argument_prefix.format(**variables)
                proc_name = arch_cfg.transfer_process_name.format(**variables)
                if proc.name() == proc_name:
                    args = proc.cmdline()
                    for arg in args:
                        if arg.startswith(dest):
                            jobs.append(proc.pid)
    return jobs

def archive(dir_cfg, all_jobs):
    '''Configure one archive job.  Needs to know all jobs so it can avoid IO
    contention on the plotting dstdir drives.  Returns either (False, <reason>)
    if we should not execute an archive job or (True, <cmd>) with the archive
    command if we should.'''
    log_messages = []
    if dir_cfg.archive is None:
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
    archdir_freebytes, freebytes_log_messages = get_archdir_freebytes(dir_cfg.archive)
    log_messages.extend(freebytes_log_messages)
    if not archdir_freebytes:
        return(False, 'No free archive dirs found.', log_messages)

    archdir = ''
    available = [(d, space) for (d, space) in archdir_freebytes.items() if
                 space > 1.2 * plot_util.get_k32_plotsize()]
    if len(available) > 0:
        index = min(dir_cfg.archive.index, len(available) - 1)
        (archdir, freespace) = sorted(available)[index]

    if not archdir:
        return(False, 'No archive directories found with enough free space', log_messages)

    archive = dir_cfg.archive
    env = dir_cfg.archive.environment(
        source=chosen_plot,
        destination=archdir,
    )
    subprocess_arguments = {
        'args': archive.transfer_path,
        'env': {**os.environ, **env}
    }

    return (True, subprocess_arguments, log_messages)
