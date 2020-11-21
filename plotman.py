#!/usr/bin/python3

from datetime import datetime
from subprocess import call

import argparse
import os
import re
import threading
import random
import readline          # For nice CLI
import sys
import yaml

# Plotman libraries
from job import Job
import analyzer
import manager

class PlotmanArgParser:
    def add_idprefix_arg(self, subparser):
        subparser.add_argument(
                'idprefix',
                type=str,
                nargs='+',
                help='disambiguating prefix of plot ID')

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Chia plotting manager.')
        subparsers = parser.add_subparsers(dest='cmd')

        p_status = subparsers.add_parser('status', help='show current plotting status')

        p_status = subparsers.add_parser('daemon', help='run plotting daemon')

        p_details = subparsers.add_parser('details', help='show details for job')
        self.add_idprefix_arg(p_details)

        p_files = subparsers.add_parser('files', help='show temp files associated with job')
        self.add_idprefix_arg(p_files)

        p_kill = subparsers.add_parser('kill', help='kill job (and cleanup temp files)')
        self.add_idprefix_arg(p_kill)

        p_suspend = subparsers.add_parser('suspend', help='suspend job')
        self.add_idprefix_arg(p_suspend)

        p_resume = subparsers.add_parser('resume', help='resume suspended job')
        self.add_idprefix_arg(p_resume)

        p_analyze = subparsers.add_parser('analyze', help='analyze timing stats of completed jobs')
        p_analyze.add_argument('logfile', type=str, nargs='+', help='logfile(s) to analyze')

        args = parser.parse_args()
        return args


if __name__ == "__main__":
    random.seed()

    pm_parser = PlotmanArgParser()
    args = pm_parser.parse_args()
    
    print('...reading config file')
    with open('config.yaml', 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    dir_cfg = cfg['directories']
    scheduling_cfg = cfg['scheduling']
    plotting_cfg = cfg['plotting']

    #
    # Stay alive, spawning plot jobs
    # TODO: not really a daemon now
    #
    if args.cmd == 'daemon':
        print('...starting background daemon')
        # daemon = threading.Thread(target=manager.daemon_thread,
                # args=(dir_cfg, scheduling_cfg, plotting_cfg),
                # daemon=True)
        # daemon.start()
        manager.daemon_thread(dir_cfg, scheduling_cfg, plotting_cfg)
        sys.exit(0)
    
    #
    # Analysis of completed jobs
    #
    if args.cmd == 'analyze':
        analyzer = analyzer.LogAnalyzer()
        analyzer.analyze(args.logfile)
    
    #
    # Job control commands
    #
    print('...scanning process tables')
    jobs = Job.get_running_jobs(dir_cfg['log'])
    job = None

    if args.cmd in [ 'details', 'files', 'kill', 'suspend', 'resume' ]:
        print(args)
        # TODO: allow multiple idprefixes, not just take the first
        selected = manager.select_jobs_by_partial_id(jobs, args.idprefix[0])
        if (len(selected) == 0):
            print('Error: %s matched no jobs.' % id_spec)
        elif len(selected) > 1:
            print('Error: "%s" matched multiple jobs:' % id_spec)
            for j in selected:
                print('  %s' % j.plot_id)
        else:
            job = selected[0]

    if args.cmd == 'status':
        print(manager.status_report(jobs, dir_cfg['tmp']))

    elif args.cmd == 'details':
        print(job.status_str_long())

    elif args.cmd == 'files':
        temp_files = job.get_temp_files()
        for f in temp_files:
            print('  %s' % f)

    elif args.cmd == 'kill':
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

    elif args.cmd == 'suspend':
        print('Suspending ' + job.plot_id)
        job.suspend()
    elif args.cmd == 'resume':
        print('Resuming ' + job.plot_id)
        job.resume()

