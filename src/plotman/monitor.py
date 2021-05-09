import os
import time

import attr
import rich
import rich.layout
import rich.live
import rich.table

import plotman.configuration
import plotman.job
import plotman.plot_util
import plotman.reporting


def main():
    config_path = plotman.configuration.get_path()
    config_text = plotman.configuration.read_configuration_text(config_path)
    cfg = plotman.configuration.get_validated_configs(config_text, config_path)

    tmp_prefix = os.path.commonpath(cfg.directories.tmp)
    dst_prefix = os.path.commonpath(cfg.directories.dst)

    overall = rich.layout.Layout('overall')
    rows = [
        header_layout,
        plots_layout,
        disks_layout,
        archive_layout,
        logs_layout,
    ] = [
        rich.layout.Layout(name='header'),
        rich.layout.Layout(name='plots'),
        rich.layout.Layout(name='disks'),
        rich.layout.Layout(name='archive'),
        rich.layout.Layout(name='logs'),
    ]
    overall.split_column(*rows)

    disks_layouts = [
        tmp_layout,
        dst_layout,
    ] = [
        rich.layout.Layout(name='tmp'),
        rich.layout.Layout(name='dst'),
    ]

    disks_layout.split_row(*disks_layouts)

    jobs = []

    with rich.live.Live(overall, auto_refresh=False) as live:
        for i in range(5):
            tmp_layout.update(str(i))

            jobs = plotman.job.Job.get_running_jobs(
                cfg.directories.log,
                cached_jobs=jobs,
            )
            jobs_data = build_jobs_data(
                jobs=jobs,
                dst_prefix=dst_prefix,
                tmp_prefix=tmp_prefix,
            )

            jobs_table = build_jobs_table(jobs_data=jobs_data)
            plots_layout.update(jobs_table)

            live.refresh()
            time.sleep(1)


def job_row_ib(name):
    return attr.ib(converter=str, metadata={'name': name})


@attr.frozen
class JobRow:
    plot_id: str = job_row_ib(name='plot_id')
    k: str = job_row_ib(name='k')
    tmp_path: str = job_row_ib(name='tmp')
    dst: str = job_row_ib(name='dst')
    wall: str = job_row_ib(name='wall')
    phase: str = job_row_ib(name='phase')
    tmp_usage: str = job_row_ib(name='tmp')
    pid: str = job_row_ib(name='pid')
    stat: str = job_row_ib(name='stat')
    mem: str = job_row_ib(name='mem')
    user: str = job_row_ib(name='user')
    sys: str = job_row_ib(name='sys')
    io: str = job_row_ib(name='io')

    @classmethod
    def from_job(cls, job, dst_prefix, tmp_prefix):
        self = cls(
            plot_id=job.plot_id[:8],
            k=job.k,
            tmp_path=plotman.reporting.abbr_path(job.tmpdir, tmp_prefix),
            dst=plotman.reporting.abbr_path(job.dstdir, dst_prefix),
            wall=plotman.plot_util.time_format(job.get_time_wall()),
            phase=plotman.reporting.phase_str(job.progress()),
            tmp_usage=plotman.plot_util.human_format(job.get_tmp_usage(), 0),
            pid=job.proc.pid,
            stat=job.get_run_status(),
            mem=plotman.plot_util.human_format(job.get_mem_usage(), 1),
            user=plotman.plot_util.time_format(job.get_time_user()),
            sys=plotman.plot_util.time_format(job.get_time_sys()),
            io=plotman.plot_util.time_format(job.get_time_iowait())
        )

        return self


def build_jobs_data(jobs, dst_prefix, tmp_prefix):
    sorted_jobs = sorted(jobs, key=plotman.job.Job.get_time_wall)

    jobs_data = [
        JobRow.from_job(job=job, dst_prefix=dst_prefix, tmp_prefix=tmp_prefix)
        for index, job in enumerate(sorted_jobs)
    ]

    return jobs_data


def build_jobs_table(jobs_data):
    table = rich.table.Table(box=None, header_style='reverse')

    table.add_column('#')

    for field in attr.fields(JobRow):
        table.add_column(field.metadata['name'])

    for index, row in enumerate(jobs_data):
        table.add_row(str(index), *attr.astuple(row))

    return table
