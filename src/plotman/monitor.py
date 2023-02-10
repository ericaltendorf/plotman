import collections
import functools
import importlib
import io
import itertools
import math
import os
import time
import typing

import anyio
import attr
import prompt_toolkit
import prompt_toolkit.buffer
import prompt_toolkit.input
import prompt_toolkit.key_binding
import prompt_toolkit.keys
import prompt_toolkit.layout.containers
import prompt_toolkit.layout.layout
import rich
import rich.console
import rich.layout
import rich.live
import rich.table
import toolz

import plotman.archive
import plotman.configuration
import plotman.job
import plotman.manager
import plotman.plot_util
import plotman.reporting
import plotman.resources


def with_rich() -> None:
    config_path = plotman.configuration.get_path()
    config_text = plotman.configuration.read_configuration_text(config_path)
    preset_target_definitions_text = importlib.resources.read_text(
        plotman.resources,
        "target_definitions.yaml",
    )
    cfg = plotman.configuration.get_validated_configs(config_text, config_path, preset_target_definitions_text)

    tmp_prefix = os.path.commonpath(cfg.directories.tmp)
    if cfg.directories.dst is None:
        dst_prefix = ""
    else:
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

    jobs: typing.List[plotman.job.Job] = []

    prompt_toolkit_input = prompt_toolkit.input.create_input()
    with prompt_toolkit_input.raw_mode():
        with rich.live.Live(overall, auto_refresh=False) as live:
            for i in itertools.count():
                header_layout.update(str(i))

                jobs = plotman.job.Job.get_running_jobs(
                    cfg.logging.plots,
                    cached_jobs=jobs,
                )
                jobs_data = build_jobs_data(
                    jobs=jobs,
                    dst_prefix=dst_prefix,
                    tmp_prefix=tmp_prefix,
                )

                jobs_table = build_jobs_table(jobs_data=jobs_data)
                plots_layout.update(jobs_table)

                tmp_data = build_tmp_data(
                    jobs=jobs,
                    dir_cfg=cfg.directories,
                    sched_cfg=cfg.scheduling,
                    prefix=tmp_prefix,
                )

                tmp_table = build_tmp_table(tmp_data=tmp_data)
                tmp_layout.update(tmp_table)

                live.refresh()
                for _ in range(10):
                    keys = prompt_toolkit_input.read_keys()
                    quit_keys = {'q', prompt_toolkit.keys.Keys.ControlC}
                    if any(key.key in quit_keys for key in keys):
                        return
                    time.sleep(0.1)


async def with_prompt_toolkit() -> None:
    config_path = plotman.configuration.get_path()
    config_text = plotman.configuration.read_configuration_text(config_path)
    preset_target_definitions_text = importlib.resources.read_text(
        plotman.resources,
        "target_definitions.yaml",
    )
    cfg = plotman.configuration.get_validated_configs(config_text, config_path, preset_target_definitions_text)

    tmp_prefix = os.path.commonpath(cfg.directories.tmp)
    if cfg.directories.dst is None:
        dst_prefix = ""
    else:
        dst_prefix = os.path.commonpath(cfg.directories.dst)

    header_buffer = prompt_toolkit.layout.controls.FormattedTextControl('header')
    plots_buffer = prompt_toolkit.layout.controls.FormattedTextControl('plots')
    tmp_buffer = prompt_toolkit.layout.controls.FormattedTextControl('tmp')
    dst_buffer = prompt_toolkit.layout.controls.FormattedTextControl('dst')
    archive_buffer = prompt_toolkit.layout.controls.FormattedTextControl('archive ')
    logs_buffer = prompt_toolkit.layout.controls.FormattedTextControl('logs')
    footer_buffer = prompt_toolkit.layout.controls.FormattedTextControl('footer')

    disk_columns = [
        tmp_window,
        dst_window,
    ] = [
        prompt_toolkit.layout.containers.Window(content=tmp_buffer, dont_extend_height=True, dont_extend_width=True),
        prompt_toolkit.layout.containers.Window(content=dst_buffer, dont_extend_height=True),
    ]
    rows = [
        header_window,
        plots_window,
        disk_layout,
        archive_window,
        logs_window,
        footer_window,
    ] = [
        prompt_toolkit.layout.containers.Window(content=header_buffer, dont_extend_height=True),
        prompt_toolkit.layout.containers.Window(content=plots_buffer, dont_extend_height=True),
        prompt_toolkit.layout.containers.VSplit(disk_columns, padding=1),
        prompt_toolkit.layout.containers.Window(content=archive_buffer, dont_extend_height=True, wrap_lines=True),
        prompt_toolkit.layout.containers.Window(content=logs_buffer),
        prompt_toolkit.layout.containers.Window(content=footer_buffer, dont_extend_height=True),
    ]

    root_container = prompt_toolkit.layout.containers.HSplit(rows)

    layout = prompt_toolkit.layout.Layout(root_container)

    key_bindings = prompt_toolkit.key_binding.KeyBindings()

    application = prompt_toolkit.Application[None](
        layout=layout,
        full_screen=True,
        key_bindings=key_bindings,
    )

    # https://github.com/prompt-toolkit/python-prompt-toolkit/issues/827#issuecomment-459099452
    application.output.show_cursor = lambda: False  # type: ignore[assignment]

    rich_console = rich.console.Console()

    jobs: typing.List[plotman.job.Job] = []

    # i think this should be able to be a single call...
    key_bindings.add('q')(exit_key_binding)
    key_bindings.add('c-c')(exit_key_binding)

    binding_handler_names: typing.Dict[typing.Callable[[prompt_toolkit.key_binding.key_processor.KeyPressEvent], object], str] = {
        exit_key_binding: 'exit',
    }

    key_bindings_text = ' '.join(
        f'{binding_handler_names[binding.handler]} \\[{", ".join(binding.keys)}]'
        for binding in key_bindings.bindings
    )
    footer_buffer.text = capture_rich(
        f'[reverse]key bindings[/reverse]\n{key_bindings_text}',
        console=rich_console,
    )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(functools.partial(
            cancel_after_application,
            application=application,
            cancel_scope=task_group.cancel_scope,
        ))

        for i in itertools.count():
            header_buffer.text = str(i)

            jobs = plotman.job.Job.get_running_jobs(
                cfg.logging.plots,
                cached_jobs=jobs,
            )
            jobs_data = build_jobs_data(
                jobs=jobs,
                dst_prefix=dst_prefix,
                tmp_prefix=tmp_prefix,
            )

            jobs_table = build_jobs_table(jobs_data=jobs_data)
            plots_buffer.text = capture_rich(jobs_table, console=rich_console)

            tmp_data = build_tmp_data(
                jobs=jobs,
                dir_cfg=cfg.directories,
                sched_cfg=cfg.scheduling,
                prefix=tmp_prefix,
            )

            tmp_table = build_tmp_table(tmp_data=tmp_data)
            tmp_buffer.text = capture_rich(tmp_table, console=rich_console)

            dst_data = build_dst_data(
                jobs=jobs,
                dstdirs=cfg.directories.dst,
                prefix=tmp_prefix,
            )

            dst_table = build_dst_table(dst_data=dst_data)
            dst_buffer.text = capture_rich(dst_table, console=rich_console)

            size = application.output.get_size()

            if cfg.archiving is not None:
                archdir_freebytes, log_message = plotman.archive.get_archdir_freebytes(cfg.archiving)

                archive_directories = list(archdir_freebytes.keys())
                if len(archive_directories) == 0:
                    arch_prefix = ""
                else:
                    arch_prefix = os.path.commonpath(archive_directories)

                archdir_rich = arch_dir_text(
                    archdir_freebytes=archdir_freebytes,
                    width=size.columns,
                    prefix=arch_prefix,
                )
                archive_buffer.text = capture_rich(archdir_rich, console=rich_console)

            logs_rich = '[reverse]log:[/reverse]'
            logs_buffer.text = capture_rich(logs_rich, console=rich_console)

            application.invalidate()
            await anyio.sleep(1)


async def cancel_after_application(application: prompt_toolkit.Application[None], cancel_scope: anyio.CancelScope) -> None:
    await application.run_async()
    cancel_scope.cancel()


def exit_key_binding(event: prompt_toolkit.key_binding.key_processor.KeyPressEvent) -> None:
    event.app.exit()


def capture_rich(*objects: object, console: rich.console.Console) -> prompt_toolkit.ANSI:
    with console.capture() as capture:
        console.print(*objects)

    return prompt_toolkit.ANSI(capture.get().strip())


def row_ib(name: str) -> typing.Any:
    return attr.ib(converter=str, metadata={'name': name})


@attr.frozen
class JobRow:
    plot_id: str = row_ib(name='plot id')
    k: str = row_ib(name='k')
    tmp_path: str = row_ib(name='tmp')
    dst: str = row_ib(name='dst')
    wall: str = row_ib(name='wall')
    phase: str = row_ib(name='phase')
    tmp_usage: str = row_ib(name='tmp')
    pid: str = row_ib(name='pid')
    stat: str = row_ib(name='stat')
    mem: str = row_ib(name='mem')
    user: str = row_ib(name='user')
    sys: str = row_ib(name='sys')
    io: str = row_ib(name='io')

    @classmethod
    def from_job(cls, job: plotman.job.Job, dst_prefix: str, tmp_prefix: str) -> "JobRow":
        plot_info = job.plotter.common_info()
        self = cls(
            plot_id=job.plot_id_prefix(),
            k=str(plot_info.plot_size),
            tmp_path=plotman.reporting.abbr_path(plot_info.tmpdir, tmp_prefix),
            dst=plotman.reporting.abbr_path(plot_info.dstdir, dst_prefix),
            wall=plotman.plot_util.time_format(job.get_time_wall()),
            phase=plotman.reporting.phases_str([job.progress()]),
            tmp_usage=plotman.plot_util.human_format(job.get_tmp_usage(), 0),
            pid=str(job.proc.pid),
            stat=job.get_run_status(),
            mem=plotman.plot_util.human_format(job.get_mem_usage(), 1),
            user=plotman.plot_util.time_format(job.get_time_user()),
            sys=plotman.plot_util.time_format(job.get_time_sys()),
            io=plotman.plot_util.time_format(job.get_time_iowait())
        )

        return self


def build_jobs_data(jobs: typing.List[plotman.job.Job], dst_prefix: str, tmp_prefix: str) -> typing.List[JobRow]:
    sorted_jobs = sorted(jobs, key=plotman.job.Job.get_time_wall)

    jobs_data = [
        JobRow.from_job(job=job, dst_prefix=dst_prefix, tmp_prefix=tmp_prefix)
        for index, job in enumerate(sorted_jobs)
    ]

    return jobs_data


def build_jobs_table(jobs_data: typing.List[JobRow]) -> rich.table.Table:
    table = rich.table.Table(box=None, header_style='reverse')

    table.add_column('#')

    for field in attr.fields(JobRow):
        table.add_column(field.metadata['name'])

    for index, row in enumerate(jobs_data):
        table.add_row(str(index), *attr.astuple(row))

    return table


@attr.frozen
class TmpRow:
    path: str = row_ib(name='tmp')
    ready: bool = row_ib(name='ready')
    phases: str = row_ib(name='phases')

    @classmethod
    def from_tmp(cls, dir_cfg: plotman.configuration.Directories, jobs: typing.List[plotman.job.Job], sched_cfg: plotman.configuration.Scheduling, tmp: str, prefix: str) -> "TmpRow":
        phases = sorted(plotman.job.job_phases_for_tmpdir(d=tmp, all_jobs=jobs))
        tmp_suffix = plotman.reporting.abbr_path(path=tmp, putative_prefix=prefix)
        ready = plotman.manager.phases_permit_new_job(
            phases=phases,
            d=tmp_suffix,
            sched_cfg=sched_cfg,
            dir_cfg=dir_cfg,
        )
        self = cls(
            path=tmp_suffix,
            ready=ready,
            phases=plotman.reporting.phases_str(phases=phases, max_num=5),
        )
        return self


def build_tmp_data(jobs: typing.List[plotman.job.Job], dir_cfg: plotman.configuration.Directories, sched_cfg: plotman.configuration.Scheduling, prefix: str) -> typing.List[TmpRow]:
    rows = [
        TmpRow.from_tmp(
            dir_cfg=dir_cfg,
            jobs=jobs,
            sched_cfg=sched_cfg,
            tmp=tmp,
            prefix=prefix,
        )
        for tmp in sorted(dir_cfg.tmp)
    ]

    return rows


def build_tmp_table(tmp_data: typing.List[TmpRow]) -> rich.table.Table:
    table = rich.table.Table(box=None, header_style='reverse')

    for field in attr.fields(TmpRow):
        table.add_column(field.metadata['name'])

    for row in tmp_data:
        table.add_row(*attr.astuple(row))

    return table


@attr.frozen
class DstRow:
    dst: str = row_ib(name='dst')
    plot_count: int = row_ib(name='plots')
    free: str = row_ib(name='free')
    inbound_phases: str = row_ib(name='phases')
    priority: int = row_ib(name='pri')

    @classmethod
    def from_dst(cls, dst: str, jobs: typing.List[plotman.job.Job], prefix: str, dir2oldphase: typing.Dict[str, plotman.job.Phase]) -> "DstRow":
        # TODO: This logic is replicated in archive.py's priority computation,
        # maybe by moving more of the logic in to directory.py
        eldest_ph = dir2oldphase.get(dst, plotman.job.Phase(0, 0))
        phases = plotman.job.job_phases_for_dstdir(dst, jobs)

        dir_plots = plotman.plot_util.list_plots(dst)
        free = plotman.plot_util.df_b(dst)
        n_plots = len(dir_plots)
        priority = plotman.archive.compute_priority(
            phase=eldest_ph,
            gb_free=free / plotman.plot_util.GB,
            n_plots=n_plots,
        )

        self = cls(
            dst=plotman.reporting.abbr_path(dst, prefix),
            plot_count=n_plots,
            free=plotman.plot_util.human_format(free, 0),
            inbound_phases=plotman.reporting.phases_str(phases, 5),
            priority=priority,
        )

        return self


def build_dst_data(jobs: typing.List[plotman.job.Job], dstdirs: typing.Optional[typing.List[str]], prefix: str) -> typing.List[DstRow]:
    dir2oldphase = plotman.manager.dstdirs_to_furthest_phase(jobs)

    if dstdirs is None:
        return []

    rows = [
        DstRow.from_dst(
            dst=dst,
            jobs=jobs,
            prefix=prefix,
            dir2oldphase=dir2oldphase,
        )
        for dst in sorted(dstdirs)
    ]

    return rows


def build_dst_table(dst_data: typing.List[DstRow]) -> rich.table.Table:
    table = rich.table.Table(box=None, header_style='reverse')

    for field in attr.fields(DstRow):
        table.add_column(field.metadata['name'])

    for row in dst_data:
        table.add_row(*attr.astuple(row))

    return table


def arch_dir_text(archdir_freebytes: typing.Dict[str, int], width: int, prefix: str) -> str:
    lines = [
        '[reverse]archive dirs free space[/reverse]',
    ]

    if len(archdir_freebytes) == 0:
        lines.append('<no archive dir info>')
        return '\n'.join(lines)

    abbreviated_archdir_freebytes = {
        plotman.reporting.abbr_path(path=path, putative_prefix=prefix): plotman.plot_util.human_format(free, 0)
        for path, free in archdir_freebytes.items()
    }

    maximum_path_length = max(len(path) for path in abbreviated_archdir_freebytes.keys())
    maximum_free_length = max(len(path) for path in abbreviated_archdir_freebytes.values())

    cells = [
        f'{path: <{maximum_path_length}} - {free: >{maximum_free_length}}'
        for path, free in sorted(abbreviated_archdir_freebytes.items())
    ]

    cell_divider = ' | '

    cells_per_line = math.floor(
        (width + len(cell_divider)) / (len(cells[0]) + len(cell_divider))
    )

    lines.extend(
        cell_divider.join(row)
        for row in toolz.partition_all(cells_per_line, cells)
    )

    return '\n'.join(lines)
