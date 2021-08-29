import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt

from plotman.log_parser import PlotLogParser


def create_ax_dumbbell(ax : matplotlib.pyplot.axis, data : np.array, max_stacked: int = 50) -> None: 
    '''
        Create a dumbbell plot of concurrent plot instances over time.
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
    '''

    def newline(p1 : float, p2 : float) -> matplotlib.lines.Line2D:
        l = matplotlib.lines.Line2D([p1[0],p2[0]], [p1[1],p2[1]], color='r')
        ax.add_line(l)
        return l

    # Prevent the stack from growing to tall
    num_rows = data.shape[0]
    stacker = []
    for _ in range(int(np.ceil(num_rows / float(max_stacked)))):
        stacker.extend(list(range(max_stacked)))
    stacker = np.array(stacker)
    if num_rows % float(max_stacked) != 0:
        stacker = stacker[:-(max_stacked-int(num_rows % float(max_stacked)))]

    for (p1, p2), i in zip(data[:,:2], stacker):
        newline([p1, i], [p2, i])
    ax.scatter(data[:,0], stacker, color='b')
    ax.scatter(data[:,1], stacker, color='b')

    ax.set_ylabel('Plots')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def create_ax_plotrate(ax : matplotlib.pyplot.axis, data : np.array, end : bool = True, window : int = 3) -> None: 
    '''
        Create a plot showing the rate of plotting over time. Can be computed
            with respect to the plot start (this is rate of plot creation) or
            with respect to the plot end (this is rate of plot completion).
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
            end: T/F, compute plot creation or plot completion rate.
            window: Window to compute rate over.
    '''

    def estimate_rate(data : np.array, window : int) -> np.array: 
        rate_list = []
        window_list = []
        # This takes care of when we dont have a full window
        for i in range(window):
            rate_list.append(data[i] - data[0])
            window_list.append(i)
        # This takes care of when we do
        for i in range(len(data) - window):
            rate_list.append(data[i+window] - data[i])
            window_list.append(window)
        rate_list, window_list = np.array(rate_list), np.array(window_list)
        rate_list[rate_list == 0] = np.nan # This prevents div by zero error
        return np.where(np.logical_not(np.isnan(rate_list)), (window_list-1) / rate_list, 0)

    # Estimate the rate of ending or the rate of starting
    if end:
        rate = estimate_rate(data[:,1], window)
        ax.plot(data[:,1], rate)
    else:
        rate = estimate_rate(data[:,0], window)
        ax.plot(data[:,0], rate)

    ax.set_ylabel('Avg Plot Rate (plots/hour)')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def create_ax_plottime(ax : matplotlib.pyplot.axis, data : np.array, window : int = 3) -> None: 
    '''
        Create a plot showing the average time to create a single plot. This is
            computed using a moving average. Note that the plot may not be
            very accurate for the beginning and ending windows.
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
            window: Window to compute rate over.
    '''

    # Compute moving avg
    kernel = np.ones(window) / window
    data_tiled = np.vstack((
        np.expand_dims(data[:,1] - data[:,0], axis=1),
        np.tile(data[-1,1] - data[-1,0], (window-1, 1))
    ))
    rolling_avg = np.convolve(data_tiled.squeeze(), kernel, mode='valid')

    ax.plot(data[:,1], rolling_avg)

    ax.set_ylabel('Avg Plot Time (hours)')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def create_ax_plotcumulative(ax : matplotlib.pyplot.axis, data : np.array) -> None:
    '''
        Create a plot showing the cumulative number of plots over time.
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
    '''
    ax.plot(data[:,1], range(data.shape[0]))

    ax.set_ylabel('Total plots (plots)')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def graph(logdir : str, figfile : str, latest_k : int, window : int) -> None: 
    assert window >= 2, "Cannot compute moving average over a window less than 3"
    assert os.path.isdir(logdir)

    # Build a list of the logfiles
    logdir = os.path.abspath(logdir)
    logfilenames = [os.path.join(logdir, l) for l in os.listdir(logdir) if
        os.path.splitext(l)[-1] == '.log']

    assert len(logfilenames) > 0, "Directory contains no files {}".format(logdir)

    # For each log file, extract the start, end, and duration
    time_catter = []
    parser = PlotLogParser()    
    for logfilename in logfilenames:
        with open(logfilename, 'r') as f:
            info = parser.parse(f)
            if info.total_time_raw != 0:
                time_catter.append(
                    [
                        info.started_at.timestamp(), 
                        info.started_at.timestamp() + info.total_time_raw,
                        info.total_time_raw
                    ]
                )

    assert len(time_catter) > 0, "No valid log files found, need a finished plot"

    # This array will hold start and end data (in hours)
    data_started_ended = np.array(time_catter) / (60 * 60)

    # Shift the data so that it starts at zero
    data_started_ended -= np.min(data_started_ended[:, 0])

    # Sort the rows by start time
    data_started_ended = data_started_ended[np.argsort(data_started_ended[:, 0])]

    # Remove older entries
    if latest_k is not None:
        data_started_ended = data_started_ended[-latest_k:, :]

    # Create figure
    num_plots = 4
    f, _ = plt.subplots(2,1, figsize=(8, 10))
    ax = plt.subplot(num_plots,1,1)
    ax.set_title('Plot performance summary')

    create_ax_dumbbell(ax, data_started_ended)

    if data_started_ended.shape[0] > window:
        ax = plt.subplot(num_plots,1,2)
        create_ax_plotrate(ax, data_started_ended, end=True, window=window)

        ax = plt.subplot(num_plots,1,3)
        create_ax_plottime(ax, data_started_ended, window=window)

    ax = plt.subplot(num_plots,1,4)
    create_ax_plotcumulative(ax, data_started_ended)

    ax.set_xlabel('Time (hours)')
    f.savefig(figfile)