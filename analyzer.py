import os
import re
import statistics
import sys
import texttable as tt

import plot_util

class LogAnalyzer:
    all_measures = ['phase 1', 'phase 2', 'phase 3', 'phase 4', 'total time']

    def analyze(self, logfilenames, bytmp, bybitfield):
        data = {}
        for logfilename in logfilenames:
            with open(logfilename, 'r') as f:
                sl = 'x'         # slice
                phase_time = {}  # Map from phase index to time

                for line in f:
                    #
                    # Aggregation specification
                    #

                    # Starting phase 1/4: Forward Propagation into tmp files... Sun Nov 15 00:35:57 2020
                    # This could be used to slice by time (hour, day, etc.)
                    #    m = re.search(r'^Starting phase 1/4.*files.*\d\d (\d\d):\d\d:\d\d \d\d\d\d', line)
                    #    if m:
                    #        bucketsize = 2
                    #        hour = int(m.group(1))
                    #        hourbucket = int(hour / bucketsize)
                    #        sl += '-%02d-%02d' % (hourbucket * bucketsize, (hourbucket + 1) * bucketsize)

                    # Starting plotting progress into temporary dirs: /mnt/tmp/01 and /mnt/tmp/a
                    m = re.search(r'^Starting plotting.*dirs: (.*) and (.*)', line)
                    if bytmp and m:
                        tmpdir = m.group(1)
                        sl += '-' + tmpdir

                    # Starting phase 2/4: Backpropagation without bitfield into tmp files... Mon Mar  1 03:56:11 2021
                    #   or
                    # Starting phase 2/4: Backpropagation into tmp files... Fri Apr  2 03:17:32 2021
                    m = re.search(r'^Starting phase 2/4: Backpropagation', line)
                    if bybitfield and m:
                        if 'without bitfield' in line:
                            sl += '-nobitfield'
                        else:
                            sl += '-bitfield'

                    #
                    # Data collection
                    #

                    # Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020
                    for phase in ['1', '2', '3', '4']:
                        m = re.search(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                        if m:
                            phase_time[phase] = float(m.group(1))

                    #
                    # Final time collection, and write to sliced data store
                    #

                    # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                    m = re.search(r'^Total time = (\d+.\d+) seconds.*', line)
                    if m:
                        data.setdefault(sl, {}).setdefault('total time', []).append(float(m.group(1)))
                        for phase in ['1', '2', '3', '4']:
                            data.setdefault(sl, {}).setdefault('phase ' + phase, []).append(phase_time[phase])

        # Prepare report
        tab = tt.Texttable()
        headings = ['Key'] + self.all_measures
        tab.header(headings)

        for sl in data.keys():
            row = [sl]
            for measure in self.all_measures:
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


