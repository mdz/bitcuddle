#!/usr/bin/env python3

# Calculate a histogram on price delta for consecutive data points.
# The prices are assumed to be in the second column.

import csv
import sys
import datetime

previous_value = None
previous_proportion = None
subsamples = 1
histo = {}

count = 0
table = csv.reader(open(sys.argv[1]))
for row in table:
    #print(row)
    #timestamp = datetime.datetime(row[0])
    value = float(row[1])
    count += 1
    if count % subsamples == 0:
        if previous_value is not None:
            delta = value - previous_value
            proportion = delta / previous_value
            if previous_proportion is not None:
                if abs(previous_proportion) > 0.05:
                    #print("{} {}", previous_proportion, proportion)
                    if abs(previous_proportion + proportion) <= 0.05:
                        previous_proportion = previous_proportion + proportion
                quantized = round(previous_proportion*100)
                histo[quantized] = histo.get(quantized,0) + 1
            previous_proportion = proportion
        previous_value = value

for key in sorted(histo.keys()):
    print(key, histo[key])
