import contextlib
import functools
import os
import glob
import time
from datetime import datetime
import typing

import attr
import click
import psutil

import plotman.errors
if typing.TYPE_CHECKING:
    import plotman.errors


def job_phases_for_tmpdir(d: str, all_jobs: typing.List["Job"]) -> typing.List["Phase"]:
    '''Return phase 2-tuples for jobs running on tmpdir d'''
    return sorted([j.progress() for j in all_jobs if os.path.normpath(j.plotter.common_info().tmpdir) == os.path.normpath(d)])

def job_phases_for_dstdir(d: str, all_jobs: typing.List["Job"]) -> typing.List["Phase"]:
    '''Return phase 2-tuples for jobs outputting to dstdir d'''
    return sorted([j.progress() for j in all_jobs if os.path.normpath(j.plotter.common_info().dstdir) == os.path.normpath(d)])


@attr.frozen
class ParsedChiaPlotsCreateCommand:
    error: typing.Optional[click.ClickException]
    help: bool
    parameters: typing.Dict[str, object]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False

        return (
            type(self.error) == type(other.error)
            and str(self.error) == str(other.error)
            and self.help == other.help
            and self.parameters == other.parameters
        )


@functools.total_ordering
@attr.frozen(order=False)
class Phase:
    major: int = 0
    minor: int = 0
    known: bool = True

    def __lt__(self, other: "Phase") -> bool:
        return (
            (not self.known, self.major, self.minor)
            < (not other.known, other.major, other.minor)
        )

    @classmethod
    def from_tuple(cls, t: typing.Tuple[typing.Optional[int], typing.Optional[int]]) -> "Phase":
        if len(t) != 2:
            raise Exception(f'phase must be created from 2-tuple: {t!r}')

        if None in t and not t[0] is t[1]:
            raise Exception(f'phase can not be partially known: {t!r}')

        if t[0] is None:
            return cls(known=False)

        return cls(major=t[0], minor=t[1])  # type: ignore[arg-type]

    @classmethod
    def list_from_tuples(
        cls,
        l: typing.Sequence[typing.Tuple[typing.Optional[int], typing.Optional[int]]],
    ) -> typing.List["Phase"]:
        return [cls.from_tuple(t) for t in l]

    def __str__(self) -> str:
        if not self.known:
            return '?:?'
        return f'{self.major}:{self.minor}'

# TODO: be more principled and explicit about what we cache vs. what we look up
# dynamically from the logfile
class Job:
    'Represents a plotter job'

    plotter: "plotman.plotters.Plotter"

    logfile: str = ''
    job_id: int = 0
    proc: psutil.Process

    @classmethod
    def get_running_jobs(
        cls,
        logroot: str,
        cached_jobs: typing.Sequence["Job"] = (),
    ) -> typing.List["Job"]:
        '''Return a list of running plot jobs.  If a cache of preexisting jobs is provided,
           reuse those previous jobs without updating their information.  Always look for
           new jobs not already in the cache.'''
        jobs: typing.List[Job] = []
        cached_jobs_by_pid = { j.proc.pid: j for j in cached_jobs }

        with contextlib.ExitStack() as exit_stack:
            processes = []

            pids = set()
            ppids = set()

            for process in psutil.process_iter():
                # Ignore processes which most likely have terminated between the time of
                # iteration and data access.
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    exit_stack.enter_context(process.oneshot())
                    # TODO: handle import loop
                    import plotman.plotters
                    if plotman.plotters.is_plotting_command_line(process.cmdline()):
                        ppids.add(process.ppid())
                        pids.add(process.pid)
                        processes.append(process)

            # https://github.com/ericaltendorf/plotman/pull/418
            # The experimental Chia GUI .deb installer launches plots
            # in a manner that results in a parent and child process
            # that both share the same command line and, as such, are
            # both identified as plot processes.  Only the child is
            # really plotting.  Filter out the parent.

            wanted_pids = pids - ppids

            wanted_processes = [
                process
                for process in processes
                if process.pid in wanted_pids
            ]

            for proc in wanted_processes:
                with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    if proc.pid in cached_jobs_by_pid.keys():
                        jobs.append(cached_jobs_by_pid[proc.pid])  # Copy from cache
                    else:
                        with proc.oneshot():
                            command_line = list(proc.cmdline())
                            if len(command_line) == 0:
                                # https://github.com/ericaltendorf/plotman/issues/610
                                continue
                            # TODO: handle import loop
                            import plotman.plotters
                            plotter_type = plotman.plotters.get_plotter_from_command_line(
                                command_line=command_line,
                            )
                            plotter = plotter_type()
                            plotter.parse_command_line(command_line=command_line, cwd=proc.cwd())

                            if plotter.parsed_command_line is None:
                                continue
                            if plotter.parsed_command_line.error is not None:
                                continue
                            if plotter.parsed_command_line.help:
                                continue

                            job = cls(
                                proc=proc,
                                # parsed_command=plotter.parsed_command_line,
                                plotter=plotter,
                                logroot=logroot,
                            )
                            # TODO: stop reloading every time...
                            with open(job.logfile, 'rb') as f:
                                r = f.read()
                            job.plotter.update(chunk=r)
                            jobs.append(job)

        return jobs


    def __init__(
        self,
        proc: psutil.Process,
        plotter: "plotman.plotters.Plotter",
        # parsed_command: ParsedChiaPlotsCreateCommand,
        logroot: str,
    ) -> None:
        '''Initialize from an existing psutil.Process object.  must know logroot in order to understand open files'''
        self.proc = proc
        self.plotter = plotter

        # Find logfile (whatever file is open under the log root).  The
        # file may be open more than once, e.g. for STDOUT and STDERR.
        for f in self.proc.open_files():
            if logroot in f.path:
                if self.logfile:
                    assert self.logfile == f.path
                else:
                    self.logfile = f.path
                break

    def progress(self) -> Phase:
        '''Return a 2-tuple with the job phase and subphase (by reading the logfile)'''
        return self.plotter.common_info().phase

    def plot_id_prefix(self) -> str:
        plot_id = self.plotter.common_info().plot_id
        if plot_id is None:
            return '--------'

        return plot_id[:8]

    # TODO: make this more useful and complete, and/or make it configurable
    def status_str_long(self) -> str:
        # TODO: get the rest of this filled out
        info = self.plotter.common_info()
        return '{plot_id}\npid:{pid}\ntmp:{tmp}\ndst:{dst}\nlogfile:{logfile}'.format(
            plot_id = info.plot_id,
            pid = self.proc.pid,
            tmp = info.tmpdir,
            dst = info.dstdir,
            logfile = self.logfile
            )
        # return '{plot_id}\nk={k} r={r} b={b} u={u}\npid:{pid}\ntmp:{tmp}\ntmp2:{tmp2}\ndst:{dst}\nlogfile:{logfile}'.format(
        #     plot_id = info.plot_id,
        #     # k = self.k,
        #     # r = self.r,
        #     # b = self.b,
        #     # u = self.u,
        #     pid = self.proc.pid,
        #     tmp = info.tmpdir,
        #     # tmp2 = self.tmp2dir,
        #     dst = info.dstdir,
        #     logfile = self.logfile
        #     )

    def print_logs(self, follow: bool = False) -> None:
        with open(self.logfile, 'r') as f:
            if follow:
                line = ''
                while True:
                    tmp = f.readline()
                    if tmp is not None:
                        line += tmp
                        if line.endswith("\n"):
                            print(line.rstrip('\n'))
                            line = ''
                    else:
                        time.sleep(0.1)
            else:
                print(f.read())

    def to_dict(self) -> typing.Dict[str, object]:
        '''Exports important information as dictionary.'''
        info = self.plotter.common_info()
        # TODO: get the rest of this filled out
        return dict(
            plot_id=self.plot_id_prefix(),
            # k=self.k,
            tmp_dir=info.tmpdir,
            dst_dir=info.dstdir,
            progress=str(self.progress()),
            tmp_usage=self.get_tmp_usage(),
            pid=self.proc.pid,
            run_status=self.get_run_status(),
            mem_usage=self.get_mem_usage(),
            time_wall=self.get_time_wall(),
            time_user=self.get_time_user(),
            time_sys=self.get_time_sys(),
            time_iowait=self.get_time_iowait()
        )


    def get_mem_usage(self) -> int:
        # Total, inc swapped
        return self.proc.memory_info().vms  # type: ignore[no-any-return]

    def get_tmp_usage(self) -> int:
        total_bytes = 0
        info = self.plotter.common_info()
        with contextlib.suppress(FileNotFoundError):
            # The directory might not exist at this name, or at all, anymore
            with os.scandir(info.tmpdir) as it:
                for entry in it:
                    if info.plot_id is not None and info.plot_id in entry.name:
                        with contextlib.suppress(FileNotFoundError):
                            # The file might disappear; this being an estimate we don't care
                            total_bytes += entry.stat().st_size
        return total_bytes

    def get_run_status(self) -> str:
        '''Running, suspended, etc.'''
        status = self.proc.status()
        if status == psutil.STATUS_RUNNING:
            return 'RUN'
        elif status == psutil.STATUS_SLEEPING:
            return 'SLP'
        elif status == psutil.STATUS_DISK_SLEEP:
            return 'DSK'
        elif status == psutil.STATUS_STOPPED:
            return 'STP'
        else:
            return self.proc.status()  # type: ignore[no-any-return]

    def get_time_wall(self) -> int:
        create_time = datetime.fromtimestamp(self.proc.create_time())
        return int((datetime.now() - create_time).total_seconds())

    def get_time_user(self) -> int:
        return int(self.proc.cpu_times().user)

    def get_time_sys(self) -> int:
        return int(self.proc.cpu_times().system)

    def get_time_iowait(self) -> typing.Optional[int]:
        cpu_times = self.proc.cpu_times()
        iowait = getattr(cpu_times, 'iowait', None)
        if iowait is None:
            return None

        return int(iowait)

    def suspend(self, reason: str = '') -> None:
        self.proc.suspend()
        self.status_note = reason

    def resume(self) -> None:
        self.proc.resume()

    def get_temp_files(self) -> typing.Set[str]:
        # Prevent duplicate file paths by using set.
        temp_files = set([])

        info = self.plotter.common_info()
        for dir in [info.tmpdir, info.tmp2dir, info.dstdir]:
            if dir is not None:
                temp_files.update(glob.glob(os.path.join(dir, f"plot-*-{info.plot_id}*.tmp")))

        return temp_files

    def cancel(self) -> None:
        'Cancel an already running job'
        # We typically suspend the job as the first action in killing it, so it
        # doesn't create more tmp files during death.  However, terminate() won't
        # complete if the job is supsended, so we also need to resume it.
        # TODO: check that this is best practice for killing a job.
        self.proc.resume()
        self.proc.terminate()
