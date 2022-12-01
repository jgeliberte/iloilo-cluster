from datetime import datetime, timedelta
import os
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import querydb as qdb

path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

sc = qdb.memcached()

#output path
output_path = path + sc['fileio']['output_path']
rainfall_path = path + sc['fileio']['rainfall_path']

for dirpath, dirnames, filenames in os.walk(output_path):
    for filename in filenames:
        curpath = os.path.join(dirpath, filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(curpath))
        if datetime.now() - file_modified > timedelta(days = 1):
            os.remove(curpath)