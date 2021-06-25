import argparse
import datetime
import importlib
import importlib.resources
import logging
import logging.handlers
import os
import glob
import random
from shutil import copyfile
import sys
import time
import typing

import pendulum

# Plotman libraries
from plotman import analyzer, archive, configuration, interactive, manager, plot_util, reporting, csv_exporter
from plotman import resources as plotman_resources
from plotman.job import Job

class PlotmanArgParser:
    def add_idprefix_arg(self, subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument(
                'idprefix',
                type=str,
                nargs='+',
                help='disambiguating prefix of plot ID')

    def parse_args(self) -> typing.Any:
        parser = argparse.ArgumentParser(description='Chia plotting manager.')
        sp = parser.add_subparsers(dest='cmd')

        sp.add_parser('version', help='print the version')

        p_status = sp.add_parser('status', help='show current plotting status')
        p_status.add_argument("--json", action="store_true",
                help="export status report in json format")

        sp.add_parser('prometheus', help='show current plotting status in prometheus readable format')

        sp.add_parser('dirs', help='show directories info')

        p_interactive = sp.add_parser('interactive', help='run interactive control/monitoring mode')
        p_interactive.add_argument('--autostart-plotting', action='store_true', default=None, dest='autostart_plotting')
        p_interactive.add_argument('--no-autostart-plotting', action='store_false', default=None, dest='autostart_plotting')
        p_interactive.add_argument('--autostart-archiving', action='store_true', default=None, dest='autostart_archiving')
        p_interactive.add_argument('--no-autostart-archiving', action='store_false', default=None, dest='autostart_archiving')

        sp.add_parser('dsched', help='print destination dir schedule')

        sp.add_parser('plot', help='run plotting loop')

        sp.add_parser('archive', help='move completed plots to farming location')

        p_export = sp.add_parser('export', help='exports metadata from the plot logs as CSV')
        p_export.add_argument('-o', dest='save_to', default=None, type=str, help='save to file. Optional, prints to stdout by default')

        p_config = sp.add_parser('config', help='display or generate plotman.yaml configuration')
        sp_config = p_config.add_subparsers(dest='config_subcommand')
        sp_config.add_parser('generate', help='generate a default plotman.yaml file and print path')
        sp_config.add_parser('path', help='show path to current plotman.yaml file')

        p_details = sp.add_parser('details', help='show details for job')
        self.add_idprefix_arg(p_details)

        p_logs = sp.add_parser('logs', help='fetch the logs for job')

        p_logs.add_argument('-f', '--follow', action='store_true', help='Follow log output')
        self.add_idprefix_arg(p_logs)

        p_files = sp.add_parser('files', help='show temp files associated with job')
        self.add_idprefix_arg(p_files)

        p_kill = sp.add_parser('kill', help='kill job (and cleanup temp files)')
        p_kill.add_argument('-f', '--force', action='store_true', default=False, help="Don't ask for confirmation before killing the plot job")
        self.add_idprefix_arg(p_kill)

        p_suspend = sp.add_parser('suspend', help='suspend job')
        self.add_idprefix_arg(p_suspend)

        p_resume = sp.add_parser('resume', help='resume suspended job')
        self.add_idprefix_arg(p_resume)

        p_analyze = sp.add_parser('analyze', help='analyze timing stats of completed jobs')

        p_analyze.add_argument('--clipterminals',
                action='store_true',
                help='Ignore first and last plot in a logfile, useful for '
                     'focusing on the steady-state in a staggered parallel '
                     'plotting test (requires plotting  with -n>2)')
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

def get_term_width() -> int:
    try:
        (rows_string, columns_string) = os.popen('stty size', 'r').read().split()
        columns = int(columns_string)
    except:
        columns = 120  # 80 is typically too narrow.  TODO: make a command line arg.
    return columns

class Iso8601Formatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt: typing.Optional[str] = None) -> str:
        time = pendulum.from_timestamp(timestamp=record.created, tz='local')
        return time.isoformat(timespec='microseconds')

def main() -> None:
    random.seed()

    pm_parser = PlotmanArgParser()
    args = pm_parser.parse_args()

    if args.cmd == 'version':
        import pkg_resources
        print(pkg_resources.get_distribution('plotman'))
        return

    elif args.cmd == 'config':
        config_file_path = configuration.get_path()
        if args.config_subcommand == 'path':
            if os.path.isfile(config_file_path):
                print(config_file_path)
                return
            print(f"No 'plotman.yaml' file exists at expected location: '{config_file_path}'")
            print(f"To generate a default config file, run: 'plotman config generate'")
            return
        if args.config_subcommand == 'generate':
            if os.path.isfile(config_file_path):
                overwrite = None
                while overwrite not in {"y", "n"}:
                    overwrite = input(
                        f"A 'plotman.yaml' file already exists at the default location: '{config_file_path}' \n\n"
                        "\tInput 'y' to overwrite existing file, or 'n' to exit without overwrite."
                      ).lower()
                    if overwrite == 'n':
                        print("\nExited without overrwriting file")
                        return

            # Copy the default plotman.yaml (packaged in plotman/resources/) to the user's config file path,
            # creating the parent plotman file/directory if it does not yet exist
            with importlib.resources.path(plotman_resources, "plotman.yaml") as default_config:
                config_dir = os.path.dirname(config_file_path)

                os.makedirs(config_dir, exist_ok=True)
                copyfile(default_config, config_file_path)
                print(f"\nWrote default plotman.yaml to: {config_file_path}")
                return

        if not args.config_subcommand:
            print("No action requested, add 'generate' or 'path'.")
            return

    config_path = configuration.get_path()
    config_text = configuration.read_configuration_text(config_path)
    preset_target_definitions_text = importlib.resources.read_text(
        plotman_resources, "target_definitions.yaml",
    )

    cfg = configuration.get_validated_configs(config_text, config_path, preset_target_definitions_text)

    with cfg.setup():
        root_logger = logging.getLogger()
        handler = logging.handlers.RotatingFileHandler(
            backupCount=10,
            encoding='utf-8',
            filename=cfg.logging.application,
            maxBytes=10_000_000,
        )
        formatter = Iso8601Formatter(fmt='%(asctime)s: %(message)s')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
        root_logger.info('abc')

        #
        # Stay alive, spawning plot jobs
        #
        if args.cmd == 'plot':
            print('...starting plot loop')
            while True:
                wait_reason = manager.maybe_start_new_plot(cfg.directories, cfg.scheduling, cfg.plotting, cfg.logging)

                # TODO: report this via a channel that can be polled on demand, so we don't spam the console
                if wait_reason:
                    print('...sleeping %d s: %s' % (cfg.scheduling.polling_time_s, wait_reason))

                time.sleep(cfg.scheduling.polling_time_s)

        #
        # Analysis of completed jobs
        #
        elif args.cmd == 'analyze':

            analyzer.analyze(args.logfile, args.clipterminals,
                    args.bytmp, args.bybitfield)

        #
        # Exports log metadata to CSV
        #
        elif args.cmd == 'export':
            logfilenames = glob.glob(os.path.join(cfg.logging.plots, '*.plot.log'))
            if args.save_to is None:
                csv_exporter.generate(logfilenames=logfilenames, file=sys.stdout)
            else:
                with open(args.save_to, 'w', encoding='utf-8') as file:
                    csv_exporter.generate(logfilenames=logfilenames, file=file)

        else:
            jobs = Job.get_running_jobs(cfg.logging.plots)

            # Status report
            if args.cmd == 'status':
                if args.json:
                    # convert jobs list into json
                    result = reporting.json_report(jobs)
                else:
                    result = "{0}\n\n{1}\n\nUpdated at: {2}".format(
                        reporting.status_report(jobs, get_term_width()),
                        reporting.summary(jobs),
                        datetime.datetime.today().strftime("%c"),
                    )
                print(result)

            # Prometheus report
            if args.cmd == 'prometheus':
                print(reporting.prometheus_report(jobs))

            # Directories report
            elif args.cmd == 'dirs':
                print(reporting.dirs_report(jobs, cfg.directories, cfg.archiving, cfg.scheduling, get_term_width()))

            elif args.cmd == 'interactive':
                interactive.run_interactive(
                    cfg=cfg,
                    autostart_plotting=args.autostart_plotting,
                    autostart_archiving=args.autostart_archiving,
                )

            # Start running archival
            elif args.cmd == 'archive':
                if cfg.archiving is None:
                    print('archiving not configured but is required for this command')
                else:
                    print('...starting archive loop')
                    firstit = True
                    while True:
                        if not firstit:
                            print('Sleeping 60s until next iteration...')
                            time.sleep(60)
                            jobs = Job.get_running_jobs(cfg.logging.plots)
                        firstit = False

                        archiving_status, log_messages = archive.spawn_archive_process(cfg.directories, cfg.archiving, cfg.logging, jobs)
                        for log_message in log_messages:
                            print(log_message)


            # Debugging: show the destination drive usage schedule
            elif args.cmd == 'dsched':
                for (d, ph) in manager.dstdirs_to_furthest_phase(jobs).items():
                    print('  %s : %s' % (d, str(ph)))

            #
            # Job control commands
            #
            elif args.cmd in [ 'details', 'logs', 'files', 'kill', 'suspend', 'resume' ]:
                print(args)

                selected = []

                # TODO: clean up treatment of wildcard
                if args.idprefix[0] == 'all':
                    selected = jobs
                else:
                    # TODO: allow multiple idprefixes, not just take the first
                    selected = manager.select_jobs_by_partial_id(jobs, args.idprefix[0])
                    if (len(selected) == 0):
                        print('Error: %s matched no jobs.' % args.idprefix[0])
                    elif len(selected) > 1:
                        print('Error: "%s" matched multiple jobs:' % args.idprefix[0])
                        for j in selected:
                            print('  %s' % j.plot_id)
                        selected = []

                for job in selected:
                    if args.cmd == 'details':
                        print(job.status_str_long())

                    elif args.cmd == 'logs':
                        job.print_logs(args.follow)

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

                        if args.force:
                            conf = 'y'
                        else:
                            conf = input('Are you sure? ("y" to confirm): ')

                        if (conf != 'y'):
                            print('Canceled.  If you wish to resume the job, do so manually.')
                        else:
                            print('killing...')

                            job.cancel()

                            print('cleaning up temp files...')

                            for f in temp_files:
                                os.remove(f)

                    elif args.cmd == 'suspend':
                        print('Suspending ' + job.plot_id)
                        job.suspend()
                    elif args.cmd == 'resume':
                        print('Resuming ' + job.plot_id)
                        job.resume()
