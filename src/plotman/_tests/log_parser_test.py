import importlib.resources

from plotman._tests import resources
from plotman.log_parser import PlotLogParser
import plotman.job
import plotman.plotinfo

example_info = plotman.plotinfo.PlotInfo(
    started_at=plotman.job.parse_chia_plot_time(s="Wed Jul 14 22:33:24 2021"),
    plot_id="d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4",
    buckets=128,
    threads=4,
    buffer=5000,
    plot_size=32,
    tmp_dir1="/farm/yards/902",
    tmp_dir2="/farm/yards/902/fake_tmp2",
    final_dir="/farm/yards/902/fake_dst",
    phase1_duration_raw=8134.660,
    phase2_duration_raw=3304.860,
    phase3_duration_raw=6515.266,
    phase4_duration_raw=425.637,
    total_time_raw=18380.426,
    copy_time_raw=178.438,
    filename="/farm/yards/902/fake_dst/plot-k32-2021-07-14-22-33-d2540dcfcffddbfbd7e60b4aca4d54fb937db71991298fabc253f020a87ff7d4.plot",
)


def test_should_correctly_parse() -> None:
    with importlib.resources.open_text(
        resources,
        "chianetwork.plot.log",
    ) as file:
        parser = PlotLogParser()
        info = parser.parse(file)

    assert info == example_info

    assert info.phase1_duration == 8135
    assert info.phase1_duration_minutes == 136
    assert info.phase1_duration_hours == 2.26

    assert info.phase2_duration == 3305
    assert info.phase2_duration_minutes == 55
    assert info.phase2_duration_hours == 0.92

    assert info.phase3_duration == 6515
    assert info.phase3_duration_minutes == 109
    assert info.phase3_duration_hours == 1.81

    assert info.phase4_duration == 426
    assert info.phase4_duration_minutes == 7
    assert info.phase4_duration_hours == 0.12

    assert info.total_time == 18380
    assert info.total_time_minutes == 306
    assert info.total_time_hours == 5.11

    assert info.copy_time == 178
    assert info.copy_time_minutes == 3
    assert info.copy_time_hours == 0.05
