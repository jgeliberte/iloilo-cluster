"""
"""

import re
import copy
from datetime import timedelta, datetime, time, date

from src.utils.monitoring import (
    get_monitoring_releases, check_if_onset_release,
    get_next_ground_data_reporting, get_next_ewi_release_ts,
    process_trigger_list)
from src.utils.sites import build_site_address, get_sites_data
from src.utils.analysis import get_ground_data_noun
from src.utils.extra import (
    retrieve_data_from_memcache, format_timestamp_to_string,
    round_to_nearest_release_time, convert_ampm_to_noon_midnight
)
from src.utils.narratives import write_narratives_to_db
from src.models.ewi import (OnDemandIdentifier)

BULLETIN_RESPONSES = retrieve_data_from_memcache("bulletin_responses")

RELEASE_INTERVAL_HOURS = retrieve_data_from_memcache(
    "dynamic_variables", {"var_name": "RELEASE_INTERVAL_HOURS"}, retrieve_attr="var_value")


def get_greeting(data_ts=datetime.now, is_midnight_evening=True, language="fil"):
    """
    Provides the appropriate greeting for several message templates

    Args:
        data_ts (datetime)
        is_midnight_evening (boolean)    specifies if midnight has evening greeting
        language (string)   "fil" for "Filipino", "eng" for "English"

    returns:
        greeting (string)
    """

    hour = data_ts.hour
    greeting = ""
    conversion = {
        "umaga": "morning",
        "tanghali": "afternoon",
        "hapon": "afternoon",
        "gabi": "evening"
    }

    if is_midnight_evening and hour == 0:
        greeting = "gabi"
    elif hour <= 11:
        greeting = "umaga"
    elif hour == 12:
        greeting = "tanghali"
    elif hour < 18:
        greeting = "hapon"
    else:
        greeting = "gabi"

    if language == "eng":
        greeting = conversion[greeting]

    return greeting


def get_highest_trigger(trigger_list_str):
    triggers_arr = re.sub(r"0|x|rx", "", trigger_list_str)

    triggers = []
    for letter in triggers_arr:
        int_symbol = retrieve_data_from_memcache(
            "internal_alert_symbols", {"alert_symbol": letter})

        trigger_symbol = int_symbol["trigger_symbol"]

        sym = {
            "alert_level": trigger_symbol["alert_level"],
            "alert_symbol": int_symbol["alert_symbol"],
            "hierarchy_id": trigger_symbol["trigger_hierarchy"]["hierarchy_id"],
            "internal_sym_id": int_symbol["internal_sym_id"]
        }

        triggers.append(sym)

    sorted_arr = sorted(triggers, key=lambda i: (
        -i["alert_level"], i["hierarchy_id"]))

    return sorted_arr[0]


def create_ewi_message(release_id=None):
    """
    Returns ewi message for event, routine monitoring.

    Arg:
        release_id (Int) - by not providing a release_id, you are basically asking for a template.
        In this case, routine ewi sms template.
    """
    address = "(site_location)"
    alert_level = 0
    data_ts = datetime.combine(date.today(), time(12, 0))
    greeting = get_greeting(data_ts)
    ts_str = format_timestamp_to_string(data_ts)
    monitoring_status = 2
    is_onset = False
    if release_id:
        release_id = int(release_id)
        release = get_monitoring_releases(
            release_id=release_id, load_options="ewi_sms_bulletin")
        data_ts = release.data_ts
        release_time = release.release_time

        event_alert = release.event_alert
        pub_sym_id = event_alert.pub_sym_id
        event_alert_id = event_alert.event_alert_id
        alert_level = event_alert.public_alert_symbol.alert_level

        event = event_alert.event
        site = event.site
        validity = event.validity
        monitoring_status = event.status

        is_onset = check_if_onset_release(event_alert_id, release_id, data_ts)
        if is_onset:
            release_interval_hours = retrieve_data_from_memcache(
                "dynamic_variables", {"var_name": "RELEASE_INTERVAL_HOURS"},
                retrieve_attr="var_value")
            if data_ts.hour > release_time.hour:
                rounded_data_ts = round_to_nearest_release_time(
                    data_ts, release_interval_hours)
            else:
                rounded_data_ts = data_ts

            updated_data_ts = rounded_data_ts.replace(
                hour=release_time.hour, minute=release_time.minute)
        else:
            updated_data_ts = data_ts + timedelta(minutes=30)

        greeting = get_greeting(updated_data_ts)
        address = build_site_address(site)
        ts_str = format_timestamp_to_string(updated_data_ts)

    # No ground measurement reminder if A3
    ground_reminder = ""
    if alert_level != 3:
        if release_id:
            g_data = get_ground_data_noun(site.site_id)
        else:
            g_data = "ground measurement/ground observation"
        ground_reminder = f"Inaasahan namin ang pagpapadala ng LEWC ng {g_data} "

        is_alert_0 = alert_level == 0
        try:
            reporting_ts, modifier = get_next_ground_data_reporting(
                updated_data_ts - timedelta(hours=0.5), is_onset, is_alert_0=is_alert_0, include_modifier=True)
        except Exception as err:
            reporting_ts, modifier = get_next_ground_data_reporting(
                data_ts, is_onset, is_alert_0=is_alert_0, include_modifier=True)

        reporting_time = format_timestamp_to_string(
            reporting_ts, time_only=True)

        if alert_level in [1, 2]:
            ground_reminder += f"{modifier} bago mag-{reporting_time}. "
        else:
            clause = "para sa"
            reason = " susunod na routine monitoring"

            reporting_str = ""

            if release_id and monitoring_status == 2:  # if monitoring status is event
                reporting_date = format_timestamp_to_string(
                    reporting_ts, date_only=True)
                modifier = f"bukas, {reporting_date},"

                day = (updated_data_ts.date() - validity.date()).days

                if day == 0:
                    extended_day = "unang"
                elif day == 1:
                    extended_day = "ikalawang"
                elif day == 2:
                    extended_day = "huling"

                if day in [0, 1, 2]:
                    reason = f" {extended_day} araw ng 3-day extended monitoring"
                    reporting_str = f"{modifier} bago mag-{reporting_time} "

            ground_reminder += f"{reporting_str}{clause}{reason}."

    desc_and_response = ""
    next_ewi = ""
    please_acknowledge = ""
    trigger_list_str = None

    if alert_level > 0:
        trigger_list_str = release.trigger_list
        trigger_list_str = process_trigger_list(
            trigger_list_str, include_ND=False)

        highest_trig = get_highest_trigger(trigger_list_str)
        ewi_trig = retrieve_data_from_memcache(
            "bulletin_triggers", {"internal_sym_id": highest_trig["internal_sym_id"]})
        trigger_desc = ewi_trig["sms"]

        res = [
            row for row in BULLETIN_RESPONSES if row["pub_sym_id"] == pub_sym_id].pop()
        ewi_response = copy.deepcopy(res)
        response = ewi_response["recommended"].upper()
        desc_and_response = f" {trigger_desc}. Ang recommended response ay {response}"

        final_data_ts = updated_data_ts
        if is_onset:
            final_data_ts = updated_data_ts.replace(
                hour=release_time.hour, minute=release_time.minute)

        next_ewi_release_ts = get_next_ewi_release_ts(final_data_ts - timedelta(hours=0.5), is_onset)
        next_ts = format_timestamp_to_string(
            next_ewi_release_ts, time_only=True)

        if next_ewi_release_ts - updated_data_ts <= timedelta(hours=0.5):
            temp_ts = next_ewi_release_ts + \
                timedelta(hours=4)
            next_ts = format_timestamp_to_string(
                temp_ts, time_only=True)

        if next_ewi_release_ts - updated_data_ts > timedelta(hours=4):
            temp_ts = next_ewi_release_ts + \
                timedelta(hours=4)
            next_ts = format_timestamp_to_string(
                temp_ts, time_only=True)

        next_ewi += f"Ang susunod na early warning information ay mamayang {next_ts}."

        if updated_data_ts.hour == 12:
            please_acknowledge = "Paki-reply po kung natanggap ninyo itong EWI. "

    third_line = ""
    if ground_reminder != "" or next_ewi != "":
        third_line += f"{ground_reminder}{next_ewi}\n\n"

    ewi_message = (f"Magandang {greeting} po.\n\n"
                   f"Alert {alert_level} ang alert level sa {address} ngayong {ts_str}."
                   f"{desc_and_response}\n\n"
                   f"{third_line}{please_acknowledge}Salamat.")
                   
    if trigger_list_str == "D" or trigger_list_str == "D0":
        ewi_message = determine_od_ewi_template(release_id, ewi_message)
        
    return ewi_message

def determine_od_ewi_template(release_id, ewi_message):
    
    try:
        od = OnDemandIdentifier(release_id)
        ondemand_eq = od.identifier()
        
        if ondemand_eq['od_eq_id'][0] is not None:
            ewi_message = ewi_message.replace('<reason_for_monitoring>', 'naramdamang paglindol')
        else:
            ewi_message = ewi_message.replace('<reason_for_monitoring>', 'nakaraan o kasalukuyang ulan')
    except Exception as err:
        ewi_message = ewi_message.replace('<reason_for_monitoring>', 'nakaraan o kasalukuyang ulan')

    return ewi_message


def create_ground_measurement_reminder(site_id, monitoring_type, ts, ground_data_noun=None):
    """
    Params:
        site_id (int)
        monitoring_type (str):      "routine" or "event"
        ts (datetime)
        ground_data_noun (str, optional)

    Returns:
        Ground measurement reminder message (str)
    """

    greeting = "umaga"
    hour = ts.hour
    if not ground_data_noun:
        ground_data_noun = get_ground_data_noun(site_id)

    site_info = get_sites_data(site_id=site_id, raise_load=True)
    address = build_site_address(site_info, limit_to_barangay=True)

    if hour == 5:
        dt_time = "07:30 AM"
    elif hour == 9:
        dt_time = "11:30 AM"
    else:
        greeting = "hapon"
        dt_time = "03:30 PM"

    message = f"Magandang {greeting}. Inaasahan ang pagpapadala ng " + \
        f"{address} ng {ground_data_noun} " + \
        f"bago mag-{dt_time} para sa {monitoring_type} monitoring. Agad ipaalam kung may " + \
        "makikitang manipestasyon ng paggalaw ng lupa o iba pang pagbabago sa site. Salamat."

    return message


def insert_ewi_sms_narrative(release_id, user_id, recipients):
    """
    """

    release = get_monitoring_releases(
        release_id=release_id, load_options="ewi_narrative")
    data_ts = release.data_ts
    event_alert = release.event_alert
    public_alert_level = event_alert.public_alert_symbol.alert_level

    event = event_alert.event
    event_id = event.event_id
    site_id = event.site_id
    first_release = list(
        sorted(event_alert.releases, key=lambda x: x.data_ts))[0]

    # Get data needed to see if onset
    first_data_ts = first_release.data_ts
    is_onset = first_data_ts == data_ts and public_alert_level > 0

    ewi_sms_detail = " onset"
    if not is_onset:
        data_ts = round_to_nearest_release_time(
            data_ts, interval=4)
        release_hour = convert_ampm_to_noon_midnight(data_ts)
        ewi_sms_detail = f" {release_hour}"

    formatted_recipients = format_recipients_for_narrative(recipients)
    narrative = f"Sent{ewi_sms_detail} EWI SMS to {formatted_recipients}"

    write_narratives_to_db(
        site_id=site_id,
        timestamp=datetime.now(),
        narrative=narrative,
        type_id=1,
        user_id=user_id,
        event_id=event_id
    )


def format_recipients_for_narrative(recipients):
    """
    """

    my_set = set()
    for row in recipients:
        orgs = row["data"]["organizations"]

        if orgs:
            org = orgs[0]
            temp = org["organization"]
            name = temp["name"]
            scope = temp["scope"]

            pre = ""
            if name == "lgu":
                if scope == 1:
                    pre = "B"
                elif scope == 2:
                    pre = "M"
                elif scope == 3:
                    pre = "P"

            pre += name.upper()
            my_set.add(pre)

    return ', '.join(my_set)


def format_alert_fyi_message(ts, sites, internal_sym_id, action):
    """
    Creates FYI message to Dynaslope bosses
    about alert raising and/or lowering

    Args:
        ts (datetime)
        sites (list)        list of site ids
        internal_sym_id (int)    from internal_symbols table
        action              raised/lowered

    Returns:
        FYI message (string)
    """

    greeting = get_greeting(data_ts=ts, language="eng")
    time_str = ts.strftime("%I:%M %p")
    date_str = ts.strftime("%B %d, %Y")

    locations = []
    for site_id in sites:
        site_info = get_sites_data(site_id=site_id, raise_load=True)
        address = build_site_address(site_info)
        locations.append(address)
    if len(locations) > 1:
        auxillary = ", are"
        loc_str = ": "
    else:
        auxillary = " is"
        loc_str = " "

    loc_str += "; ".join(locations)

    trigger_temp = retrieve_data_from_memcache(
        "bulletin_triggers", filters_dict={
            "internal_sym_id": internal_sym_id},
        retrieve_one=True)
    if action == "raised":
        reason = trigger_temp["cause"]
        alert_level = trigger_temp["internal_sym"]["trigger_symbol"]["alert_level"]
        reason_clause = f"{alert_level} due to {reason}"
    else:
        reason = trigger_temp["lowering_fyi"]
        reason_clause = f"0. {reason}"

    message = (f"Good {greeting}! As of {time_str} today, "
               f"{date_str}, alert level in{loc_str}{auxillary} "
               f"now {action} to Alert {reason_clause}.")

    return message
