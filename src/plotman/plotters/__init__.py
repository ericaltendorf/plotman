import codecs
import collections
import functools
import pathlib
import re
import typing

import attr
import click
import pendulum
import typing_extensions

import plotman.job
import plotman.plotters.core


T = typing.TypeVar("T")


class UnableToIdentifyCommandLineError(Exception):
    pass


@attr.mutable
class LineDecoder:
    decoder: codecs.IncrementalDecoder = attr.ib(
        factory=lambda: codecs.getincrementaldecoder(encoding="utf-8")(),
    )
    buffer: str = ""

    def update(self, chunk: bytes, final: bool = False) -> typing.List[str]:
        self.buffer += self.decoder.decode(input=chunk, final=final)

        if final:
            index = len(self.buffer)
        else:
            newline_index = self.buffer.rfind("\n")

            if newline_index == -1:
                return []

            index = newline_index + 1

        splittable = self.buffer[:index]
        self.buffer = self.buffer[index:]

        return splittable.splitlines()


# from https://github.com/altendky/qtrio/blob/e891874bae70a8671b969a4f9de25ea160bdf211/qtrio/_util.py#L17-L42
class ProtocolChecker(typing.Generic[T]):
    """Instances of this class can be used as decorators that will result in type hint
    checks to verifying that other classes implement a given protocol.  Generally you
    would create a single instance where you define each protocol and then use that
    instance as the decorator.  Note that this usage is, at least in part, due to
    Python not supporting type parameter specification in the ``@`` decorator
    expression.
    .. code-block:: python
       import typing
       class MyProtocol(typing.Protocol):
           def a_method(self): ...
       check_my_protocol = qtrio._util.ProtocolChecker[MyProtocol]()
       @check_my_protocol
       class AClass:
           def a_method(self):
               return 42092
    """

    def __call__(self, cls: typing.Type[T]) -> typing.Type[T]:
        return cls


# TODO: should use pendulum without these helpers
def duration_to_minutes(duration: float) -> int:
    return round(duration / 60)


# TODO: should use pendulum without these helpers
def duration_to_hours(duration: float) -> float:
    return round(duration / 60 / 60, 2)


@attr.frozen
class CommonInfo:
    type: str
    phase: plotman.job.Phase
    tmpdir: str
    tmp2dir: str
    dstdir: str
    buckets: int
    threads: int
    filename: str
    buffer: typing.Optional[int] = None
    plot_size: int = 0
    phase1_duration_raw: float = 0
    phase2_duration_raw: float = 0
    phase3_duration_raw: float = 0
    phase4_duration_raw: float = 0
    total_time_raw: float = 0
    copy_time_raw: float = 0
    started_at: typing.Optional[pendulum.DateTime] = None
    tmp_files: typing.List[pathlib.Path] = attr.ib(factory=list)
    plot_id: typing.Optional[str] = None
    process_id: typing.Optional[int] = None
    completed: bool = False

    # Phase 1 duration
    @property
    def phase1_duration(self) -> int:
        return round(self.phase1_duration_raw)

    @property
    def phase1_duration_minutes(self) -> int:
        return duration_to_minutes(self.phase1_duration_raw)

    @property
    def phase1_duration_hours(self) -> float:
        return duration_to_hours(self.phase1_duration_raw)

    # Phase 2 duration
    @property
    def phase2_duration(self) -> int:
        return round(self.phase2_duration_raw)

    @property
    def phase2_duration_minutes(self) -> int:
        return duration_to_minutes(self.phase2_duration_raw)

    @property
    def phase2_duration_hours(self) -> float:
        return duration_to_hours(self.phase2_duration_raw)

    # Phase 3 duration
    @property
    def phase3_duration(self) -> int:
        return round(self.phase3_duration_raw)

    @property
    def phase3_duration_minutes(self) -> int:
        return duration_to_minutes(self.phase3_duration_raw)

    @property
    def phase3_duration_hours(self) -> float:
        return duration_to_hours(self.phase3_duration_raw)

    # Phase 4 duration
    @property
    def phase4_duration(self) -> int:
        return round(self.phase4_duration_raw)

    @property
    def phase4_duration_minutes(self) -> int:
        return duration_to_minutes(self.phase4_duration_raw)

    @property
    def phase4_duration_hours(self) -> float:
        return duration_to_hours(self.phase4_duration_raw)

    # Total time
    @property
    def total_time(self) -> int:
        return round(self.total_time_raw)

    @property
    def total_time_minutes(self) -> int:
        return duration_to_minutes(self.total_time_raw)

    @property
    def total_time_hours(self) -> float:
        return duration_to_hours(self.total_time_raw)

    # Copy time
    @property
    def copy_time(self) -> int:
        return round(self.copy_time_raw)

    @property
    def copy_time_minutes(self) -> int:
        return duration_to_minutes(self.copy_time_raw)

    @property
    def copy_time_hours(self) -> float:
        return duration_to_hours(self.copy_time_raw)


class SpecificInfo(typing_extensions.Protocol):
    def common(self) -> CommonInfo:
        ...


check_SpecificInfo = ProtocolChecker[SpecificInfo]()


class LineHandler(typing_extensions.Protocol, typing.Generic[T]):
    def __call__(self, match: typing.Match[str], info: T) -> T:
        ...


@attr.mutable
class RegexLineHandlers(typing.Generic[T]):
    mapping: typing.Dict[typing.Pattern[str], typing.List[LineHandler[T]]] = attr.ib(
        factory=lambda: collections.defaultdict(list),
    )

    def register(
        self, expression: str
    ) -> typing.Callable[[LineHandler[T]], LineHandler[T]]:
        return functools.partial(self._decorator, expression=expression)

    def _decorator(self, handler: LineHandler[T], expression: str) -> LineHandler[T]:
        self.mapping[re.compile(expression)].append(handler)
        return handler


class Plotter(typing_extensions.Protocol):
    parsed_command_line: typing.Optional[plotman.job.ParsedChiaPlotsCreateCommand]

    def __init__(self) -> None:
        ...

    def common_info(self) -> CommonInfo:
        ...

    @classmethod
    def identify_log(cls, line: str) -> bool:
        ...

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        ...

    def parse_command_line(self, command_line: typing.List[str], cwd: str) -> None:
        ...

    def update(self, chunk: bytes) -> SpecificInfo:
        ...


check_Plotter = ProtocolChecker[Plotter]()


def all_plotters() -> typing.List[typing.Type[Plotter]]:
    # TODO: maybe avoid the import loop some other way
    import plotman.plotters.bladebit
    import plotman.plotters.bladebit2disk
    import plotman.plotters.chianetwork
    import plotman.plotters.madmax

    return [
        plotman.plotters.bladebit.Plotter,
        plotman.plotters.bladebit2disk.Plotter,
        plotman.plotters.chianetwork.Plotter,
        plotman.plotters.madmax.Plotter,
    ]


def get_plotter_from_log(lines: typing.Iterable[str]) -> typing.Type[Plotter]:
    import plotman.plotters.bladebit
    import plotman.plotters.bladebit2disk
    import plotman.plotters.chianetwork
    import plotman.plotters.madmax

    plotters = all_plotters()

    for line in lines:
        for plotter in plotters:
            if plotter.identify_log(line=line):
                return plotter

    raise plotman.errors.UnableToIdentifyPlotterFromLogError()


def get_plotter_from_command_line(
    command_line: typing.List[str],
) -> typing.Type[Plotter]:
    for plotter in all_plotters():
        if plotter.identify_process(command_line=command_line):
            return plotter

    raise UnableToIdentifyCommandLineError(
        "Failed to identify the plotter definition for parsing the command line",
    )


def parse_command_line_with_click(
    command: "plotman.plotters.core.CommandProtocol",
    arguments: typing.List[str],
    subcommand: typing.Optional["plotman.plotters.core.CommandProtocol"] = None,
) -> plotman.job.ParsedChiaPlotsCreateCommand:
    # nice idea, but this doesn't include -h
    # help_option_names = command.get_help_option_names(ctx=context)
    help_option_names = {"--help", "-h"}

    command_arguments = [
        argument for argument in arguments if argument not in help_option_names
    ]

    params = {}
    subcommand_name = None
    subparams = {}
    try:
        # TODO: sounds interesting resilient_parsing=True
        context = command.make_context(info_name="", args=list(command_arguments))
    except click.ClickException as e:
        error = e
    else:
        params = context.params
        if subcommand is None:
            error = None
        elif subcommand.name not in context.protected_args:
            error = Exception("not the requested subcommand")
        else:
            subcommand_name = subcommand.name
            try:
                subcontext = subcommand.make_context(
                    info_name="",
                    args=list(context.args),
                )
            except click.ClickException as e:
                error = e
            else:
                error = None
                params = context.params
                subparams = subcontext.params

    return plotman.job.ParsedChiaPlotsCreateCommand(
        error=error,
        help=len(arguments) > len(command_arguments),
        parameters=dict(sorted(params.items())),
        subcommand_name=subcommand_name,
        subparameters=dict(sorted(subparams.items())),
    )


def is_plotting_command_line(command_line: typing.List[str]) -> bool:
    try:
        get_plotter_from_command_line(command_line=command_line)
    except UnableToIdentifyCommandLineError:
        return False

    return True
