import codecs
import collections
import functools
import pathlib
import re
import typing

import attr
import typing_extensions

import plotman.job
import plotman.plotinfo


T = typing.TypeVar("T")


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


# check_specific_info_protocol = ProtocolChecker[SpecificInfo]()


class LineHandler(typing_extensions.Protocol):
    def __call__(self, match: typing.Match[str], info: SpecificInfo) -> typing.Optional[SpecificInfo]:
        ...


@attr.mutable
class RegexLineHandlers:
    mapping: typing.Dict[typing.Pattern[str], typing.List[LineHandler]] = attr.ib(
        factory=lambda: collections.defaultdict(list),
    )

    def register(self, expression: str) -> typing.Callable[[LineHandler], LineHandler]:
        return functools.partial(self._decorator, expression=expression)

    def _decorator(self, handler: LineHandler, expression: str) -> LineHandler:
        self.mapping[re.compile(expression)].append(handler)
        return handler


class Parser(typing_extensions.Protocol):
    def update(self, chunk: bytes) -> SpecificInfo:
        ...


# check_parser_protocol = ProtocolChecker[Parser]()


class Plotter(typing_extensions.Protocol):
    parser: Parser


# check_plotter_protocol = ProtocolChecker[Plotter]()
