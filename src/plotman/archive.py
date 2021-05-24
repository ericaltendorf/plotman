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

from plotman import job, manager, plot_util

# TODO : write-protect and delete-protect archived plots

def spawn_archive_process(dir_cfg, all_jobs):
    '''Spawns a new archive process using the command created
    in the archive() function. Returns archiving status and a log message to print.'''

    log_message = None
    archiving_status = None

    # Look for running archive jobs.  Be robust to finding more than one
    # even though the scheduler should only run one at a time.
    arch_jobs = get_running_archive_jobs(dir_cfg.archive)

    if not arch_jobs:
        (should_start, status_or_cmd) = archive(dir_cfg, all_jobs)
        if not should_start:
            archiving_status = status_or_cmd
        else:
            cmd = status_or_cmd
            # TODO: do something useful with output instead of DEVNULL
            p = subprocess.Popen(cmd,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    start_new_session=True)
            log_message = 'Starting archive: ' + cmd
            # At least for now it seems that even if we get a new running
            # archive jobs list it doesn't contain the new rsync process.
            # My guess is that this is because the bash in the middle due to
            # shell=True is still starting up and really hasn't launched the
            # new rsync process yet.  So, just put a placeholder here.  It
            # will get filled on the next cycle.
            arch_jobs.append('<pending>')

    if archiving_status is None:
        archiving_status = 'pid: ' + ', '.join(map(str, arch_jobs))

    return archiving_status, log_message

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
    archdir_freebytes = {}
    df_cmd = ('ssh %s@%s df -aBK | grep " %s/"' %
        (arch_cfg.rsyncd_user, arch_cfg.rsyncd_host, posixpath.normpath(arch_cfg.rsyncd_path)) )
    with subprocess.Popen(df_cmd, shell=True, stdout=subprocess.PIPE) as proc:
        for line in proc.stdout.readlines():
            fields = line.split()
            if fields[3] == b'-':
                # not actually mounted
                continue
            freebytes = int(fields[3][:-1]) * 1024  # Strip the final 'K'
            archdir = (fields[5]).decode('utf-8')
            archdir_freebytes[archdir] = freebytes
    return archdir_freebytes

def rsync_dest(arch_cfg, arch_dir):
    rsync_path = arch_dir.replace(arch_cfg.rsyncd_path, arch_cfg.rsyncd_module)
    if rsync_path.startswith('/'):
        rsync_path = rsync_path[1:]  # Avoid dup slashes.  TODO use path join?
    rsync_url = 'rsync://%s@%s:12000/%s' % (
            arch_cfg.rsyncd_user, arch_cfg.rsyncd_host, rsync_path)
    return rsync_url

# TODO: maybe consolidate with similar code in job.py?
def get_running_archive_jobs(arch_cfg):
    '''Look for running rsync jobs that seem to match the pattern we use for archiving
       them.  Return a list of PIDs of matching jobs.'''
    jobs = []
    dest = rsync_dest(arch_cfg, '/')
    for proc in psutil.process_iter(['pid', 'name']):
        with contextlib.suppress(psutil.NoSuchProcess):
            if proc.name() == 'rsync':
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
    if dir_cfg.archive is None:
        return (False, "No 'archive' settings declared in plotman.yaml")

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
        return (False, 'No plots found')

    # TODO: sanity check that archive machine is available
    # TODO: filter drives mounted RO

    #
    # Pick first archive dir with sufficient space
    #
    archdir_freebytes = get_archdir_freebytes(dir_cfg.archive)
    if not archdir_freebytes:
        return(False, 'No free archive dirs found.')

    archdir = ''
    available = [(d, space) for (d, space) in archdir_freebytes.items() if
                 space > 1.2 * plot_util.get_k32_plotsize()]

    if len(available) > 0:
        available = sorted(available)
        candidates = []

        for candidate in available:
            # The last time thru the loop we found a resumable temp file so
            # break ths loop now
            if archdir:
                break

            # Observed pattern is:
            #   plot-k32-something.plot => .plot-k32-something.plot.XXXX
            # Check if there is an rsync temp file here. TODO maybe use find or a regex
            # pattern or make the pattern configurable, or even find better documentation on rsync temp files.
            # Making it configurable would fit better with upcoming changes to opening up the archive process,
            # Assuming that custom process created a tmp file and cleaned up after itself
            temp_cmd = ('ssh %s@%s ls -1 %s/.plot*.plot.* 2>/dev/null' %
                            (dir_cfg.archive.rsyncd_user, dir_cfg.archive.rsyncd_host, candidate[0]) )

            with subprocess.Popen(temp_cmd, shell=True, stdout=subprocess.PIPE) as proc:
                # Assumes the command returns nothing if no temp files are found (hence the supression of stderr)
                # This needs work because what if it is the ssh command that fails?
                lines = [os.path.basename(line.decode('utf-8')) for line in proc.stdout.readlines()]
                if len(lines) > 0:
                    for line in lines:
                        found = re.search(r'^\.(\S*)\.\S+', line)
                        if found and found.group(1) == chosen_plot:
                            (archdir, freespace) = candidate
                            break
                else:
                    candidates.append(candidate)

        # If we didn't find the resumable temp file, then use the first one that
        # doesn't have any temp files in it
        if not archdir and len(candidates):
            (archdir, freespace) = candidates[0]

    if not archdir:
        return(False, 'No archive directories found with enough free space')

    msg = 'Found %s with ~%d GB free' % (archdir, freespace / plot_util.GB)

    bwlimit = dir_cfg.archive.rsyncd_bwlimit
    throttle_arg = ('--bwlimit=%d' % bwlimit) if bwlimit else ''
    cmd = ('rsync %s --compress-level=0 --remove-source-files -P %s %s' %
            (throttle_arg, chosen_plot, rsync_dest(dir_cfg.archive, archdir)))

    return (True, cmd)
