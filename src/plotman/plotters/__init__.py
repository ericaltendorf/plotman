import codecs
import collections
import functools
import pathlib
import re
import typing

import attr
import click
import typing_extensions

import plotman.chia
import plotman.job
import plotman.plotinfo


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


@attr.frozen
class CommonInfo:
    phase: plotman.job.Phase
    tmp_files: typing.List[pathlib.Path] = attr.ib(factory=list)
    plot_id: typing.Optional[str] = None
    process_id: typing.Optional[int] = None


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

    def register(self, expression: str) -> typing.Callable[[LineHandler[T]], LineHandler[T]]:
        return functools.partial(self._decorator, expression=expression)

    def _decorator(self, handler: LineHandler[T], expression: str) -> LineHandler[T]:
        self.mapping[re.compile(expression)].append(handler)
        return handler


class Plotter(typing_extensions.Protocol):
    @classmethod
    def identify_log(cls, line: str) -> bool:
        ...

    @classmethod
    def identify_process(cls, command_line: typing.List[str]) -> bool:
        ...

    def parse_command_line(self, command_line: typing.List[str]) -> None:
        ...

    def update(self, chunk: bytes) -> SpecificInfo:
        ...


check_Plotter = ProtocolChecker[Plotter]()


def all_plotters() -> typing.List[typing.Type[Plotter]]:
    # TODO: maybe avoid the import loop some other way
    return [
        plotman.plotters.chianetwork.Plotter,
        plotman.plotters.madmax.Plotter,
    ]


def get_plotter_from_log(lines: typing.Iterable[str]) -> typing.Type[Plotter]:
    import plotman.plotters.chianetwork
    import plotman.plotters.madmax

    plotters = all_plotters()

    for line in lines:
        for plotter in plotters:
            if plotter.identify_log(line=line):
                return plotter

    raise Exception("Failed to identify the plotter definition for parsing log")


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
    command: plotman.chia.CommandProtocol,
    arguments: typing.List[str],
) -> plotman.job.ParsedChiaPlotsCreateCommand:
    # nice idea, but this doesn't include -h
    # help_option_names = command.get_help_option_names(ctx=context)
    help_option_names = {'--help', '-h'}

    command_arguments = [
        argument
        for argument in arguments
        if argument not in help_option_names
    ]

    try:
        context = command.make_context(info_name='', args=list(command_arguments))
    except click.ClickException as e:
        error = e
        params = {}
    else:
        error = None
        params = context.params

    return plotman.job.ParsedChiaPlotsCreateCommand(
        error=error,
        help=len(arguments) > len(command_arguments),
        parameters=params,
    )


def is_plotting_command_line(command_line: typing.List[str]) -> bool:
    try:
        get_plotter_from_command_line(command_line=command_line)
    except UnableToIdentifyCommandLineError:
        return False

    return True
