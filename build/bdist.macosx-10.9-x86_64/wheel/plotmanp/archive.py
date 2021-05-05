import contextlib
import subprocess

import psutil
from . import manager, plot_util


# TODO : write-protect and delete-protect archived plots

def compute_priority(phase, gb_free, n_plots):
    # All these values are designed around dst buffer dirs of about
    # ~2TB size and containing k32 plots.  TODO: Generalize, and
    # rewrite as a sort function.

    priority = 50

    # To avoid concurrent IO, we should not touch drives that
    # are about to receive a new plot.  If we don't know the phase,
    # ignore.
    if (phase[0] and phase[1]):
        if (phase == (3, 4)):
            priority -= 4
        elif (phase == (3, 5)):
            priority -= 8
        elif (phase == (3, 6)):
            priority -= 16
        elif (phase >= (3, 7)):
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
              (arch_cfg.rsyncd_user, arch_cfg.rsyncd_host, arch_cfg.rsyncd_path))
    with subprocess.Popen(df_cmd, shell=True, stdout=subprocess.PIPE) as proc:
        for line in proc.stdout.readlines():
            fields = line.split()
            if fields[3] == b'-':
                # not actually mounted
                continue
            freebytes = int(fields[3][:-1]) * 1024  # Strip the final 'K'
            archdir = (fields[5]).decode('ascii')
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

    for d in dir_cfg.dst:
        ph = dir2ph.get(d, (0, 0))
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
        return (False, 'No free archive dirs found.')

    archdir = ''
    available = [(d, space) for (d, space) in archdir_freebytes.items() if
                 space > 1.2 * plot_util.get_k32_plotsize()]
    if len(available) > 0:
        index = min(dir_cfg.archive.index, len(available) - 1)
        (archdir, freespace) = sorted(available)[index]

    if not archdir:
        return (False, 'No archive directories found with enough free space')

    msg = 'Found %s with ~%d GB free' % (archdir, freespace / plot_util.GB)

    bwlimit = dir_cfg.archive.rsyncd_bwlimit
    throttle_arg = ('--bwlimit=%d' % bwlimit) if bwlimit else ''
    cmd = ('rsync %s --remove-source-files -P %s %s' %
           (throttle_arg, chosen_plot, rsync_dest(dir_cfg.archive, archdir)))

    return (True, cmd)
