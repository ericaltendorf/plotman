import importlib.resources

import pendulum

import plotman.job
import plotman.plotters.bladebit
import plotman._tests.resources


def test_byte_by_byte_full_load() -> None:
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit.plot.log",
    )

    parser = plotman.plotters.bladebit.Plotter()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.bladebit.SpecificInfo(
        phase=plotman.job.Phase(major=5, minor=1),
        started_at=pendulum.datetime(2021, 8, 29, 22, 22, 0, tz=None),
        plot_id="1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3",
        threads=88,
        plot_size=32,
        dst_dir="/mnt/tmp/01/manual-transfer/",
        phase1_duration_raw=313.98,
        phase2_duration_raw=44.60,
        phase3_duration_raw=203.26,
        phase4_duration_raw=1.11,
        total_time_raw=582.91,
        filename="plot-k32-2021-08-29-22-22-1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3.plot",
        plot_name="plot-k32-2021-08-29-22-22-1fc7b57baae24da78e3bea44d58ab51f162a3ed4d242bab2fbcc24f6577d88b3",
    )


def test_log_phases() -> None:
    # TODO: CAMPid 0978413087474699698142013249869897439887
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit.marked",
    )

    parser = plotman.plotters.bladebit.Plotter()

    wrong = []

    for marked_line in read_bytes.splitlines(keepends=True):
        phase_bytes, _, line_bytes = marked_line.partition(b",")
        major, _, minor = phase_bytes.decode("utf-8").partition(":")
        phase = plotman.job.Phase(major=int(major), minor=int(minor))

        parser.update(chunk=line_bytes)

        if parser.info.phase != phase:  # pragma: nocov
            wrong.append([parser.info.phase, phase, line_bytes.decode("utf-8")])

    assert wrong == []


def test_marked_log_matches() -> None:
    # TODO: CAMPid 909831931987460871349879878609830987138931700871340870
    marked_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit.marked",
    )
    log_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit.plot.log",
    )

    for marked_line, log_line in zip(
        marked_bytes.splitlines(keepends=True), log_bytes.splitlines(keepends=True)
    ):
        _, _, marked_just_line = marked_line.partition(b",")
        assert marked_just_line == log_line
