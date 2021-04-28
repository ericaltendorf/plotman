import os
import re
import statistics
import sys

import texttable as tt

from plotman import plot_util


def analyze(logfilenames, clipterminals, bytmp, bybitfield):
    data = {}
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


