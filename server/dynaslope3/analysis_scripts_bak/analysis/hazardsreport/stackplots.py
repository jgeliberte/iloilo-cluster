"""
end-of-event report plotting tools
"""

from datetime import timedelta
import matplotlib as mpl
import matplotlib.dates as pltdates
import matplotlib.pyplot as plt
import mpl_axes_aligner
import numpy as np
import os
import pandas as pd
#import seaborn
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import dynadb.db as db
import analysis.querydb as qdb
import analysis.rainfall.rainfall as rm
import analysis.rainfall.rainfallalert as ra
import analysis.subsurface.plotterlib as plotter
import analysis.subsurface.proc as proc
import analysis.subsurface.rtwindow as rtw


plt.ion()

mpl.rcParams['xtick.labelsize'] = 8
mpl.rcParams['ytick.labelsize'] = 8

            
def nonrepeat_colors(ax,NUM_COLORS,color='plasma'):
    cm = plt.get_cmap(color)
    ax.set_prop_cycle(color=[cm((NUM_COLORS-i+1)/NUM_COLORS) for i in
                                range(NUM_COLORS+1)[::-1]])
    return ax

def zeroed(df, column):
    df['zeroed_'+column] = df[column] - df[column].values[0]
    return df

# surficial data
def get_surficial_df(site, start, end):

    query = "SELECT * FROM marker_measurements"
    query += " WHERE site_code = '%s'" % site
    query += " AND ts <= '%s'"% end
    query += " AND ts > '%s'" % start
    query += " ORDER BY ts"

    df = db.df_read(query, connection='analysis')
    df['ts'] = pd.to_datetime(df['ts'])
    df['marker_name'] = df['marker_name'].apply(lambda x: x.upper())
    
    marker_df = df.groupby('marker_name', as_index=False)
    df = marker_df.apply(zeroed, column='measurement')
    
    return df

# surficial plot
def plot_surficial(ax, df, marker_lst):
    if marker_lst == 'all':
        marker_lst = set(df.marker_name)
    ax = nonrepeat_colors(ax,len(marker_lst))
    for marker in marker_lst:
        marker_df = df[df.marker_name == marker]
        ax.plot(marker_df.ts, marker_df.zeroed_measurement, marker='o',
                label=marker, alpha=1)
    ax.set_ylabel('Displacement\n(cm)', fontsize='small')
    ax.set_title('Surficial Ground Displacement', fontsize='medium')
    ncol = int((len(set(df.marker_name)) + 3) / 4)
    ax.legend(loc='upper left', ncol=ncol, fontsize='x-small', fancybox = True, framealpha = 0.5)
    ax.grid()

# rainfall data
def get_rain_df(rain_gauge, start, end):
    offsetstart = start - timedelta(3)
    query = "SELECT * FROM rainfall_gauges WHERE gauge_name = '{}'".format(rain_gauge.replace('rain_', ''))
    df = db.df_read(query, connection='analysis')
    rain_id = df.rain_id[0]
    rain_df = ra.get_resampled_data(rain_id, rain_gauge, offsetstart, start, end, check_nd=False)
    rain_df = rain_df[rain_df.rain >= 0]
    rain_df = rain_df.resample("30min").asfreq()
    
    rain_df['one'] = rain_df.rain.rolling(window=48, min_periods=1, center=False).sum()
    rain_df['one'] = np.round(rain_df.one, 2)
    rain_df['three'] = rain_df.rain.rolling(window=144, min_periods=1, center=False).sum()
    rain_df['three'] = np.round(rain_df.three, 2)
    
    rain_df = rain_df[(rain_df.index >= start) & (rain_df.index <= end)]
    rain_df = rain_df.reset_index()
    
    return rain_df

# rainfall plot
def plot_rain(ax, df, site, rain_gauge, plot_inst=True, alpha=0.05):
    ax.plot(df.ts, df.one, color='green', label='1-day cml', alpha=1)
    ax.plot(df.ts,df.three, color='blue', label='3-day cml', alpha=1)
    ax.set_ylim([0, min(max(df.three), 300)+5])
    
    if plot_inst:
        ax2 = ax.twinx()
        width = float(0.004 * (max(df['ts']) - min(df['ts'])).days)
        ax2.bar(df['ts'].apply(lambda x: pltdates.date2num(x)), df.rain, width=width,alpha=alpha, color='k', label = '30min rainfall')
        ax2.xaxis_date()
        ax2.set_ylim([0, min(max(df.rain), 100)+2])
        mpl_axes_aligner.align.yaxes(ax, 0, ax2, 0, 0.01)
    
    gauges = rm.rainfall_gauges()
    gauges = gauges[gauges.site_code == site]
    twoyrmax = gauges['threshold_value'].values[0]
    halfmax = twoyrmax/2
    
    ax.plot(df.ts, [halfmax]*len(df.ts), color='green', label='half of 2-yr max', alpha=1, linestyle='--')
    ax.plot(df.ts, [twoyrmax]*len(df.ts), color='blue', label='2-yr max', alpha=1, linestyle='--')
    
    ax.set_title("%s Rainfall Data" %rain_gauge.upper(), fontsize='medium')  
    ax.set_ylabel('1D, 3D Rain\n(mm)', fontsize='small')  
    ax.legend(loc='upper left', fontsize='x-small', fancybox = True, framealpha = 0.5)
    #ax.grid()

# subsurface data
def get_tsm_data(tsm_name, start, end, plot_type, node_lst):
    
    tsm_props = qdb.get_tsm_list(tsm_name)[0]
    window, sc = rtw.get_window(end)
    window.start = pd.to_datetime(start)
    window.offsetstart = window.start - timedelta((sc['subsurface']['num_roll_window_ops']*window.numpts-1)/48.)
    
    data = proc.proc_data(tsm_props, window, sc, comp_vel=False, analysis=False)
    df = data.tilt.reset_index()[['ts', 'node_id', 'xz', 'xy']]
    df = df.loc[(df.ts >= window.start)&(df.ts <= window.end)]
    df = df.sort_values('ts')
    
    if plot_type == 'cml':
        xzd_plotoffset = 0
        if node_lst != 'all':
            df = df[df.node_id.isin(node_lst)]
        df = plotter.cum_surf(df, xzd_plotoffset, tsm_props.nos)
    else:
        node_df = df.groupby('node_id', as_index=False)
        df = node_df.apply(zeroed, column='xz')
        df['zeroed_xz'] = df['zeroed_xz'] * 100
        node_df = df.groupby('node_id', as_index=False)
        df = node_df.apply(zeroed, column='xy')
        df['zeroed_xy'] = df['zeroed_xy'] * 100
    
    return df

# subsurface cumulative displacement plot
def plot_cml(ax, df, axis, tsm_name):
    ax.plot(df.index, df[axis].values*100)
    ax.set_ylabel('Cumulative\nDisplacement\n(cm)', fontsize='small')
    ax.set_title('%s Subsurface Cumulative %s Displacement' %(tsm_name.upper(), axis.upper()), fontsize='medium')
    ax.grid()
    
# subsurface displacemnt plot
def plot_disp(ax, df, axis, node_lst, tsm_name):
    ax = nonrepeat_colors(ax,len(node_lst))
    for node in node_lst:
        node_df = df[df.node_id == node]
        ax.plot(node_df.ts, node_df['zeroed_'+axis].values, label='Node '+str(node))
    ax.set_ylabel('Displacement\n(cm)', fontsize='small')
    ax.set_title('%s Subsurface %s Displacement' %(tsm_name.upper(), axis.upper()), fontsize='medium')
    ncol = int((len(node_lst) + 3) / 4)
    ax.legend(loc='upper left', ncol=ncol, fontsize='x-small', fancybox = True, framealpha = 0.5)
    ax.grid()

def plot_single_event(ax, ts, color='red'):
    ax.axvline(pd.to_datetime(ts), color=color, linestyle='--', alpha=1)    
    
def plot_span(ax, start, end, color):
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    ax.axvspan(start, end, facecolor=color, alpha=0.25, edgecolor=None,linewidth=0)

def rename_markers(rename_history, data):
    prev_name = rename_history['previous_name'].values[0]
    new_name = rename_history['marker_name'].values[0]
    ts = rename_history['ts'].values[0]
    mask = np.logical_and(data.ts <= ts, data.marker_name == prev_name)
    data.loc[mask, ['marker_name']] = new_name

def cml_disp(data, repo_hist):
    data['disp'] = (data['meas'] - data['meas'].shift()).fillna(0)
    for ts, marker_name,data_source in repo_hist[['ts', 'marker_name','data_source']].values:
        mask = np.logical_and(data.ts == ts, data.marker_name == marker_name)
        mask = np.logical_and(mask, data.data_source == data_source)
        data.loc[mask, ['disp']] = 0
    data['zeroed_meas'] = data['disp'].cumsum()
    return data

def get_surficial_csv(site, fname, hist, start, end, hide_mute, zero_repo):
    
    data = pd.read_csv(fname)
    data['site_code'] = data.site_code.str.upper()
    data = data[data.site_code == site.upper()]
    data['ts'] = pd.to_datetime(data.ts)
    data = data.set_index('ts').truncate(start,end).reset_index()
    data['marker_name'] = data.marker_name.str.upper()
    data = data.reset_index()

    hist = pd.read_csv(hist)
    hist['site_code'] = hist.site_code.str.upper()
    hist = hist[hist.site_code == site.upper()]
    hist['marker_name'] = hist.marker_name.str.upper()
    hist['previous_name'] = hist.previous_name.str.upper()
    hist['ts'] = pd.to_datetime(hist.ts)
    rename_hist = hist[hist.operation == 'rename'].reset_index()
    rename_grp = rename_hist.groupby('index')
    rename_grp.apply(rename_markers, data=data)
    
    keep_index = data[['ts', 'marker_name', 'data_source']].drop_duplicates().index
    data = data[data.index.isin(keep_index)]
    
    if hide_mute:
        keep_index = pd.concat([data[['ts', 'marker_name', 'data_source']], 
                                hist[hist.operation == 'mute'][['ts', 'marker_name',
                                    'data_source']]]).drop_duplicates(keep=False).index
        data = data[data.index.isin(keep_index)]
    
    data = data.sort_index()
    dfg = data.groupby('marker_name', as_index=False)
    if zero_repo:
        data = dfg.apply(cml_disp, repo_hist=hist[hist.operation == 'reposition'])
    else:
        data = dfg.apply(zeroed, column='meas')
    
    return data

def plot_from_csv(ax, df, marker_lst):    
    if marker_lst == 'all':
        marker_lst = set(df.marker_name)
        
    ax = nonrepeat_colors(ax,len(marker_lst))
    for marker in marker_lst:
        temp = df[df.marker_name == marker]
        ax.plot(temp.ts, temp.zeroed_meas, marker='o',
                label=marker, alpha=1)
    
    ax.set_ylabel('Displacement\n(cm)', fontsize='small')
    ax.set_title('Surficial Ground Displacement', fontsize='medium')
    ncol = (len(set(df.marker_name)) + 3) / 4
    ax.legend(loc='upper left', ncol=ncol, fontsize='x-small', fancybox = True, framealpha = 0.5)
    ax.grid()   

def main(site, start, end, rainfall_props, surficial_props, subsurface_props, csv_props, event_lst, span_list):
    subsurface_end = subsurface_props['end']
    # count of subplots in subsurface displacement
    disp = subsurface_props['disp']['to_plot']
    num_disp = 0
    disp_plot = subsurface_props['disp']['disp_tsm_axis']
    disp_plot_key = disp_plot.keys()
    for i in disp_plot_key:
        num_disp += len(disp_plot[i].keys())
    disp = [disp] * num_disp

    # count of subplots in subsurface displacement
    cml = subsurface_props['cml']['to_plot']
    num_cml = 0
    cml_plot = subsurface_props['cml']['cml_tsm_axis']
    cml_plot_key = cml_plot.keys()
    for i in cml_plot_key:
        num_cml += len(cml_plot[i].keys())
    cml = [cml] * num_cml

    # total number of subplots in subsurface
    subsurface = disp + cml

    # total number of subplots
    num_subplots = ([rainfall_props['to_plot']]*len(rainfall_props['rain_gauge_lst']) +
                 [surficial_props['to_plot']]+ [csv_props['to_plot']] + subsurface).count(True)
    subplot = num_subplots*101+10

    x_size = 8
    y_size = 5*num_subplots
    fig=plt.figure(figsize = (x_size, y_size))

    if rainfall_props['to_plot']:
        for rain_gauge in rainfall_props['rain_gauge_lst']:
            ax = fig.add_subplot(subplot)
            rain = get_rain_df(rain_gauge, start, end)
            rain.to_csv('rain_lung_stack.csv')
            if rain_gauge != rainfall_props['rain_gauge_lst'][0]:
                ax = fig.add_subplot(subplot-1, sharex=ax)
                subplot -= 1                    
                ax.xaxis.set_visible(False)
            plot_rain(ax, rain, site, rain_gauge.upper().replace('RAIN_NOAH_', 'ASTI ARG '), plot_inst=rainfall_props['plot_inst'], alpha=rainfall_props['alpha'])
            for event_id in range(len(event_lst[0])):
                try:
                    color = event_lst[1][event_id]
                except:
                    color = 'red'
                plot_single_event(ax, event_lst[0][event_id], color=color)
            
            for i in range(len(span_list[0])):
                startTS = span_list[0][i]
                endTS = span_list[1][i]
                color = span_list[2][i]
                plot_span(ax, startTS, endTS, color)
    
    if surficial_props['to_plot']:
        surficial = get_surficial_df(site, start, end)
        try:
            ax = fig.add_subplot(subplot-1, sharex=ax)
            subplot -= 1
        except:
            ax = fig.add_subplot(subplot)
        if rainfall_props['to_plot']:
            ax.xaxis.set_visible(False)
        plot_surficial(ax, surficial, surficial_props['markers'])
        for event_id in range(len(event_lst[0])):
            try:
                color = event_lst[1][event_id]
            except:
                color = 'red'
            plot_single_event(ax, event_lst[0][event_id], color=color)
            
        for i in range(len(span_list[0])):
            startTS = span_list[0][i]
            endTS = span_list[1][i]
            color = span_list[2][i]
            plot_span(ax, startTS, endTS, color)

    if csv_props['to_plot']:
        df = get_surficial_csv(site, csv_props['fname'], csv_props['hist'],
                               start, end, csv_props['hide_mute'],
                               csv_props['zero_repo'])
        try:
            ax = fig.add_subplot(subplot-1, sharex=ax)
            subplot -= 1
        except:
            ax = fig.add_subplot(subplot)
        if rainfall_props['to_plot']:
            ax.xaxis.set_visible(False)
        plot_from_csv(ax, df, csv_props['markers'])
        for event_id in range(len(event_lst[0])):
            try:
                color = event_lst[1][event_id]
            except:
                color = 'red'
            plot_single_event(ax, event_lst[0][event_id], color=color)
            
        for i in range(len(span_list[0])):
            startTS = span_list[0][i]
            endTS = span_list[1][i]
            color = span_list[2][i]
            plot_span(ax, startTS, endTS, color)

    if subsurface_props['disp']['to_plot']:
        disp = subsurface_props['disp']['disp_tsm_axis']
        for tsm_name in disp.keys():
            tsm_data = get_tsm_data(tsm_name, start, subsurface_end, 'disp', 'all')
            if subsurface_props['mirror_xz']:
                tsm_data['zeroed_xz'] = -tsm_data['zeroed_xz']
            if subsurface_props['mirror_xy']:
                tsm_data['zeroed_xy'] = -tsm_data['zeroed_xy']

            axis_lst = disp[tsm_name]
            for axis in axis_lst.keys():
                try:
                    ax = fig.add_subplot(subplot-1, sharex=ax)
                    subplot -= 1
                except:
                    ax = fig.add_subplot(subplot)
                ax.xaxis.set_visible(False)
                plot_disp(ax, tsm_data, axis, axis_lst[axis], tsm_name)
                for event_id in range(len(event_lst[0])):
                    try:
                        color = event_lst[1][event_id]
                    except:
                        color = 'red'
                    plot_single_event(ax, event_lst[0][event_id], color=color)
          
                for i in range(len(span_list[0])):
                    startTS = span_list[0][i]
                    endTS = span_list[1][i]
                    color = span_list[2][i]
                    plot_span(ax, startTS, endTS, color)

    if subsurface_props['cml']['to_plot']:
        cml = subsurface_props['cml']['cml_tsm_axis']
        for tsm_name in cml.keys():
            node_lst = []
            for node in cml[tsm_name].values():
                if node != 'all':
                    node_lst += node
                else:
                    node_lst += [node]
            if 'all' in node_lst:
                node_lst = 'all'
            else:
                node_lst = list(set(node_lst))
            tsm_data = get_tsm_data(tsm_name, start, subsurface_end, 'cml', node_lst)
            if subsurface_props['mirror_xz']:
                tsm_data['xz'] = -tsm_data['xz']
            if subsurface_props['mirror_xy']:
                tsm_data['xy'] = -tsm_data['xy']
                
            axis_lst = cml[tsm_name]
            for axis in axis_lst.keys():
                try:
                    ax = fig.add_subplot(subplot-1, sharex=ax)
                    subplot -= 1
                except:
                    ax = fig.add_subplot(subplot)
                ax.xaxis.set_visible(False)
                plot_cml(ax, tsm_data, axis, tsm_name)
                for event_id in range(len(event_lst[0])):
                    try:
                        color = event_lst[1][event_id]
                    except:
                        color = 'red'
                    plot_single_event(ax, event_lst[0][event_id], color=color)
                for i in range(len(span_list[0])):
                    startTS = span_list[0][i]
                    endTS = span_list[1][i]
                    color = span_list[2][i]
                    plot_span(ax, startTS, endTS, color)

    ax.set_xlim([start, end])
    fig.autofmt_xdate()
    xfmt = pltdates.DateFormatter('%Y-%m-%d')
    ax.xaxis.set_major_formatter(xfmt)
    fig.subplots_adjust(top=0.9, right=0.95, left=0.15, bottom=0.05, hspace=0.3)
    fig.suptitle(site.upper() + " Event Timeline",fontsize='x-large')
    plt.savefig(site + "_event_timeline", dpi=200,mode='w', orientation='portrait')#, 
#        facecolor='w', edgecolor='w',orientation='landscape')




###########################################################

if __name__ == '__main__':
    
    site = 'DAD'
    start = pd.to_datetime('2017-01-01')
    end = pd.to_datetime('2022-04-01')
    subsurface_end = end
    
    # annotate events
    event_lst = ['2017-01-25 16:25', '2017-01-26 10:10', '2017-02-21 17:30', '2017-02-27 12:00', '2017-04-01 21:30', '2018-01-10 3:00', '2019-01-22 8:30', '2022-01-22 15:00', '2022-02-25 7:00']#['2021-12-16 05:19','2021-12-29 04:00','2022-01-01 14:00','2022-01-02 20:48']
    event_color = ['red','red', 'red', 'red','red','red', 'red', 'red', 'red']#['yellow','yellow','orange','red']#['gold', 'red', 'red'] # [] kapag red lang everything
    
    span_starts = ['2017-01-01 00:00']#['2021-12-09 00:00', '2021-12-16 05:19', '2021-12-21 20:00','2021-12-29 04:00', '2022-01-01 14:00', '2022-01-02 20:48','2022-01-06 16:00']
    span_ends = ['2022-03-31 23:59']#['2021-12-16 05:18', '2021-12-21 19:59', '2021-12-29 03:59','2022-01-01 13:59', '2022-01-02 20:47', '2022-01-06 15:59','2022-01-07 00:00']
    alert = []
    span_colors = ['white'] #['white', 'white','white', 'white', 'white', 'white', 'white']
    #span_colors = ['yellow', 'white', 'yellow', 'red', 'red', 'red', 'red']
    span_list = [span_starts, span_ends, span_colors]
    
    
    # rainfall plot                                                 
    rainfall = True                          ### True if to plot rainfall
    plot_inst = True                          ### True if to plot instantaneous rainfall
    alpha = 0.1                                ### opacity of instantaneous rainfall
    rain_gauge_lst = ['rain_dadra']                ### specifiy rain gauge (e.g rain_noah_1234, rain_tuetb)
    rainfall_props = {'to_plot': rainfall, 'rain_gauge_lst': rain_gauge_lst, 'plot_inst': plot_inst, 'alpha': alpha}

    # surficial plot
    surficial = False             ### True if to plot surficial
    markers = 'all'    ### specifiy markers; 'all' if all markers
    surficial_props = {'to_plot': surficial, 'markers': markers}
    
    
    # from csv
    from_csv = False             ### True if to plot surficial
    fname = 'DAD_surficialdata.csv'
    hist = 'DAD_markerhistory.csv'
    markers = 'all'               ### specifiy markers; 'all' if all markers
    hide_mute = False              ### Hide muted points
    zero_repo = False              ### Set displacement to zero for repositioned points
    csv_props = {'to_plot': from_csv, 'markers': markers, 'fname':fname,
                 'hide_mute': hide_mute, 'zero_repo': zero_repo, 'hist': hist}
    
      # subsurface plot
    
    mirror_xz = False ### True or False
    mirror_xy = False ### True or False
    
    # subsurface displacement
    disp = False                 ### True if to plot subsurface displacement
    ### specifiy tsm name and axis; 'all' if all nodes
    disp_tsm_axis = {'luntd': {'xz': [9,18,19], 'xy': [9,18,19]}} #'inata': {'xz': [6,14]}} #{'xz': [7,8,9], 'xy': [7,8,9]},
            #'blcsb': {'xy': range(1,11), 'xz': range(1,11)}}
    
    # subsurface cumulative displacement
    cml = False     ### True if to plot subsurface cumulative displacement
    ### specifiy tsm name and axis; 'all' if all nodes
    cml_tsm_axis = {'luntd': {'xz': [9,18,19], 'xy': [9,18,19]}}# 'inata': {'xz': [6,14]}} 
    #'sagtb': {'xz':range(3,20)}} #'magtb': {'xy': range(11,16), 'xz': range(11,16)}}
    
    subsurface_props = {'disp': {'to_plot': disp, 'disp_tsm_axis': disp_tsm_axis},
                       'cml': {'to_plot': cml, 'cml_tsm_axis': cml_tsm_axis},
                        'end': subsurface_end, 'mirror_xz': mirror_xz,
                        'mirror_xy': mirror_xy}
    
    df = main(site.lower(), start, end, rainfall_props, surficial_props, subsurface_props, csv_props, [event_lst, event_color], span_list)
    
################################################################################

#    def ts_range(df, lst):
#        lst.append((pd.to_datetime(df['ts'].values[0]), pd.to_datetime(df['ts'].values[0]) + timedelta(hours=0.5)))
#        return lst
#    
#    def stitch_intervals(ranges):
#        result = []
#        cur_start = -1
#        cur_stop = -1
#        for start, stop in sorted(ranges):
#            if start != cur_stop:
#                result.append((start,stop))
#                cur_start, cur_stop = start, stop
#            else:
#                result[-1] = (cur_start,stop)
#                cur_stop = max(cur_stop,stop)
#        return result
#    
#    rain = get_rain_df('pintaw', '2016-03-15', '2017-09-13')
#    query = "SELECT * FROM rain_props where name = '%s'" %'pin'
#    twoyrmax = qdb.GetDBDataFrame(query)['max_rain_2year'].values[0]
#    halfmax = twoyrmax/2
#    
#    halfT = rain[(rain.one >= halfmax/2)|(rain.three >= halfmax)]
#    
#    lst = []
#    halfTts = halfT.groupby('ts', as_index=False)
#    rain_ts_range = halfTts.apply(ts_range, lst=lst)
#    rain_ts_range = rain_ts_range[0]
#    rain_ts_range = rain_ts_range[1::]
#    halfT_range = stitch_intervals(rain_ts_range)
