"""
API for handling bulletin email
"""

from datetime import datetime
from flask import Blueprint, jsonify
from config import APP_CONFIG
from instance.config import EMAILS
from src.utils.emails import get_email_subject, remove_file_from_temp
from src.utils.monitoring import get_monitoring_releases
from src.utils.sites import build_site_address
from src.utils.bulletin import download_monitoring_bulletin
from src.utils.extra import var_checker, round_to_nearest_release_time
from src.utils.contacts import get_bulletin_recipients

BULLETIN_EMAIL = Blueprint("bulletin_email", __name__)


@BULLETIN_EMAIL.route("/bulletin/download_bulletin/<release_id>", methods=["GET"])
def wrap_download_bulletin(release_id):
    """
    Function that lets users download bulletin by release id
    """

    try:
        ret = download_monitoring_bulletin(release_id=release_id)
        remove_file_from_temp(
            APP_CONFIG["bulletin_save_path"] + f"/{release_id}")
        return ret
    except KeyError:
        return "Bulletin download FAILED."
    except Exception as err:
        raise err


def prepare_onset_message(release_data, address, site_alert_level):
    """
    Subset function of get_bulletin_email_body.
    Prepares the onset message.
    """

    onset_msg = ""
    release_triggers = release_data.triggers

    highest_trigger = next(iter(sorted(release_triggers,
                                       key=lambda x: x.internal_sym.trigger_symbol.alert_level,
                                       reverse=True)))

    combined = datetime.combine(
        release_data.data_ts.date(), release_data.release_time)
    f_data_ts = datetime.strftime(combined, "%B %e, %Y, %I:%M %p")
    cause = highest_trigger.internal_sym.bulletin_trigger.first().cause

    onset_msg = f"As of {f_data_ts}, {address} is under {site_alert_level} based on {cause}.\n"

    return onset_msg


def prepare_base_email_body(address, alert_level, data_ts):
    """
    Prepare the basic bulletin email content.
    """

    f_r_time = datetime.strftime(data_ts, "%B %e, %Y, %I:%M %p")
    return f"Dynaslope Bulletin for {f_r_time}\n{alert_level} - {address}"


@BULLETIN_EMAIL.route("/bulletin_email/get_bulletin_email_details/<release_id>", methods=["GET"])
def get_bulletin_email_details(release_id):
    """
    Function for composing the email's recipients,
    subject, and mail body
    """

    recipients = []
    mail_body = ""
    subject = ""
    filename = ""

    bulletin_release_data = get_monitoring_releases(
        release_id=release_id)  # TODO: Load options load_options="ewi_narrative"
    event_alert = bulletin_release_data.event_alert

    first_ea_release = list(
        sorted(event_alert.releases, key=lambda x: x.data_ts))[0]
    event = event_alert.event
    event_id = event.event_id
    event_start = event.event_start

    # Get data needed to prepare base message
    site = event.site
    site_address = build_site_address(site)
    p_a_level = event_alert.public_alert_symbol.alert_level
    site_alert_level = f"Alert {p_a_level}"
    data_ts = bulletin_release_data.data_ts

    # Get data needed to see if onset
    first_ea_data_ts = first_ea_release.data_ts
    data_ts = bulletin_release_data.data_ts
    is_onset = first_ea_data_ts == data_ts

    # MAIL BODY
    mail_body = ""
    body_ts = data_ts
    if is_onset and p_a_level != 0:  # prevent onset message from appearing on A0 lowering bulletin
        onset_msg = prepare_onset_message(
            bulletin_release_data,
            site_address,
            site_alert_level
        )

        mail_body = f"{onset_msg}\n "
        body_ts = datetime.combine(
            data_ts.date(), bulletin_release_data.release_time)
        file_time = body_ts
    else:
        file_time = round_to_nearest_release_time(data_ts, 4)
        body_ts = file_time

    mail_body += prepare_base_email_body(
        site_address, site_alert_level, body_ts)

    # GET THE SUBJECT NOW
    subject = get_email_subject(mail_type="bulletin", details={
        "site_code": site.site_code,
        "date": event_start.strftime("%d %b %Y").upper()
    })

    # GET THE FILENAME NOW
    file_time = file_time.strftime("%I%p")
    file_date = data_ts.strftime("%d%b%y")
    filename = f"{site.site_code.upper()}_{file_date}_{file_time}".upper() + ".pdf"

    # GET THE RECIPIENTS NOW
    # if APP_CONFIG["is_live_mode"]:
    #     recipients.extend(EMAILS["director_and_head_emails"])
    #     if is_onset and p_a_level > 0:
    #         recipients.extend(EMAILS["dynaslope_groups"])
    # else:
    # NOTE to front-end. CHECK if TEST SERVER by using typeof object.
    # recipients.append(EMAILS["dev_email"])
    is_live_mode = APP_CONFIG["is_live_mode"]
    emails = get_bulletin_recipients(site_codes=[site.site_code],
                                     is_live_mode=is_live_mode,
                                     is_onset=is_onset,
                                     p_a_level=p_a_level,
                                     event_id=event_id)

    bulletin_email_details = {
        "recipients": emails,
        "mail_body": mail_body,
        "subject": subject,
        "file_name": filename,
        "narrative_details": {
            "event_id": event_id,
            "is_onset": is_onset,
            "public_alert_level": p_a_level,
            "event_id": event_id,
            "file_time": file_time
        }
    }

    return jsonify(bulletin_email_details)
