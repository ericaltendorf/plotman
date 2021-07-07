import typing

import attr
import pendulum


@attr.mutable
class PlotInfo:
    """Represents the results of a finished plot job"""
    started_at: typing.Optional[pendulum.DateTime] = None
    plot_id: str = ""
    buckets: int = 0
    threads: int = 0
    buffer: int = 0
    plot_size: int = 0
    tmp_dir1: str = ""
    tmp_dir2: str = ""
    phase1_duration_raw: float = 0
    phase2_duration_raw: float = 0
    phase3_duration_raw: float = 0
    phase4_duration_raw: float = 0
    total_time_raw: float = 0
    copy_time_raw: float = 0
    filename: str = ""

    def in_progress(self) -> bool:
      "The plot is in progress if no total time has been reported."
      return self.total_time == 0

    # Phase 1 duration
    @property
    def phase1_duration(self) -> int:
        return round(self.phase1_duration_raw)

    @property
    def phase1_duration_minutes(self) -> int:
        return self.duration_to_minutes(self.phase1_duration_raw)

    @property
    def phase1_duration_hours(self) -> float:
        return self.duration_to_hours(self.phase1_duration_raw)

    # Phase 2 duration
    @property
    def phase2_duration(self) -> int:
        return round(self.phase2_duration_raw)

    @property
    def phase2_duration_minutes(self) -> int:
        return self.duration_to_minutes(self.phase2_duration_raw)

    @property
    def phase2_duration_hours(self) -> float:
        return self.duration_to_hours(self.phase2_duration_raw)

    # Phase 3 duration
    @property
    def phase3_duration(self) -> int:
        return round(self.phase3_duration_raw)

    @property
    def phase3_duration_minutes(self) -> int:
        return self.duration_to_minutes(self.phase3_duration_raw)

    @property
    def phase3_duration_hours(self) -> float:
        return self.duration_to_hours(self.phase3_duration_raw)

    # Phase 4 duration
    @property
    def phase4_duration(self) -> int:
        return round(self.phase4_duration_raw)

    @property
    def phase4_duration_minutes(self) -> int:
        return self.duration_to_minutes(self.phase4_duration_raw)

    @property
    def phase4_duration_hours(self) -> float:
        return self.duration_to_hours(self.phase4_duration_raw)

    # Total time
    @property
    def total_time(self) -> int:
        return round(self.total_time_raw)

    @property
    def total_time_minutes(self) -> int:
        return self.duration_to_minutes(self.total_time_raw)

    @property
    def total_time_hours(self) -> float:
        return self.duration_to_hours(self.total_time_raw)

    # Copy time
    @property
    def copy_time(self) -> int:
        return round(self.copy_time_raw)

    @property
    def copy_time_minutes(self) -> int:
        return self.duration_to_minutes(self.copy_time_raw)

    @property
    def copy_time_hours(self) -> float:
        return self.duration_to_hours(self.copy_time_raw)

    def duration_to_minutes(self, duration: float) -> int:
        return round(duration / 60)

    def duration_to_hours(self, duration: float) -> float:
        return round(duration / 60 / 60, 2)
