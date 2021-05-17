import importlib.resources

from plotman._tests import resources
from plotman.log_parser import PlotLogParser

def test_should_correctly_parse():
  with importlib.resources.path(resources, "2021-04-04T19_00_47.681088-0400.log") as p:
    logfile_path = p

  parser = PlotLogParser()
  info = parser.parse(logfile_path)

  assert info.plot_id == "3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24"

  assert info.plot_size == 32
  assert info.started_at == "Sun Apr  4 19:00:50 2021"
  assert info.buffer == 4000
  assert info.buckets == 128
  assert info.threads == 4

  assert info.tmp_dir1 == "/farm/yards/901"
  assert info.tmp_dir2 == "/farm/yards/901"

  assert info.phase1_duration_raw == 17571.981
  assert info.phase1_duration == 17572
  assert info.phase1_duration_minutes == 293
  assert info.phase1_duration_hours == 4.88

  assert info.phase2_duration_raw == 6911.621
  assert info.phase2_duration == 6912
  assert info.phase2_duration_minutes == 115
  assert info.phase2_duration_hours == 1.92

  assert info.phase3_duration_raw == 14537.188
  assert info.phase3_duration == 14537
  assert info.phase3_duration_minutes == 242
  assert info.phase3_duration_hours == 4.04

  assert info.phase4_duration_raw == 924.288
  assert info.phase4_duration == 924
  assert info.phase4_duration_minutes == 15
  assert info.phase4_duration_hours == 0.26

  assert info.total_time_raw == 39945.080
  assert info.total_time == 39945
  assert info.total_time_minutes == 666
  assert info.total_time_hours == 11.10

  assert info.copy_time_raw == 501.696 
  assert info.copy_time == 502
  assert info.copy_time_minutes == 8
  assert info.copy_time_hours == 0.14

  assert info.filename == "/farm/wagons/801/plot-k32-2021-04-04-19-00-3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24.plot"