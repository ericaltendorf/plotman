#!/usr/bin/env python3

import argparse
import os
import random
import re
import readline  # For nice CLI
import sys
import threading
import time
from datetime import datetime
from subprocess import call

import yaml

# Plotman libraries
from plotman import analyzer, archive, interactive, manager, plot_util, reporting
from plotman.job import Job


class PlotmanArgParser:
    def add_idprefix_arg(self, subparser):
        subparser.add_argument(
                'idprefix',
                type=str,
                nargs='+',
                help='disambiguating prefix of plot ID')

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Chia plotting manager.')
        sp = parser.add_subparsers(dest='cmd')

        p_status = sp.add_parser('version', help='print the version')

        p_status = sp.add_parser('status', help='show current plotting status')
 
        p_dirs = sp.add_parser('dirs', help='show directories info')

        p_interactive = sp.add_parser('interactive', help='run interactive control/montioring mode')

        p_dst_sch = sp.add_parser('dsched', help='print destination dir schedule')

        p_plot = sp.add_parser('plot', help='run plotting loop')

        p_archive = sp.add_parser('archive',
                help='move completed plots to farming location')

        p_details = sp.add_parser('details', help='show details for job')
        self.add_idprefix_arg(p_details)

        p_files = sp.add_parser('files', help='show temp files associated with job')
        self.add_idprefix_arg(p_files)

        p_kill = sp.add_parser('kill', help='kill job (and cleanup temp files)')
        self.add_idprefix_arg(p_kill)

        p_suspend = sp.add_parser('suspend', help='suspend job')
        self.add_idprefix_arg(p_suspend)

        p_resume = sp.add_parser('resume', help='resume suspended job')
        self.add_idprefix_arg(p_resume)

        p_analyze = sp.add_parser('analyze',
                help='analyze timing stats of completed jobs')
        p_analyze.add_argument('--bytmp',
                action='store_true',
                help='slice by tmp dirs')
        p_analyze.add_argument('--bybitfield',
                action='store_true',
                help='slice by bitfield/non-bitfield sorting')
        p_analyze.add_argument('logfile', type=str, nargs='+',
                help='logfile(s) to analyze')

        args = parser.parse_args()
        return args

def get_term_width():
    columns = 0
    try:
        (rows, columns) = os.popen('stty size', 'r').read().split()
        columns = int(columns)
    except:
        columns = 120  # 80 is typically too narrow.  TODO: make a command line arg.
    return columns

def main():
    random.seed()

    pm_parser = PlotmanArgParser()
    args = pm_parser.parse_args()

    if args.cmd == 'version':
        import pkg_resources
        print(pkg_resources.get_distribution('plotman'))
        exit()
    
    with open('config.yaml', 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    dir_cfg = cfg['directories']
    sched_cfg = cfg['scheduling']
    plotting_cfg = cfg['plotting']

    #
    # Stay alive, spawning plot jobs
    #
    if args.cmd == 'plot':
        print('...starting plot loop')
        while True:
            wait_reason = manager.maybe_start_new_plot(dir_cfg, sched_cfg, plotting_cfg)

            # TODO: report this via a channel that can be polled on demand, so we don't spam the console
            sleep_s = int(sched_cfg['polling_time_s'])
            if wait_reason:
                print('...sleeping %d s: %s' % (sleep_s, wait_reason))

            time.sleep(sleep_s)
    
    #
    # Analysis of completed jobs
    #
    elif args.cmd == 'analyze':
        analyzer = analyzer.LogAnalyzer()
        analyzer.analyze(args.logfile, args.bytmp, args.bybitfield)

    else:
        # print('...scanning process tables')
        jobs = Job.get_running_jobs(dir_cfg['log'])

        # Status report
        if args.cmd == 'status':
            print(reporting.status_report(jobs, get_term_width()))

        # Directories report
        elif args.cmd == 'dirs':
            print(reporting.dirs_report(jobs, dir_cfg, sched_cfg, get_term_width()))

        elif args.cmd == 'interactive':
            interactive.run_interactive()

        # Start running archival
        elif args.cmd == 'archive':
            print('...starting archive loop')
            firstit = True
            while True:
                if not firstit:
                    print('Sleeping 60s until next iteration...')
                    time.sleep(60)
                    jobs = Job.get_running_jobs(dir_cfg['log'])
                firstit = False
                archive.archive(dir_cfg, jobs)

        # Debugging: show the destination drive usage schedule
        elif args.cmd == 'dsched':
            dstdirs = dir_cfg['dst']
            for (d, ph) in manager.dstdirs_to_furthest_phase(jobs).items():
                print('  %s : %s' % (d, str(ph)))
        
        #
        # Job control commands
        #
        elif args.cmd in [ 'details', 'files', 'kill', 'suspend', 'resume' ]:
            print(args)

            selected = []

            # TODO: clean up treatment of wildcard
            if args.idprefix[0] == 'all':
                selected = jobs
            else:
                # TODO: allow multiple idprefixes, not just take the first
                selected = manager.select_jobs_by_partial_id(jobs, args.idprefix[0])
                if (len(selected) == 0):
                    print('Error: %s matched no jobs.' % id_spec)
                elif len(selected) > 1:
                    print('Error: "%s" matched multiple jobs:' % id_spec)
                    for j in selected:
                        print('  %s' % j.plot_id)
                    selected = []

            for job in selected:
                if args.cmd == 'details':
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
