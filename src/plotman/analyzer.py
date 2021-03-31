import os
import re
import statistics
import sys
import texttable as tt

from plotman import plot_util

class LogAnalyzer:
    # Map from key (e.g. logdir or the like) to (map from measurement name to list of values)
    all_measures = ['phase 1', 'phase 2', 'phase 3', 'phase 4', 'total time']

    def analyze(self, logfilenames):
        data = {}
        for logfilename in logfilenames:
            with open(logfilename, 'r') as f:
                key = 'x'  # TODO
                for line in f:
                    #
                    # Aggregation specification
                    #

                    # Starting phase 1/4: Forward Propagation into tmp files... Sun Nov 15 00:35:57 2020
                    # TODO: This only does by day!!!
                    m = re.search(r'^Starting phase 1/4.*files.*\d\d (\d\d):\d\d:\d\d \d\d\d\d', line)
                    if m:
                        bucketsize = 2
                        hour = int(m.group(1))
                        hourbucket = int(hour / bucketsize)
                        # key += '-%02d-%02d' % (hourbucket * bucketsize, (hourbucket + 1) * bucketsize)

                    # Starting plotting progress into temporary dirs: /mnt/tmp/01 and /mnt/tmp/a
                    m = re.search(r'^Starting plotting.*dirs: (.*) and (.*)', line)
                    if False and m:
                        tmpdir = m.group(1)
                        # Hack to split data for backing hardware
                        tmpdir_idx = tmpdir[-2:]
                        if tmpdir_idx in ['00', '01']:
                            key += '-wd-raid'
                        if tmpdir_idx in ['02', '03', '04', '05']:
                            key += '-samsung'

                    #
                    # Data collection
                    #

                    # Time for phase 1 = 22796.7 seconds. CPU (98%) Tue Sep 29 17:57:19 2020
                    for phase in ['1', '2', '3', '4']:
                        m = re.search(r'^Time for phase ' + phase + ' = (\d+.\d+) seconds..*', line)
                        if m:
                            data.setdefault(key, {}).setdefault('phase ' + phase, []).append(float(m.group(1)))

                    # Total time = 49487.1 seconds. CPU (97.26%) Wed Sep 30 01:22:10 2020
                    m = re.search(r'^Total time = (\d+.\d+) seconds.*', line)
                    if m:
                        data.setdefault(key, {}).setdefault('total time', []).append(float(m.group(1)))

        # Prepare report
        tab = tt.Texttable()
        headings = ['Key'] + self.all_measures
        tab.header(headings)

        #for logdir in logdirs:
        for key in data.keys():
            row = [key]
            for measure in self.all_measures:
                values = data.get(key, {}).get(measure, [])
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


