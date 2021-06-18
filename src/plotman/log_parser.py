import os
import re
import typing

from plotman.plotinfo import PlotInfo
import plotman.job


class PlotLogParser:
    """Parser for a finished plotting job"""

    def parse(self, file: typing.TextIO) -> PlotInfo:
        """Parses a single log and returns its info"""
        entry = PlotInfo()

        matchers = [
            self.ignore_line,
            self.plot_id,
            self.plot_start_date,
            self.plot_size,
            self.buffer_size,
            self.buckets,
            self.threads,
            self.plot_dirs,
            self.phase1_duration,
            self.phase2_duration,
            self.phase3_duration,
            self.phase4_duration,
            self.total_time,
            self.copy_time,
            self.filename
        ]

        for line in file:
            for matcher in matchers:
                if (matcher(line, entry)):
                    break
        
        return entry

    # ID: 3eb8a37981de1cc76187a36ed947ab4307943cf92967a7e166841186c7899e24
    def plot_id(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r'^ID: (.+)$', line)
        if m:
            entry.plot_id = m.group(1)
        return m != None

    # Renamed final file from "/farm/wagons/801/abc.plot.2.tmp" to "/farm/wagons/801/abc.plot"
    def filename(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r'^Renamed final file from ".+" to "(.+)"', line)
        if m:
            entry.filename = m.group(1)
        return m != None

    # Time for phase 1 = 17571.981 seconds. CPU (178.600%) Sun Apr  4 23:53:42 2021
    def phase1_duration(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Time for phase 1 = (\d+\.\d+) seconds", line)
        if m:
            entry.phase1_duration_raw = float(m.group(1))
        return m != None

    # Time for phase 2 = 6911.621 seconds. CPU (71.780%) Mon Apr  5 01:48:54 2021
    def phase2_duration(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Time for phase 2 = (\d+\.\d+) seconds", line)
        if m:
            entry.phase2_duration_raw = float(m.group(1))
        return m != None

    # Time for phase 3 = 14537.188 seconds. CPU (82.730%) Mon Apr  5 05:51:11 2021
    def phase3_duration(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Time for phase 3 = (\d+\.\d+) seconds", line)
        if m:
            entry.phase3_duration_raw = float(m.group(1))
        return m != None

    # Time for phase 4 = 924.288 seconds. CPU (86.810%) Mon Apr  5 06:06:35 2021
    def phase4_duration(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Time for phase 4 = (\d+\.\d+) seconds", line)
        if m:
            entry.phase4_duration_raw = float(m.group(1))
        return m != None

    # Total time = 39945.080 seconds. CPU (123.100%) Mon Apr  5 06:06:35 2021
    def total_time(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Total time = (\d+\.\d+) seconds", line)
        if m:
            entry.total_time_raw = float(m.group(1))
        return m != None

    # Copy time = 501.696 seconds. CPU (23.860%) Sun May  9 22:52:41 2021
    def copy_time(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Copy time = (\d+\.\d+) seconds", line)
        if m:
            entry.copy_time_raw = float(m.group(1))
        return m != None

    # Starting plotting progress into temporary dirs: /farm/yards/901 and /farm/yards/901
    def plot_dirs(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Starting plotting progress into temporary dirs: (.+) and (.+)$", line)
        if m:
            entry.tmp_dir1 = m.group(1)
            entry.tmp_dir2 = m.group(2)
        return m != None

    # Using 4 threads of stripe size 65536
    def threads(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Using (\d+) threads of stripe size (\d+)", line)
        if m:
            entry.threads = int(m.group(1))
        return m != None

    # "^Using (\\d+) buckets"
    def buckets(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Using (\d+) buckets", line)
        if m:
            entry.buckets = int(m.group(1))
        return m != None

    # Buffer size is: 4000MiB
    def buffer_size(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r"^Buffer size is: (\d+)MiB", line)
        if m:
            entry.buffer = int(m.group(1))
        return m != None

    # Plot size is: 32
    def plot_size(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r'^Plot size is: (\d+)', line)
        if m:
            entry.plot_size = int(m.group(1))
        return m != None

    # Starting phase 1/4: Forward Propagation into tmp files... Sun May  9 17:36:12 2021
    def plot_start_date(self, line: str, entry: PlotInfo) -> bool:
        m = re.search(r'^Starting phase 1/4: Forward Propagation into tmp files\.\.\. (.+)', line)
        if m:
            entry.started_at = plotman.job.parse_chia_plot_time(s=m.group(1))
        return m != None


    # Ignore lines starting with Bucket
    # Bucket 0 uniform sort. Ram: 3.250GiB, u_sort min: 0.563GiB, qs min: 0.281GiB.
    def ignore_line(self, line: str, _: PlotInfo) -> bool:
        m = re.search(r'^\tBucket', line)
        return m != None