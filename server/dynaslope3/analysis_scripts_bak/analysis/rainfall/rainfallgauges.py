from datetime import datetime
import numpy as np
import os
import pandas as pd
import requests
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import analysis.querydb as qdb
import volatile.memory as mem


def noah_gauges():
    """Gathers information on rain gauges from NOAN or ASTI

    Returns:
        dataframe: available rain gauges from NOAH or ASTI

    """

    sc = mem.server_config()
    r = requests.get(sc['rainfall']['noah_gauges'],
                     auth=(sc['rainfall']['noah_user'],
                           sc['rainfall']['noah_password']))    
    noah = pd.DataFrame(r.json())
    noah = noah.loc[noah['type_name'].str.contains('rain', case = False)]
    noah = noah.dropna(subset=['station_id', 'latitude', 'longitude', 'date_installed'])
    noah.loc[:, 'dev_id'] = noah.loc[:, 'station_id'].apply(lambda x: int(x))
    noah.loc[:, 'longitude'] = noah.loc[:, 'longitude'].apply(lambda x: np.round(float(x),6))
    noah.loc[:, 'latitude'] = noah.loc[:, 'latitude'].apply(lambda x: np.round(float(x),6))
    noah = noah.loc[(noah.longitude != 0) & (noah.latitude != 0) & \
                    (noah.date_installed >= str(pd.to_datetime(0))), :]
    noah = noah.rename(columns = {'dev_id': 'gauge_name',
                                  'date_installed': 'date_activated'})
    noah.loc[:, 'data_source'] = 'noah'
    noah.loc[:, 'date_deactivated'] = noah.status_description.map({'NON-OPERATIONAL': datetime.now().strftime('%Y-%m-%d')})
    noah = noah.loc[:, ['gauge_name', 'data_source', 'longitude', 'latitude',
                 'date_activated', 'date_deactivated']]
    return noah

def main():
    """Writes in rainfall_gauges information on available rain gauges 
     for rainfall alert analysis

    """

    start = datetime.now()
    qdb.print_out(start)

    if qdb.does_table_exist('rainfall_gauges') == False:
        #Create a rainfall_gauges table if it doesn't exist yet
        qdb.create_rainfall_gauges()

    senslope = mem.get('df_dyna_rain_gauges')
    senslope = senslope.loc[senslope.has_rain == 1, :]
    senslope.loc[:, 'data_source'] = 'senslope'
    
    noah = noah_gauges()
    
    all_gauges = senslope.append(noah, sort=False)
    all_gauges.loc[:, 'gauge_name'] = all_gauges.loc[:, 'gauge_name'].apply(lambda x: str(x))
    all_gauges.loc[:, 'date_activated'] = pd.to_datetime(all_gauges.loc[:, 'date_activated'])
    written_gauges = mem.get('df_rain_gauges')
    not_written = set(all_gauges['gauge_name']) \
                     - set(written_gauges['gauge_name'])
    
    new_gauges = all_gauges.loc[all_gauges.gauge_name.isin(not_written), :]
    new_gauges = new_gauges.loc[new_gauges.date_deactivated.isnull(), :]
    new_gauges = new_gauges.loc[:, ['gauge_name', 'data_source', 'longitude',
                             'latitude', 'date_activated']]
    if len(new_gauges) != 0:
        qdb.write_rain_gauges(new_gauges)
    
    deactivated = written_gauges.loc[~written_gauges.date_deactivated.isnull(), :]
    
    deactivated_gauges = all_gauges.loc[(~all_gauges.date_deactivated.isnull()) \
                                  & (~all_gauges.gauge_name.isin(not_written))\
                                  & (~all_gauges.gauge_name.isin(deactivated.gauge_name)), :]
    date_deactivated = pd.to_datetime(deactivated_gauges.loc[:, 'date_deactivated'])
    deactivated_gauges.loc[:, 'date_deactivated'] = date_deactivated
    deactivated_gauges = deactivated_gauges.loc[:, ['gauge_name', 'data_source',
                                             'longitude','latitude',
                                             'date_activated', 'date_deactivated']]
    if len(deactivated_gauges) != 0:
        qdb.write_rain_gauges(deactivated_gauges)

    qdb.print_out('runtime = %s' %(datetime.now() - start))

################################################################################
if __name__ == "__main__":
    main()
