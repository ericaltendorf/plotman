class PlotmanError(Exception):
    """An exception type for all plotman errors to inherit from.  This is
    never to be raised.
    """

    pass


class UnableToIdentifyPlotterFromLogError(PlotmanError):
    def __init__(self) -> None:
        super().__init__("Failed to identify the plotter definition for parsing log")
