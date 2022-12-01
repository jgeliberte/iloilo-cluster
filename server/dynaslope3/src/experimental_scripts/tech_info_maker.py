"""
Tech Info Maker (Py3) version 0.2
======
For use of Dynaslope Early Warning System
Receives a trigger class and uses its details to
generate technical information for use in the
alert release bulletins.

August 2019
"""

from datetime import timedelta
from connection import DB
# from run import APP
from src.models.analysis import (
    RainfallAlerts as ra,
    NodeAlerts as na,
    TSMSensors as tsma)
from src.models.monitoring import MonitoringMoms as mm
from src.utils.rainfall import get_rainfall_gauge_name
from src.utils.surficial import get_marker_alerts, get_surficial_markers
from src.utils.monitoring import round_to_nearest_release_time
from src.utils.extra import var_checker, retrieve_data_from_memcache


# Every how many hours per release
RELEASE_INTERVAL_HOURS = retrieve_data_from_memcache(
    "dynamic_variables", {"var_name": "RELEASE_INTERVAL_HOURS"}, retrieve_attr="var_value")

#####################################
# DATA PROCESSING CODES BEYOND HERE #
#####################################


def get_on_demand_tech_info(on_demand_details):
    """
    """
    # on_demand_details

    return on_demand_details


def get_earthquake_tech_info(earthquake_details):
    """
    """

    latitude = earthquake_details["latitude"]
    longitude = earthquake_details["longitude"]
    distance = earthquake_details["distance"]
    critical_distance = earthquake_details["critical_distance"]

    return f"Site is {distance} km away from earthquake at " + \
        f"{latitude} N, {longitude} E (inside critical radius of {critical_distance} km)"


def get_moms_tech_info(moms_alert_details):
    """
    Sample
    """
    m2_triggers_features = []
    m3_triggers_features = []
    moms_tech_info = {}
    moms_parts = []

    for item in moms_alert_details:
        feature = item.moms_instance.feature.feature_type
        if item.op_trigger == 2:
            m2_triggers_features.append(feature)
        elif item.op_trigger == 3:
            m3_triggers_features.append(feature)

    significant = ", ".join(m2_triggers_features)
    critical = ", ".join(m3_triggers_features)

    if m3_triggers_features:
        critical_word = "critical"
        if len(m3_triggers_features) == 1:
            critical_word = critical_word.capitalize()
        moms_parts.append(f"{critical_word} ({critical})")

    if m2_triggers_features:
        significant_word = "significant"
        if len(m2_triggers_features) == 1:
            significant_word = significant_word.capitalize()
        moms_parts.append(f"{significant_word} ({significant})")

    multiple = ""
    feature = "feature"
    if sum(1 for d in moms_alert_details if d.op_trigger >= 2) > 1:
        multiple = "Multiple "
        feature = "features"

    day = " and ".join(moms_parts)
    moms_tech_info = f"{multiple}{day} {feature} observed in site"
    return moms_tech_info


def get_moms_alerts(site_id, latest_trigger_ts):
    """
    Get MOMS alerts
    """
    moms_alerts_list = []

    # op_trigger is same concept with alert_level
    moms_alerts = mm.query.filter(
        mm.observance_ts == latest_trigger_ts, mm.op_trigger > 0)

    for item in moms_alerts.all():
        if item.moms_instance.site_id == site_id:
            moms_alerts_list.append(item)

    return moms_alerts_list


def get_surficial_tech_info(surficial_alert_details, site_id):
    """
    g triggers or surficial triggers tech info
    """

    tech_info = []
    surficial_tech_info = ""
    markers = get_surficial_markers(site_id=site_id)
    for item in surficial_alert_details:
        name_row = next(
            x for x in markers if x.marker_id == item.marker_data.marker_id)
        disp = item.displacement
        timestamp = '{:.2f}'.format(item.time_delta)
        tech_info.append(
            f"Marker {name_row.marker_name}: {disp} cm difference in {timestamp} hours")

        surficial_tech_info = '; '.join(tech_info)

    return surficial_tech_info


def get_rainfall_alerts(site_id, latest_trigger_ts):
    """
    Query rainfall alerts
    Non-Testable
    """
    rain_alerts = ra.query.filter(
        ra.site_id == site_id, ra.ts == latest_trigger_ts).all()

    return rain_alerts


def get_rainfall_tech_info(rainfall_alert_details, site_id):
    """
    Sample
    """
    one_day_data = None
    three_day_data = None

    if not rainfall_alert_details:
        raise Exception(f"Code flow reaching rainfall tech info WITHOUT any "
                        f"ENTRY on rainfall_alerts table.")

    for item in rainfall_alert_details:
        days = []
        cumulatives = []
        thresholds = []

        rain_gauge_name, distance = get_rainfall_gauge_name(item, site_id)

        # Not totally sure if there is always only one entry of a and b per rainfall ts
        # if yes, this can be improved.
        if item.rain_alert == "a":
            one_day_data = item

        if item.rain_alert == "b":
            three_day_data = item

        if one_day_data is not None:
            days.append("1-day")
            cumulatives.append('{:.2f}'.format(one_day_data.cumulative))
            thresholds.append('{:.2f}'.format(one_day_data.threshold))

        if three_day_data is not None:
            days.append("3-day")
            cumulatives.append('{:.2f}'.format(three_day_data.cumulative))
            thresholds.append('{:.2f}'.format(three_day_data.threshold))

    day = " and ".join(days)
    cumulative = " and ".join(cumulatives)
    threshold = " and ".join(thresholds)

    try:
        formatted_distance = "{:.2f}".format(distance)
    except Exception as err:
        formatted_distance = "0.00"

    rain_tech_info = {}
    rain_tech_info["rain_gauge"] = rain_gauge_name
    rain_tech_info["tech_info_string"] = (f"{rain_gauge_name} ({str(formatted_distance)} km away): {day} cumulative rainfall "
                                          f"({cumulative} mm) exceeded threshold ({threshold} mm)")

    return rain_tech_info


def get_subsurface_node_alerts(site_id, start_ts, latest_trigger_ts, alert_level):
    """
    Update: Returns a list of node alerts
    Returns list of sensors with its corresponding node alerts
    """
    # NOTE: OPTIMIZE: Use TSMSensor instead of NodeAlerts OR use join() query
    try:
        tsm_sensors = tsma.query.filter(tsma.site_id == site_id).all()

        tsm_node_alerts = []
        for sensor in tsm_sensors:
            sensor_node_alerts = sensor.node_alerts.filter(
                DB.or_(na.disp_alert == alert_level, na.vel_alert == alert_level)) \
                .order_by(DB.desc(na.na_id)) \
                .filter(start_ts <= na.ts, na.ts <= latest_trigger_ts).all()

            if sensor_node_alerts:  # If there are no node alerts on sensor, skip.
                # If there is, remove duplicate node alerts. We only need the latest.
                unique_list = []
                comparator = []
                for item in sensor_node_alerts:
                    com = item.node_id
                    comparator.append(com)
                    if not (com in comparator and comparator.count(com) > 1):
                        unique_list.append(item)
                sensor_node_alerts = unique_list

                tsm_node_alerts.extend(sensor_node_alerts)
    except:
        raise

    return tsm_node_alerts


def format_node_details(node_alerts):
    """
    Sample
    """
    node_details = []
    tsm_name_list = []

    # NOTE: OPTIMIZE
    for node_alert in node_alerts:
        tsm_name_list.append(node_alert.tsm_sensor.logger.logger_name)

    for i in tsm_name_list:
        col_list = []
        for node_alert in node_alerts:
            if node_alert.tsm_sensor.logger.logger_name == i:
                col_list.append(node_alert)

    if len(col_list) == 1:
        node_details.append(f"{i.upper()} (node {col_list[0].node_id})")
    else:
        sorted_nodes = sorted(col_list, key=lambda x: x.node_id)
        node_details.append(
            f"{i.upper()} (nodes {', '.join(str(v.node_id) for v in sorted_nodes)})")

    return ", ".join(node_details)


def formulate_subsurface_tech_info(node_alert_group):
    """
    Sample
    """
    both_trigger = []
    dis_trigger = []
    vel_trigger = []

    for node_alert in node_alert_group:
        disp_alert = node_alert.disp_alert
        vel_alert = node_alert.vel_alert
        if disp_alert > 0 and vel_alert > 0:
            both_trigger.append(node_alert)

        if disp_alert > 0 and vel_alert == 0:
            dis_trigger.append(node_alert)

        if disp_alert == 0 and vel_alert > 0:
            vel_trigger.append(node_alert)

    node_details = []

    if both_trigger:
        dispvel_tech = format_node_details(both_trigger)
        node_details += ['%s exceeded displacement and velocity threshold' %
                         (dispvel_tech)]

    if dis_trigger:
        disp_tech = format_node_details(dis_trigger)
        node_details += ['%s exceeded displacement threshold' % (disp_tech)]

    if vel_trigger:
        vel_tech = format_node_details(vel_trigger)
        node_details += ['%s exceeded velocity threshold' % (vel_tech)]

    node_details = '; '.join(node_details)

    return node_details


def get_subsurface_tech_info(subsurface_node_alerts):
    """
    Sample
    """

    subsurface_tech_info = formulate_subsurface_tech_info(
        subsurface_node_alerts)

    return subsurface_tech_info


def main(trigger, special_details=None):
    """
    Return tech_info
    """
    global RELEASE_INTERVAL_HOURS
    release_interval = RELEASE_INTERVAL_HOURS

    has_special_details = False
    if special_details:
        has_special_details = True

    site_id = trigger.site_id
    latest_trigger_ts = trigger.ts_updated
    trigger_source = trigger.trigger_symbol.trigger_hierarchy.trigger_source
    alert_level = trigger.trigger_symbol.alert_level

    if trigger_source == 'subsurface':
        # According to Meryll update_ts - 3 hours so mas malawak pa ito
        start_ts = latest_trigger_ts - timedelta(hours=release_interval)
        subsurface_node_alerts = get_subsurface_node_alerts(
            site_id, start_ts, latest_trigger_ts, alert_level)
        technical_info = get_subsurface_tech_info(
            subsurface_node_alerts)

    elif trigger_source == 'rainfall':
        # Something special with rainfall. Attaches data source with the tech_info
        # technical_info = {
        #     "rain_gauge": "Sample",
        #     "tech_info_string": "Sample"
        # }
        rainfall_alerts = get_rainfall_alerts(site_id, latest_trigger_ts)
        technical_info = get_rainfall_tech_info(rainfall_alerts, site_id)

    elif trigger_source == 'surficial':
        # technical_info = "Sample tech info"
        surficial_alert_details = get_marker_alerts(
            site_id, latest_trigger_ts, alert_level, check_for_g0t_alerts=True)
        technical_info = get_surficial_tech_info(
            surficial_alert_details, site_id)

    elif trigger_source == 'moms':
        if not has_special_details:
            moms_alert_details = get_moms_alerts(site_id, latest_trigger_ts)
        else:
            moms_alert_details = special_details
        technical_info = get_moms_tech_info(moms_alert_details)

    elif trigger_source == 'earthquake':
        if not has_special_details:
            raise "No earthquake details saved"
        else:
            earthquake_details = special_details

        technical_info = get_earthquake_tech_info(earthquake_details)
    else:
        raise Exception("Something wrong in tech_info_maker")

    return technical_info
