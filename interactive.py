import curses
import datetime
import locale
import os
import subprocess
import threading
import yaml

from job import Job
import archive
import manager
import reporting

def window_width(window):
    return window.getmaxyx()[1]

def window_height(window):
    return window.getmaxyx()[0]

class Log:
    entries = []
    cur_pos = 0

    # TODO: store timestamp as actual timestamp indexing the messages
    def log(self, msg):
        '''Log the message and scroll to the end of the log'''
        ts = datetime.datetime.now().strftime('%m-%d %H:%M:%S')
        self.entries.append(ts + ' ' + msg)
        self.cur_pos = len(self.entries)

    def tail(self, num_entries):
        '''Return the entries at the end of the log.  Consider cur_slice() instead.'''
        return self.entries[-num_entries:]

    def shift_slice(self, offset):
        '''Positive shifts towards end, negative shifts towards beginning'''
        self.cur_pos = max(0, min(len(self.entries), self.cur_pos + offset))

    def shift_slice_to_end(self):
        self.cur_pos = len(self.entries)

    def cur_slice(self, num_entries):
        '''Return num_entries log entries up to the current slice position'''
        return self.entries[max(0, self.cur_pos - num_entries) : self.cur_pos]

def plotting_status_msg(active, status):
    if active:
        return status
    else:
        return '<inactive>'

def archiving_status_msg(active, status):
    if active:
        return status
    else:
        return '<inactive>'

def curses_main(stdscr):
    # TODO: figure out how to pass the configs in from plotman.py instead of
    # duplicating the code here.
    with open('config.yaml', 'r') as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)
    dir_cfg = cfg['directories']
    sched_cfg = cfg['scheduling']
    plotting_cfg = cfg['plotting']

    log = Log()

    plotting_active = True
    archiving_active = True

    (n_rows, n_cols) = map(int, stdscr.getmaxyx())

    # Page layout.  Currently requires at least ~40 rows.
    # TODO: make everything dynamically resize to best use available space
    header_height = 2
    jobs_height = 10
    dirs_height = 14
    logscreen_height = n_rows - (header_height + jobs_height + dirs_height)

    # For testing. TODO: remove
    # for i in range(100):
        # log.log('Log line %d' % i)

    header_pos = 0
    jobs_pos = header_pos + header_height
    dirs_pos = jobs_pos + jobs_height
    logscreen_pos = dirs_pos + dirs_height

    plotting_status = '<startup>'    # todo rename these msg?
    archiving_status = '<startup>'

    refresh_period = int(sched_cfg['polling_time_s'])

    stdscr.timeout(5000)  # this doesn't seem to do anything....

    header_win = curses.newwin(header_height, n_cols, header_pos, 0)
    log_win = curses.newwin(logscreen_height, n_cols, logscreen_pos, 0)
    jobs_win = curses.newwin(jobs_height, n_cols, jobs_pos, 0)
    dirs_win = curses.newwin(dirs_height, n_cols, dirs_pos, 0)

    jobs = Job.get_running_jobs(dir_cfg['log'])
    last_refresh = datetime.datetime.now()

    while True:

        # todo: none of this resizing works
        (n_rows, n_cols) = map(int, stdscr.getmaxyx())
        stdscr.clear()
        curses.resizeterm(n_rows, n_cols)
        linecap = n_cols - 1
        logscreen_height = n_rows - (header_height + jobs_height + dirs_height)

        elapsed = (datetime.datetime.now() - last_refresh).total_seconds() 
        if (elapsed < refresh_period):
            # Lightweight; does virtually no work if there are no new jobs.
            jobs = Job.get_running_jobs_w_cache(dir_cfg['log'], jobs)

        else:
            # Full refresh
            jobs = Job.get_running_jobs(dir_cfg['log'])
            last_refresh = datetime.datetime.now()

            if plotting_active:
                (started, msg) = manager.maybe_start_new_plot(dir_cfg, sched_cfg, plotting_cfg)
                if (started):
                    log.log(msg)
                    plotting_status = '<just started plot>'
                    jobs = Job.get_running_jobs_w_cache(dir_cfg['log'], jobs)
                else:
                    plotting_status = msg

            if archiving_active:
                # Look for running archive jobs
                arch_jobs = archive.get_running_archive_jobs(dir_cfg['archive'])
                if arch_jobs:
                    archiving_status = 'active pids ' + ', '.join(map(str, arch_jobs))
                else:
                    (should_start, status_or_cmd) = archive.archive(dir_cfg, jobs)
                    if not should_start:
                        archiving_status = status_or_cmd
                    else:
                        cmd = status_or_cmd
                        log.log('Starting archive: ' + cmd)

                        # TODO: do something useful with output instead of DEVNULL
                        p = subprocess.Popen(cmd,
                                shell=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT,
                                start_new_session=True)

        # Directory prefixes, for abbreviation
        tmp_prefix = os.path.commonpath(dir_cfg['tmp'])
        dst_prefix = os.path.commonpath(dir_cfg['dst'])
        arch_prefix = dir_cfg['archive']['rsyncd_path']

        # Render
        stdscr.clear()

        # Header
        header_win.addnstr(0, 0, 'Plotman', linecap, curses.A_BOLD)
        header_win.addnstr(' %s (refresh %ds/%ds)' %
                (datetime.datetime.now().strftime("%H:%M:%S"), elapsed, refresh_period),
                linecap)
        header_win.addnstr('  |  Plotting: ', linecap, curses.A_BOLD)
        header_win.addnstr(
                plotting_status_msg(plotting_active, plotting_status), linecap)
        header_win.addnstr(' Archival: ', linecap, curses.A_BOLD)
        header_win.addnstr(
                archiving_status_msg(archiving_active, archiving_status), linecap) 
        header_win.addnstr('  term size: (%d, %d)' % (n_rows, n_cols), linecap)  # Debuggin
        header_win.addnstr(1, 0, 'Prefixes:', linecap, curses.A_BOLD)
        header_win.addnstr('  tmp=', linecap, curses.A_BOLD)
        header_win.addnstr(tmp_prefix, linecap)
        header_win.addnstr('  dst=', linecap, curses.A_BOLD)
        header_win.addnstr(dst_prefix, linecap)
        header_win.addnstr('  archive=', linecap, curses.A_BOLD)
        header_win.addnstr(arch_prefix, linecap)
        header_win.addnstr(' (remote)', linecap)
        

        # Jobs
        jobs_win.addstr(0, 0, reporting.status_report(jobs, n_cols, jobs_height, 
            tmp_prefix, dst_prefix))
        jobs_win.chgat(0, 0, curses.A_REVERSE)

        # Dirs.  Collect reports as strings, then lay out.
        n_tmpdirs = len(dir_cfg['tmp']) 
        n_tmpdirs_half = int(n_tmpdirs / 2)
        tmp_report_1 = reporting.tmp_dir_report(
            jobs, dir_cfg['tmp'], sched_cfg, n_cols, 0, n_tmpdirs_half, tmp_prefix)
        tmp_report_2 = reporting.tmp_dir_report(
            jobs, dir_cfg['tmp'], sched_cfg, n_cols, n_tmpdirs_half, n_tmpdirs, tmp_prefix)

        dst_report = reporting.dst_dir_report(
            jobs, dir_cfg['dst'], n_cols, dst_prefix)
        arch_report = reporting.arch_dir_report(
            archive.get_archdir_freebytes(dir_cfg['archive']), n_cols, arch_prefix)
        tmp_h = max(len(tmp_report_1.splitlines()),
                    len(tmp_report_2.splitlines()))
        tmp_w = len(max(tmp_report_1.splitlines() +
                        tmp_report_2.splitlines(), key=len)) + 1
        dst_h = len(dst_report.splitlines())
        dst_w = len(max(dst_report.splitlines(), key=len)) + 1
        arch_h = len(arch_report.splitlines()) + 1
        arch_w = n_cols

        tmpwin_12_gutter = 3
        tmpwin_dstwin_gutter = 6

        # gutter = int((n_cols - (tmp_w * 2 + tmpwin_12_gutter) - dst_w) / 3)
        maxtd_h = max([tmp_h, dst_h])

        tmpwin_1 = curses.newwin(
                    tmp_h, tmp_w,
                    dirs_pos + int((maxtd_h - tmp_h) / 2), 0)
        tmpwin_1.addstr(tmp_report_1)

        tmpwin_2 = curses.newwin(
                    tmp_h, tmp_w,
                    dirs_pos + int((maxtd_h - tmp_h) / 2),
                    tmp_w + tmpwin_12_gutter)
        tmpwin_2.addstr(tmp_report_2)

        tmpwin_1.chgat(0, 0, curses.A_REVERSE)
        tmpwin_2.chgat(0, 0, curses.A_REVERSE)

        dstwin = curses.newwin(
                dst_h, dst_w,
                dirs_pos + int((maxtd_h - dst_h) / 2), 2 * tmp_w + tmpwin_12_gutter + tmpwin_dstwin_gutter)
        dstwin.addstr(dst_report)
        dstwin.chgat(0, 0, curses.A_REVERSE)

        archwin = curses.newwin(arch_h, arch_w, dirs_pos + maxtd_h, 0)
        archwin.addstr(0, 0, 'Archive dirs free space', curses.A_REVERSE)
        archwin.addstr(1, 0, arch_report)

        # Log.  Could use a pad here instead of managing scrolling ourselves, but
        # this seems easier.
        log_win.addnstr(0, 0, 'Log: (<up>/<down> to scroll, <end> to most recent)\n',
                linecap, curses.A_REVERSE)
        for i, logline in enumerate(log.tail(logscreen_height - 1)):
            log_win.addnstr(i + 1, 0, logline, linecap)

        stdscr.noutrefresh()
        header_win.noutrefresh()
        jobs_win.noutrefresh()
        tmpwin_1.noutrefresh()
        tmpwin_2.noutrefresh()
        dstwin.noutrefresh()
        archwin.noutrefresh()
        log_win.noutrefresh()
        curses.doupdate()


        # TODO: these keys aren't currently working.
        # try:
        key = stdscr.getch()
        if key == curses.KEY_UP:
            log.shift_slice(-1)
        elif key == curses.KEY_DOWN:
            log.shift_slice(1)
        elif key == curses.KEY_EOL:
            log.shift_slice_to_end()
        elif key == ord('q'):
            break
        elif key == ord('p'):
            plotting_active = not plotting_active
        elif key == ord('a'):
            archiving_active = not archiving_active
        # except curses.error:
            # pass


def run_interactive():
    locale.setlocale(locale.LC_ALL, '')
    code = locale.getpreferredencoding()
    # Then use code as the encoding for str.encode() calls.

    curses.wrapper(curses_main)
