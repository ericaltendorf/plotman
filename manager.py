#!/usr/bin/python3
#
# Warning: lsof may block or deadlock if NFS host is unreachable; avoid
# using this tool if your plotting processes are touching NFS files.

from datetime import datetime
from subprocess import call

import logging
import os
import re
import threading
import time
import random
import readline          # For nice CLI
import sys
import texttable as tt   # from somewhere?

# Plotman libraries
from job import Job

# Constants
MIN = 60    # Seconds
HR = 3600   # Seconds
MAX_AGE = 1000_000_000   # Arbitrary large number of seconds

# Plotting scheduling parameters
tmpdir_stagger = 170 * MIN        # Don't run a job on a particular temp dir more often than this.
global_stagger = 40 * MIN         # Global min; don't run any jobs more often than this.
daemon_sleep_time = 5 * MIN       # How often the daemon wakes to consider starting a new plot job

# Plot parameters
kval = 32
n_threads = 12                    # Threads per job
n_buckets = 128                   # Number of buckets to split data into
job_buffer = 4550                 # Per job memory

# Directories
tmpdirs = [ '/mnt/tmp/' + d for d in [ '00', '01', '02', '03' ] ]
tmpdir2 = '/mnt/tmp/a/'
logdir = '/home/eric/chia/logs'
dstdirs = [ '/home/eric/chia/plots/000', '/home/eric/chia/plots/001' ]


def daemon_thread(name):
    'Daemon thread for automatically starting jobs and monitoring job status'

    while True:
        jobs = Job.get_running_jobs(logdir)

        # TODO: Factor out some of this complex logic, clean it up, add unit tests
        
        # Identify the most recent time a tmp had a job start (its "age")
        tmpdir_age = {}
        for d in tmpdirs:
            d_jobs = [j for j in jobs if j.tmpdir == d]
            if d_jobs:
                tmpdir_age[d] = min(d_jobs, key=Job.get_time_wall, default=MAX_AGE).get_time_wall()
            else:
                tmpdir_age[d] = MAX_AGE

        # We should only plot if the youngest tmpdir is old enough
        if (min(tmpdir_age.values()) > global_stagger):

            # Filter too-young tmpdirs
            tmpdir_age = { k:v for k, v in tmpdir_age.items() if v > tmpdir_stagger }

            if tmpdir_age:
                # Plot to oldest tmpdir
                tmpdir = max(tmpdir_age, key=tmpdir_age.get)

                dstdir = random.choice(dstdirs)  # TODO: Pick most empty drive?

                logfile = os.path.join(logdir, datetime.now().strftime('%Y-%m-%d-%H:%M:%S.log'))

                plot_args = ['chia', 'plots', 'create',
                        '-k', str(kval),
                        '-r', str(n_threads),
                        '-u', str(n_buckets),
                        '-b', str(job_buffer),
                        '-t', tmpdir,
                        '-2', tmpdir2,
                        '-d', dstdir ]

                plot_cmd_str = ' '.join(plot_args)
                full_cmd = '%s > %s 2>&1 &' % (plot_cmd_str, logfile)

                print('\nDaemon starting new plot job:\n%s' % full_cmd)
                call(full_cmd, shell=True)

        time.sleep(daemon_sleep_time)



def human_format(num, precision):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    return (('%.' + str(precision) + 'f%s') % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude]))

def time_format(sec, precision):
    if sec < 60:
        return '%ds' % sec
    else:
        return '%d:%02d' % (int(sec / 3600), int((sec % 3600) / 60))

def status_report(jobs):
    tab = tt.Texttable()
    headings = ['plot id', 'k', 'tmp dir', 'wall', 'phase', 'tmp', 'pid', 'stat', 'mem', 'user', 'sys', 'io']
    tab.header(headings)
    tab.set_cols_align('r' * len(headings))
    for j in sorted(jobs, key=Job.get_time_wall):
        row = [j.plot_id[:8] + '...',
               j.k,
               j.tmpdir,
               time_format(j.get_time_wall(), 1),
               '%d:%d' % j.progress(),
               human_format(j.get_tmp_usage(), 0),
               j.proc.pid,
               j.get_run_status(),
               human_format(j.get_mem_usage(), 1),
               time_format(j.get_time_user(), 1),
               time_format(j.get_time_sys(), 1),
               time_format(j.get_time_iowait(), 1)
               ]
        tab.add_row(row)

    (rows, columns) = os.popen('stty size', 'r').read().split()
    tab.set_max_width(int(columns))
    tab.set_deco(tt.Texttable.BORDER | tt.Texttable.HEADER )
    return tab.draw()
 
def select_jobs_by_partial_id(jobs, partial_id):
    selected = []
    for j in jobs:
        if j.plot_id.startswith(partial_id):
            selected.append(j)
    return selected

if __name__ == "__main__":
    random.seed()

    print('...scanning process tables')
    jobs = Job.get_running_jobs(logdir)

    print('...starting background daemon')
    # TODO: don't start the background daemon automatically; make it user startable/stoppable
    daemon = threading.Thread(target=daemon_thread, args=('foo',), daemon=True)
    daemon.start()

    print('Welcome to PlotMan.  Detected %d active plot jobs.  Type \'h\' for help.' % len(jobs))

    # TODO: use a real CLI library, or make the tool a CLI tool and use argparser.
    while True:
        cmd_line = input('\033[94mplotman> \033[0m')
        if cmd_line:
            # Re-read active jobs
            jobs = Job.get_running_jobs(logdir)

            cmd_line = cmd_line.split()
            cmd = cmd_line[0]
            args = cmd_line[1:]

            if cmd == 'h':
                print('Commands which reference a job require an unambiguous prefix of the plot id')
                print('  l            : list current jobs')
                print('  d <idprefix> : show details for a plot job')
                print('  f <idprefix> : show temp files for a job')
                print('  k <idprefix> : kill and cleanup a plot job')
                print('  p <idprefix> : pause (suspend) a plot job')
                print('  r <idprefix> : resume a plot job')
                print('  h            : help info (this message)')
                print('  x            : exit')
                continue

            elif cmd == 'l':
                print(status_report(jobs))
                continue

            elif cmd == 'x':
                break

            elif cmd == 'd' or cmd == 'f' or cmd == 'k' or cmd == 'p' or cmd == 'r':
                if (len(args) != 1):
                    print('Need to supply job id spec')
                    continue

                id_spec = args[0]
                selected = select_jobs_by_partial_id(jobs, id_spec)
                if (len(selected) == 0):
                    print('Error: %s matched no jobs.')
                    continue
                elif len(selected) > 1:
                    print('Error: "%s" matched multiple jobs:' % id_spec)
                    for j in selected:
                        print('  %s' % j.plot_id)
                    continue
                else:
                    job = selected[0]

                    # Do the real command
                    if cmd == 'd':
                        print(job.status_str_long())

                    elif cmd == 'f':
                        temp_files = job.get_temp_files()
                        for f in temp_files:
                            print('  %s' % f)

                    elif cmd == 'k':
                        # First suspend so job doesn't create new files
                        print('Pausing PID %d, plot id %s' % (job.proc.pid, job.plot_id))
                        job.suspend()

                        temp_files = job.get_temp_files()
                        print('Will kill pid %d, plot id %s' % (job.proc.pid, job.plot_id))
                        print('Will delete %d temp files' % len(temp_files))
                        conf = input('Are you sure? ("y" to confirm): ')
                        if (conf != 'y'):
                            print('canceled.  If you wish to resume the job, do so manually.')
                        else:
                            print('killing...')
                            job.cancel()
                            print('cleaing up temp files...')
                            for f in temp_files:
                                os.remove(f)

                    elif cmd == 'p':
                        print('Pausing ' + job.plot_id)
                        job.suspend()
                    elif cmd == 'r':
                        print('Resuming ' + job.plot_id)
                        job.resume()

            else:
                print('Unknown command: %s' % cmd)
                continue 

    sys.exit(0)

