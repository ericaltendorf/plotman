#!/usr/bin/python3
#
# Warning: lsof may block or deadlock if NFS host is unreachable; avoid
# using this tool if your plotting processes are touching NFS files.

from datetime import datetime
from subprocess import call

import os
import re
import threading
import random
import readline          # For nice CLI
import sys

# Plotman libraries
from job import Job
import manager

# Constants
MIN = 60    # Seconds
HR = 3600   # Seconds

#
# Configuration values.  TODO: factor these out into either a config
# file or make them command line parameters.
#

# Plotting scheduling parameters
tmpdir_stagger = 170 * MIN        # Don't run a job on a particular temp dir more often than this.
global_stagger = 40 * MIN         # Global min; don't run any jobs more often than this.
daemon_sleep_time = 5 * MIN       # How often the daemon wakes to consider starting a new plot job

# Directories
tmpdirs = [ '/mnt/tmp/' + d for d in [ '00', '01', '02', '03' ] ]
tmpdir2 = '/mnt/tmp/a/'
logdir = '/home/eric/chia/logs'
dstdirs = [ '/home/eric/chia/plots/000', '/home/eric/chia/plots/001' ]


if __name__ == "__main__":
    random.seed()

    print('...scanning process tables')
    jobs = Job.get_running_jobs(logdir)

    print('...starting background daemon')
    # TODO: don't start the background daemon automatically; make it user startable/stoppable
    daemon = threading.Thread(target=manager.daemon_thread,
            args=(logdir, tmpdirs, tmpdir2, dstdirs, tmpdir_stagger, global_stagger, daemon_sleep_time),
            daemon=True)
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
                print(manager.status_report(jobs))
                continue

            elif cmd == 'x':
                break

            elif cmd == 'd' or cmd == 'f' or cmd == 'k' or cmd == 'p' or cmd == 'r':
                if (len(args) != 1):
                    print('Need to supply job id spec')
                    continue

                id_spec = args[0]
                selected = manager.select_jobs_by_partial_id(jobs, id_spec)
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

