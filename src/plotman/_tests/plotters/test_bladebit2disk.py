import importlib.resources

import pendulum

import plotman.job
import plotman.plotters.bladebit2disk
import plotman._tests.resources


def test_byte_by_byte_full_load() -> None:
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit2disk.plot.log",
    )

    parser = plotman.plotters.bladebit2disk.Plotter()

    for byte in (bytes([byte]) for byte in read_bytes):
        parser.update(chunk=byte)

    assert parser.info == plotman.plotters.bladebit2disk.SpecificInfo(
        phase=plotman.job.Phase(major=4, minor=2),
        started_at=pendulum.datetime(2022, 5, 4, 00, 44, 0, tz=None),
        plot_id="8f781fecff9d78b83b7116580af550b62530a623750738a19dcea498a7a73010",
        threads=64,
        plot_size=32,
        tmp1_dir="/farm/yards/907/1",
        tmp2_dir="/farm/yards/907/2",
        dst_dir="/farm/yards/907/d",
        phase1_duration_raw=526.48,
        phase2_duration_raw=100.36,
        phase3_duration_raw=562.95,
        total_time_raw=1189.79,
        filename="plot-k32-2022-05-04-00-44-8f781fecff9d78b83b7116580af550b62530a623750738a19dcea498a7a73010.plot.tmp",
        plot_name="plot-k32-2022-05-04-00-44-8f781fecff9d78b83b7116580af550b62530a623750738a19dcea498a7a73010",
    )


def test_log_phases() -> None:
    # TODO: CAMPid 0978413087474699698142013249869897439887
    read_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit2disk.marked",
    )

    parser = plotman.plotters.bladebit2disk.Plotter()

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
        resource="bladebit2disk.marked",
    )
    log_bytes = importlib.resources.read_binary(
        package=plotman._tests.resources,
        resource="bladebit2disk.plot.log",
    )

    for marked_line, log_line in zip(
        marked_bytes.splitlines(keepends=True), log_bytes.splitlines(keepends=True)
    ):
        _, _, marked_just_line = marked_line.partition(b",")
        assert marked_just_line == log_line
