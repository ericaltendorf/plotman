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

class Log:
    def __init__(self):
        self.entries = []
        self.cur_pos = 0

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

    def get_cur_pos(self):
        return self.cur_pos

    def cur_slice(self, num_entries):
        '''Return num_entries log entries up to the current slice position'''
        return self.entries[max(0, self.cur_pos - num_entries) : self.cur_pos]

    def fill_log(self):
        '''Add a bunch of stuff to the log.  Useful for testing.'''
        for i in range(100):
            self.log('Log line %d' % i)

def plotting_status_msg(active, status):
    if active:
        return '(active) ' + status
    else:
        return '(inactive) ' + status

def archiving_status_msg(configured, active, status):
    if configured:
        if active:
            return '(active) ' + status
        else:
            return '(inactive) ' + status
    else:
        return '(not configured)'

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
    archiving_configured = 'archive' in dir_cfg
    archiving_active = archiving_configured

    (n_rows, n_cols) = map(int, stdscr.getmaxyx())

    # Page layout.  Currently requires at least ~40 rows.
    # TODO: make everything dynamically resize to best use available space
    header_height = 3
    jobs_height = 10
    dirs_height = 14
    logscreen_height = n_rows - (header_height + jobs_height + dirs_height)

    header_pos = 0
    jobs_pos = header_pos + header_height
    dirs_pos = jobs_pos + jobs_height
    logscreen_pos = dirs_pos + dirs_height

    plotting_status = '<startup>'    # todo rename these msg?
    archiving_status = '<startup>'

    refresh_period = int(sched_cfg['polling_time_s'])

    stdscr.nodelay(True)  # make getch() non-blocking
    stdscr.timeout(2000)

    header_win = curses.newwin(header_height, n_cols, header_pos, 0)
    log_win = curses.newwin(logscreen_height, n_cols, logscreen_pos, 0)
    jobs_win = curses.newwin(jobs_height, n_cols, jobs_pos, 0)
    dirs_win = curses.newwin(dirs_height, n_cols, dirs_pos, 0)

    jobs = Job.get_running_jobs(dir_cfg['log'])
    last_refresh = datetime.datetime.now()

    pressed_key = ''   # For debugging

    while True:

        # TODO: handle resizing.  Need to (1) figure out how to reliably get
        # the terminal size -- the recommended method doesn't seem to work:
        #    (n_rows, n_cols) = [int(v) for v in stdscr.getmaxyx()]
        # Consider instead:
        #    ...[int(v) for v in os.popen('stty size', 'r').read().split()]
        # and then (2) implement the logic to resize all the subwindows as above

        stdscr.clear()
        linecap = n_cols - 1
        logscreen_height = n_rows - (header_height + jobs_height + dirs_height)

        elapsed = (datetime.datetime.now() - last_refresh).total_seconds() 

        # A full refresh scans for and reads info for running jobs from
        # scratch (i.e., reread their logfiles).  Otherwise we'll only
        # initialize new jobs, and mostly rely on cached info.
        do_full_refresh = elapsed >= refresh_period

        if not do_full_refresh:
            jobs = Job.get_running_jobs(dir_cfg['log'], cached_jobs=jobs)

        else:
            last_refresh = datetime.datetime.now()
            jobs = Job.get_running_jobs(dir_cfg['log'])

            if plotting_active:
                (started, msg) = manager.maybe_start_new_plot(dir_cfg, sched_cfg, plotting_cfg)
                if (started):
                    log.log(msg)
                    plotting_status = '<just started job>'
                    jobs = Job.get_running_jobs(dir_cfg['log'], cached_jobs=jobs)
                else:
                    plotting_status = msg

            if archiving_configured and archiving_active:
                # Look for running archive jobs.  Be robust to finding more than one
                # even though the scheduler should only run one at a time.
                arch_jobs = archive.get_running_archive_jobs(dir_cfg['archive'])
                if arch_jobs:
                    archiving_status = 'pid: ' + ', '.join(map(str, arch_jobs))
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
        if archiving_configured:
            arch_prefix = dir_cfg['archive']['rsyncd_path']

        # Header
        header_win.addnstr(0, 0, 'Plotman', linecap, curses.A_BOLD)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        refresh_msg = "now" if do_full_refresh else f"{int(elapsed)}s/{refresh_period}"
        header_win.addnstr(f" {timestamp} (refresh {refresh_msg})", linecap)
        header_win.addnstr('  |  <P>lotting: ', linecap, curses.A_BOLD)
        header_win.addnstr(
                plotting_status_msg(plotting_active, plotting_status), linecap)
        header_win.addnstr(' <A>rchival: ', linecap, curses.A_BOLD)
        header_win.addnstr(
                archiving_status_msg(archiving_configured,
                    archiving_active, archiving_status), linecap) 

        # Oneliner progress display
        header_win.addnstr(1, 0, 'Jobs (%d): ' % len(jobs), linecap)
        header_win.addnstr('[' + reporting.job_viz(jobs) + ']', linecap)

        # These are useful for debugging.
        # header_win.addnstr('  term size: (%d, %d)' % (n_rows, n_cols), linecap)  # Debuggin
        # if pressed_key:
            # header_win.addnstr(' (keypress %s)' % str(pressed_key), linecap)
        header_win.addnstr(2, 0, 'Prefixes:', linecap, curses.A_BOLD)
        header_win.addnstr('  tmp=', linecap, curses.A_BOLD)
        header_win.addnstr(tmp_prefix, linecap)
        header_win.addnstr('  dst=', linecap, curses.A_BOLD)
        header_win.addnstr(dst_prefix, linecap)
        if archiving_configured:
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

        if archiving_configured:
            arch_report = reporting.arch_dir_report(
                archive.get_archdir_freebytes(dir_cfg['archive']), n_cols, arch_prefix)
            if not arch_report:
                arch_report = '<no archive dir info>'
        else:
            arch_report = '<archiving not configured>'
            
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
        log_win.addnstr(0, 0, ('Log: %d (<up>/<down>/<end> to scroll)\n' % log.get_cur_pos() ),
                linecap, curses.A_REVERSE)
        for i, logline in enumerate(log.cur_slice(logscreen_height - 1)):
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

        key = stdscr.getch()
        if key == curses.KEY_UP:
            log.shift_slice(-1)
            pressed_key = 'up'
        elif key == curses.KEY_DOWN:
            log.shift_slice(1)
            pressed_key = 'dwn'
        elif key == curses.KEY_END:
            log.shift_slice_to_end()
            pressed_key = 'end'
        elif key == ord('p'):
            plotting_active = not plotting_active
            pressed_key = 'p'
        elif key == ord('a'):
            archiving_active = not archiving_active
            pressed_key = 'a'
        elif key == ord('q'):
            break
        else:
            pressed_key = key


def run_interactive():
    locale.setlocale(locale.LC_ALL, '')
    code = locale.getpreferredencoding()
    # Then use code as the encoding for str.encode() calls.

    curses.wrapper(curses_main)
