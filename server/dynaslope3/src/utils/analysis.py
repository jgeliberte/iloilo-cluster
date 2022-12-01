"""
Utility code for analysis
"""

from datetime import timedelta

from src.utils.surficial import (
    check_if_site_has_active_surficial_markers,
    get_surficial_data
)
from src.utils.manifestations_of_movements import get_moms_report


def check_ground_data_and_return_noun(site_id, timestamp, hour, minute):
    """
    Returns a string that describes what ground data is available on site
    (either "ground measurement" or "ground observation")
    and ground data for specific timestamp, if available

    Returns:
        ground_data_noun (string):     either "ground measurement" or "ground observation"
        ground_data_result (object):    surficial data or moms data or null
    """

    ground_data_noun = get_ground_data_noun(site_id=site_id)

    if ground_data_noun == "ground measurement":
        start_ts = timestamp - timedelta(hours=hour, minutes=minute)
        result = get_surficial_data(
            site_id=site_id, end_ts=timestamp, start_ts=start_ts,
            ts_order="desc", limit=1, anchor="marker_observations")
    else:
        result = get_moms_report(timestamp,
                                 timedelta_hour=hour, minute=hour, site_id=site_id)

    return ground_data_noun, result


def get_ground_data_noun(site_id):
    """
    Returns a string that describes what ground data is available on site
    (either "ground measurement" or "ground observation")

    Returns: string
    """

    has_active_markers = check_if_site_has_active_surficial_markers(
        site_id=site_id)
    g_data = "ground measurement" if has_active_markers else "ground observation"

    return g_data
