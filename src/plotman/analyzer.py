import os
import re
import statistics
import sys
import time, datetime

import texttable as tt
import numpy as np

import matplotlib
import matplotlib.pyplot as plt

from plotman import plot_util


def create_ax_dumbbell(ax, data, max_stacked=50):
    '''
        Create a dumbbell plot of concurrent plot instances over time.
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
    '''

    def newline(p1, p2, color='r'):
        l = matplotlib.lines.Line2D([p1[0],p2[0]], [p1[1],p2[1]], color=color)
        ax.add_line(l)
        return l

    # Prevent the stack from growing to tall
    num_rows = data.shape[0]
    stacker = []
    for _ in range(int(np.ceil(num_rows / float(max_stacked)))):
        stacker.extend(list(range(max_stacked)))
    stacker = np.array(stacker)
    stacker = stacker[:-(max_stacked-int(num_rows % float(max_stacked)))]

    for (p1, p2), i in zip(data[:,:2], stacker):
        newline([p1, i], [p2, i])
    ax.scatter(data[:,0], stacker, color='b')
    ax.scatter(data[:,1], stacker, color='b')

    ax.set_ylabel('Plots')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def create_ax_plotrate(ax, data, end=True, window=3):
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

    def estimate_rate(data, window):
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


def create_ax_plottime(ax, data, window=3):
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


def create_ax_plotcumulative(ax, data):
    '''
        Create a plot showing the cumulative number of plots over time.
        Parameters:
            ax: a matplotlib axis.
            data: numpy arrary with [start times, end times].
    '''
    cumsum = np.cumsum(range(data.shape[0]))

    ax.plot(data[:,1], cumsum)

    ax.set_ylabel('Total plots (plots)')
    ax.set_xlim(np.min(data[:,0])-2, np.max(data[:,1])+2)


def analyze(logfilenames, clipterminals, bytmp, bybitfield, figfile):
    data = {}
    
    # Figfile now also acts like a switch between passing a directory or a single log file
    if figfile is not None:
        logfilenames = [os.path.join(os.path.dirname(logfilenames), l) for l in os.listdir(logfilenames) if
            os.path.splitext(l)[-1] == '.log']

    for logfilename in logfilenames:
        with open(logfilename, 'r') as f:
            # Record of slicing and data associated with the slice
            sl = 'x'         # Slice key
            phase_time = {}  # Map from phase index to time
            n_sorts = 0
            n_uniform = 0
            is_first_last = False

            # Read the logfile, triggering various behaviors on various
            # regex matches.
            for line in f:
                # Beginning of plot job.  We may encounter this multiple
                # times, if a job was run with -n > 1.  Sample log line:
                # 2021-04-08T13:33:43.542  chia.plotting.create_plots       : INFO     Starting plot 1/5
                m = re.search(r'Starting plot (\d*)/(\d*)', line)
                if m:
                    # (re)-initialize data structures
                    sl = 'x'         # Slice key
                    phase_time = {}  # Map from phase index to time
                    n_sorts = 0
                    n_uniform = 0

                    seq_num = int(m.group(1))
                    seq_total = int(m.group(2))
                    is_first_last = seq_num == 1 or seq_num == seq_total

                # Temp dirs.  Sample log line:
                # Starting plotting progress into temporary dirs: /mnt/tmp/01 and /mnt/tmp/a
                m = re.search(r'^Starting plotting.*dirs: (.*) and (.*)', line)
                if m:
                    # Record tmpdir, if slicing by it
                    if bytmp:
                        tmpdir = m.group(1)
                        sl += '-' + tmpdir

                # Bitfield marker.  Sample log line(s):
                # Starting phase 2/4: Backpropagation without bitfield into tmp files... Mon Mar  1 03:56:11 2021
                #   or
                # Starting phase 2/4: Backpropagation into tmp files... Fri Apr  2 03:17:32 2021
                m = re.search(r'^Starting phase 2/4: Backpropagation', line)
                if bybitfield and m:
                    if 'without bitfield' in line:
                        sl += '-nobitfield'
                    else:
                        sl += '-bitfield'

                # Phase timing.  Sample log line:
                # Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020
                for phase in ['1', '2', '3', '4']:
                    m = re.search(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                    if m:
                        phase_time[phase] = float(m.group(1))

                # Uniform sort.  Sample log line:
                # Bucket 267 uniform sort. Ram: 0.920GiB, u_sort min: 0.688GiB, qs min: 0.172GiB.
                #   or
                # ....?....
                #   or
                # Bucket 511 QS. Ram: 0.920GiB, u_sort min: 0.375GiB, qs min: 0.094GiB. force_qs: 1
                m = re.search(r'Bucket \d+ ([^\.]+)\..*', line)
                if m and not 'force_qs' in line:
                    sorter = m.group(1)
                    n_sorts += 1
                    if sorter == 'uniform sort':
                        n_uniform += 1
                    elif sorter == 'QS':
                        pass
                    else:
                        print ('Warning: unrecognized sort ' + sorter)

                # Job completion.  Record total time in sliced data store.
                # Sample log line:
                # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                m = re.search(r'^Total time = (\d+.\d+) seconds.*', line)
                if m:
                    if clipterminals and is_first_last:
                        pass  # Drop this data; omit from statistics.
                    else:
                        data.setdefault(sl, {}).setdefault('total time', []).append(float(m.group(1)))
                        for phase in ['1', '2', '3', '4']:
                            data.setdefault(sl, {}).setdefault('phase ' + phase, []).append(phase_time[phase])
                        data.setdefault(sl, {}).setdefault('%usort', []).append(100 * n_uniform // n_sorts)

                        # Grab the time ended, compute the time started
                        time_ended = time.mktime(datetime.datetime.strptime(line.split(')')[-1][1:-1], '%a %b %d %H:%M:%S %Y').timetuple())
                        data.setdefault(sl, {}).setdefault('time ended', []).append(time_ended)
                        data.setdefault(sl, {}).setdefault('time started', []).append(time_ended - float(m.group(1)))

    if figfile is not None:
        # Prepare report
        for sl in data.keys():
            
            # This array will hold start and end data (in hours)
            data_started_ended = np.array([[ts, te, te-ts] for 
                ts, te in zip(data[sl]['time started'], data[sl]['time ended'])
            ]) / (60 * 60)

            # Sift the data so that it starts at zero
            data_started_ended -= np.min(data_started_ended[:, 0])

            # Sort the rows by start time 
            data_started_ended = data_started_ended[np.argsort(data_started_ended[:, 0])]

            # Create figure
            num_plots = 4
            f, _ = plt.subplots(2,1, figsize=(8, 12))
            ax = plt.subplot(num_plots,1,1)

            create_ax_dumbbell(ax, data_started_ended)

            ax = plt.subplot(num_plots,1,2)
            create_ax_plotrate(ax, data_started_ended, end=True, window=3)

            ax = plt.subplot(num_plots,1,3)
            create_ax_plottime(ax, data_started_ended, window=3)

            ax = plt.subplot(num_plots,1,4)
            create_ax_plotcumulative(ax, data_started_ended)

            print('Saving analysis figure to {}'.format(figfile))
            ax.set_xlabel('Time (hours)')
            f.savefig(figfile)
    else:
        # Prepare report
        tab = tt.Texttable()
        all_measures = ['%usort', 'phase 1', 'phase 2', 'phase 3', 'phase 4', 'total time']
        headings = ['Slice', 'n'] + all_measures
        tab.header(headings)

        for sl in data.keys():
            row = [sl]

            # Sample size
            sample_sizes = []
            for measure in all_measures:
                values = data.get(sl, {}).get(measure, [])
                sample_sizes.append(len(values))
            sample_size_lower_bound = min(sample_sizes)
            sample_size_upper_bound = max(sample_sizes)
            if sample_size_lower_bound == sample_size_upper_bound:
                row.append('%d' % sample_size_lower_bound)
            else:
                row.append('%d-%d' % (sample_size_lower_bound, sample_size_upper_bound))

            # Phase timings
            for measure in all_measures:
                values = data.get(sl, {}).get(measure, [])
                if(len(values) > 1):
                    row.append('μ=%s σ=%s' % (
                        plot_util.human_format(statistics.mean(values), 1),
                        plot_util.human_format(statistics.stdev(values), 0)
                        ))
                elif(len(values) == 1):
                    row.append(plot_util.human_format(values[0], 1))
                else:
                    row.append('N/A')

            tab.add_row(row)

        (rows, columns) = os.popen('stty size', 'r').read().split()
        tab.set_max_width(int(columns))
        s = tab.draw()
        print(s)


