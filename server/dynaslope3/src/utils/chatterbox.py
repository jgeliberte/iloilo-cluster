"""
Utils of Chatterbox
"""

import json
from datetime import datetime, timedelta
from sqlalchemy import (
    bindparam, literal, text
)
from sqlalchemy.orm import joinedload, raiseload
from connection import DB
from flask import Blueprint, jsonify, request
from src.models.inbox_outbox import (
    SmsInboxUsers, SmsOutboxUsers, SmsOutboxUserStatus,
    ViewLatestMessagesMobileID, TempLatestMessagesSchema,
    SmsInboxUserTags, GetSMSInboxForQASchema, SmsInboxUserTagsSchema,
    SmsTags, SmsOutboxUserTags, SmsOutboxUserTagsSchema,
    SmsUserUpdates, ViewLatestUnsentMsgsPerMobileID,
    SmsQueue, SmsQueueSchema
)
from src.models.users import Users, UserOrganizations
from src.models.sites import Sites
from src.models.mobile_numbers import (
    UserMobiles, MobileNumbers, MobileNumbersSchema)

from src.utils.contacts import get_mobile_numbers
from src.utils.extra import var_checker, retrieve_data_from_memcache


def get_sms_inbox_data(ts_start=None, ts_end=None):
    """
    Fetch SMS inbox data for QA
    """
    inbox_data = None
    if ts_start and ts_end:
        siu = SmsInboxUsers
        siut = SmsInboxUserTags
        um = UserMobiles
        users = Users
        uo = UserOrganizations
        sites = Sites
        st = SmsTags
        mn = MobileNumbers

        query = DB.session.query(
            siu.ts_sms.label("timestamp"), 
            siu.inbox_id,
            siu.sms_msg.label("message"),
            users.first_name.concat(' ' + users.last_name + ' - ' + mn.sim_num.label("mobile_number")).label("sender"), 
            uo.org_name.label("affiliation"),
            sites.site_code,
            st.tag,
        ) \
        .join(um, um.mobile_id == siu.mobile_id) \
        .join(users, users.user_id == um.user_id) \
        .join(uo, uo.user_id == users.user_id) \
        .join(sites, sites.site_id == uo.site_id) \
        .outerjoin(siut, siut.inbox_id == siu.inbox_id) \
        .outerjoin(st, st.tag_id == siut.tag_id) \
        .join(mn, mn.mobile_id == um.mobile_id) \
        .filter(siu.ts_sms >= ts_start, siu.ts_sms <= ts_end)

        inbox_data = GetSMSInboxForQASchema(many=True).dump(query.all())

    return inbox_data
    

def get_quick_inbox(inbox_limit=50, limit_inbox_outbox=True):
    """
    Quick inbox function
    """

    query_start = datetime.now()
    vlmmid = ViewLatestMessagesMobileID
    inbox_mobile_ids = vlmmid.query.outerjoin(
        UserMobiles, vlmmid.mobile_id == UserMobiles.mobile_id) \
        .outerjoin(Users).order_by(DB.desc(vlmmid.max_ts)).limit(inbox_limit).all()

    latest_inbox_messages = []
    for row in inbox_mobile_ids:
        mobile_id = row.mobile_id
        mobile_schema = get_user_mobile_details(mobile_id)

        msgs_schema = get_formatted_latest_mobile_id_message(
            mobile_id, limit_inbox_outbox)

        formatted = {
            "mobile_details": mobile_schema,
            "messages": msgs_schema
        }
        latest_inbox_messages.append(formatted)

    unsent_messages = get_formatted_unsent_messages()
    queued_messages = get_messages_on_queue()

    messages = {
        "inbox": latest_inbox_messages,
        "unsent": unsent_messages,
        "queue": queued_messages
    }

    query_end = datetime.now()

    print("")
    print("SCRIPT RUNTIME", (query_end - query_start).total_seconds())
    print("")

    return messages


def get_formatted_latest_mobile_id_message(mobile_id, limit_inbox_outbox=True, ts_start=None, ts_end=None):
    msgs = get_latest_messages(
        mobile_id, limit_inbox_outbox=limit_inbox_outbox,
        ts_start=ts_start, ts_end=ts_end)
    msgs_schema = TempLatestMessagesSchema(many=True).dump(msgs)

    return msgs_schema


def get_formatted_unsent_messages():
    query_start = datetime.now()

    unsent_messages_arr = get_unsent_messages(duration=1)
    unsent_messages = format_unsent_messages(unsent_messages_arr)

    query_end = datetime.now()

    print("")
    print("SCRIPT RUNTIME: GET UNSENT MESSAGES ",
          (query_end - query_start).total_seconds())
    print("")

    return unsent_messages


def get_unsent_messages(duration=1):
    """
    Args: duration (int) - in days
    """

    vlum = ViewLatestUnsentMsgsPerMobileID
    date_filter = datetime.now() - timedelta(days=duration)
    unsent_messages_arr = vlum.query.filter(
        vlum.ts_written > date_filter).order_by(vlum.ts_written).all()
    return unsent_messages_arr


def get_messages_schema_dict(msgs):
    msgs_schema = []

    query_tag_start = datetime.now()

    for msg in msgs:
        msg_schema = TempLatestMessagesSchema().dump(msg)
        msg_schema["tags"] = get_message_tags(msg)
        msgs_schema.append(msg_schema)

    query_tag_end = datetime.now()

    print("")
    print("SCRIPT RUNTIME: GET MESSAGE TAGS",
          (query_tag_end - query_tag_start).total_seconds())
    print("")

    return msgs_schema


def format_unsent_messages(message_arr):
    messages = []

    for row in message_arr:
        mobile_id = row.mobile_id
        mobile_schema = get_user_mobile_details(mobile_id)
        msg_schema = TempLatestMessagesSchema().dump(row)

        formatted = {
            "mobile_details": mobile_schema,
            "messages": [msg_schema]
        }

        messages.append(formatted)

    return messages


def get_user_mobile_details(mobile_id):
    """
    """

    user = DB.subqueryload("users").joinedload(
        "user", innerjoin=True)
    org = user.subqueryload("organizations")

    query = MobileNumbers.query.options(
        org.joinedload("site", innerjoin=True).raiseload("*"),
        org.joinedload("organization", innerjoin=True),
        user.subqueryload("teams").joinedload(
            "team", innerjoin=True), raiseload("*")
    ).filter_by(mobile_id=mobile_id)

    # if not include_inactive_numbers:
    #     query = query.join(UserMobiles).filter(UserMobiles.status == 1).options(
    #         DB.contains_eager(MobileNumbers.users))

    mobile_details = query.first()

    mobile_schema = MobileNumbersSchema(exclude=[
        "users.user.landline_numbers",
        "users.user.emails",
        "users.user.ewi_restriction"
    ]).dump(mobile_details)
    # NOTE EXCLUDE: "blocked_mobile"

    return mobile_schema


def get_latest_messages(
        mobile_id, messages_per_convo=20,
        batch=0, limit_inbox_outbox=False,
        ts_start=None, ts_end=None
):
    """
    """

    query_start = datetime.now()

    offset = messages_per_convo * batch

    siu = SmsInboxUsers
    sms_inbox = DB.session.query(
        siu.inbox_id.label("convo_id"),
        siu.inbox_id,
        bindparam("outbox_id", None),
        siu.mobile_id,
        siu.sms_msg,
        siu.ts_sms.label("ts"),
        siu.ts_sms.label("ts_received"),
        bindparam("ts_written", None),
        bindparam("ts_sent", None),
        literal("inbox").label("source"),
        bindparam("send_status", None)
    ).options(raiseload("*")).filter(siu.mobile_id == mobile_id)

    if ts_start:
        sms_inbox = sms_inbox.filter(siu.ts_sms >= ts_start)

    if ts_end:
        sms_inbox = sms_inbox.filter(siu.ts_sms <= ts_end)

    sms_inbox = sms_inbox.order_by(DB.desc(siu.ts_sms))

    if limit_inbox_outbox:
        sms_inbox = sms_inbox.limit(1)

    sou = SmsOutboxUsers
    sous = SmsOutboxUserStatus
    sms_outbox = DB.session.query(
        sous.stat_id.label("convo_id"),
        bindparam("inbox_id", None),
        sous.outbox_id,
        sous.mobile_id,
        sou.sms_msg,
        sou.ts_written.label("ts"),
        bindparam("ts_received", None),
        sou.ts_written,
        sous.ts_sent,
        literal("outbox").label("source"),
        sous.send_status
    ).options(raiseload("*")).join(sou).filter(sous.mobile_id == mobile_id)

    if ts_start:
        sms_outbox = sms_outbox.filter(sou.ts_written >= ts_start)

    if ts_end:
        sms_outbox = sms_outbox.filter(sou.ts_written <= ts_end)

    sms_outbox = sms_outbox.order_by(DB.desc(sous.outbox_id))

    if limit_inbox_outbox:
        sms_outbox = sms_outbox.limit(1)

    union = sms_inbox.union(sms_outbox).order_by(
        DB.desc(text("anon_1_ts"))).limit(messages_per_convo).offset(offset)

    query_end = datetime.now()

    print("")
    print("SCRIPT RUNTIME: GET LATEST MESSAGES",
          (query_end - query_start).total_seconds())
    print("")

    return union


def get_message_users_within_ts_range(ts_start=None, ts_end=None):
    """
    """

    siu = SmsInboxUsers
    sms_inbox = DB.session.query(siu.mobile_id.label(
        "mobile_id")).options(raiseload("*"))

    if ts_start:
        sms_inbox = sms_inbox.filter(siu.ts_sms >= ts_start)

    if ts_end:
        sms_inbox = sms_inbox.filter(siu.ts_sms <= ts_end)

    sms_inbox = sms_inbox.order_by(DB.desc(siu.ts_sms))

    sou = SmsOutboxUsers
    sous = SmsOutboxUserStatus
    sms_outbox = DB.session.query(
        sous.mobile_id.label("mobile_id")).options(raiseload("*")).join(sou)

    if ts_start:
        sms_outbox = sms_outbox.filter(sou.ts_written >= ts_start)

    if ts_end:
        sms_outbox = sms_outbox.filter(sou.ts_written <= ts_end)

    sms_outbox = sms_outbox.order_by(DB.desc(sous.outbox_id))

    union = sms_inbox.union(sms_outbox).group_by(DB.text("mobile_id"))

    return union


def get_message_tags(message):
    """
    """

    tags_list = []
    if message.source == "inbox":
        sms_tags = DB.session.query(SmsInboxUserTags).options(
            joinedload(SmsInboxUserTags.tag, innerjoin=True),
            raiseload("*")
        ).filter_by(inbox_id=message.inbox_id).all()
        tags_list = SmsInboxUserTagsSchema(
            many=True).dump(sms_tags)  # NOTE EXCLUDE: exclude=["inbox_message"]
    elif message.source == "outbox":
        sms_tags = DB.session.query(SmsOutboxUserTags).options(
            joinedload(SmsOutboxUserTags.tag, innerjoin=True),
            raiseload("*")
        ).filter_by(outbox_id=message.outbox_id).all()
        tags_list = SmsOutboxUserTagsSchema(
            many=True).dump(sms_tags)  # NOTE EXCLUDE: exclude=["outbox_message"]

    return tags_list


def get_message_tag_options(source=None):
    """
    """

    tags = SmsTags.query.options(DB.raiseload("*"))

    if source:
        tags = tags.filter_by(source=source)

    tags = tags.all()
    return tags


def get_sms_user_updates():
    """
    """
    # TODO: Group updates by mobile_id and source
    DB.session.flush()
    results = DB.session.query(SmsUserUpdates).filter_by(processed=0).order_by(
        SmsUserUpdates.update_id).limit(10).all()
    DB.session.commit()

    return results


def insert_sms_user_update(mobile_id, update_source, pk_id=0):
    """
    """

    row = SmsUserUpdates(
        mobile_id=mobile_id,
        update_source=update_source,
        pk_id=pk_id
    )

    DB.session.add(row)
    DB.session.commit()


def delete_sms_user_update(updates=None):
    """
    """

    if not updates:
        # SmsUserUpdates.query.delete()
        updates = SmsUserUpdates.query.filter_by(processed=1).all()

    for row in updates:
        row.processed = 1

    DB.session.commit()


def insert_message_on_database(obj):
    """
    Params:
    (object) with following attributes:
        sms_msg (str)
        recipient_list (array of objects):
            (object) attributes:
                mobile_id (int)
                gsm_id (int)
        priority (int)
    """

    sms_msg = obj["sms_msg"]
    recipient_list = obj["recipient_list"]

    try:
        priority = obj["priority"]
    except KeyError:
        priority = retrieve_data_from_memcache(
            "sms_priority",
            {"keyword": "default"},
            retrieve_attr="priority_id")

    new_msg = SmsOutboxUsers(
        ts_written=datetime.now(),
        source="central",
        sms_msg=sms_msg
    )

    DB.session.add(new_msg)
    DB.session.flush()

    outbox_id = new_msg.outbox_id

    for row in recipient_list:
        mobile_id = row["mobile_id"]
        gsm_id = row["gsm_id"]

        new_status = SmsOutboxUserStatus(
            outbox_id=outbox_id,
            mobile_id=mobile_id,
            gsm_id=gsm_id,
            priority=priority
        )

        DB.session.add(new_status)
        DB.session.flush()

    DB.session.commit()

    return outbox_id


def get_search_results(obj):
    """
    """

    start = datetime.now()
    print("Search start:", start)

    site_ids = obj["site_ids"]
    org_ids = obj["org_ids"]
    only_ewi_recipients = obj["only_ewi_recipients"]
    only_active_mobile_numbers = not obj["include_inactive_numbers"]
    ts_start = obj["ts_start"]
    ts_end = obj["ts_end"]
    string = obj["string_search"]
    tag = obj["tag_search"]
    mobile_number = obj["mobile_number_search"]
    names = obj["name_search"]
    offset = obj["updated_offset"]

    has_string_or_tag = string or tag["value"]
    mobile_ids = None
    if names:
        mobile_ids = list(map(lambda x: x["value"], names))
    # search for mobile_ids using ts range given
    # if site_ids OR org_ids not given
    # (yes OR, because lower code would just apply date filter)
    elif ts_start and ts_end and (not site_ids or not org_ids) \
            and not has_string_or_tag:
        print("Entered 1st")
        result = get_message_users_within_ts_range(
            ts_start=ts_start, ts_end=ts_end)
        mobile_ids = list(map(lambda x: x[0], result))

    search_results = []

    if has_string_or_tag:
        result = smart_search(
            string=string, tag=tag, org_ids=org_ids,
            site_ids=site_ids, only_ewi_recipients=only_ewi_recipients,
            offset=offset, ts_start=ts_start, ts_end=ts_end, mobile_ids=mobile_ids,
            only_active_mobile_numbers=only_active_mobile_numbers,
            mobile_number=mobile_number)

        mobile_details_dict = {}
        for row in result:
            formatted_row = format_conversation_result(row)
            mobile_id = row.mobile_id

            if mobile_id not in mobile_details_dict:
                temp_contact = get_mobile_numbers(
                    return_schema=True, mobile_ids=[mobile_id])

                if temp_contact:
                    temp = temp_contact[0]

                    contact = {
                        **temp["mobile_number"],
                        "users": [{
                            "user": temp["user"],
                            "priority": temp["priority"],
                            "status": temp["status"]
                        }]
                    }
                else:
                    number = MobileNumbers.query.options(
                        DB.raiseload("*")).filter_by(mobile_id=mobile_id)
                    contact = {
                        "mobile_id": mobile_id,
                        "sim_num": number.sim_num,
                        "gsm_id": number.gsm_id,
                        "users": []
                    }

                mobile_details_dict[mobile_id] = contact
            else:
                contact = mobile_details_dict[mobile_id]

            temp = {
                "messages": [formatted_row],
                "mobile_details": contact
            }

            search_results.append(temp)
    else:
        contacts = get_mobile_numbers(
            return_schema=True, mobile_ids=mobile_ids,
            site_ids=site_ids, org_ids=org_ids,
            only_ewi_recipients=only_ewi_recipients,
            only_active_mobile_numbers=only_active_mobile_numbers,
            mobile_number=mobile_number)

        for contact in contacts:
            mobile_number = contact["mobile_number"]
            mobile_id = mobile_number["mobile_id"]
            msgs_schema = get_formatted_latest_mobile_id_message(
                mobile_id, limit_inbox_outbox=True, ts_start=ts_start, ts_end=ts_end)

            temp = {
                "messages": msgs_schema,
                "mobile_details": {
                    **mobile_number,
                    "users": [{
                        "user": contact["user"],
                        "priority": contact["priority"],
                        "status": contact["status"]
                    }]
                }
            }

            search_results.append(temp)

    end = datetime.now()
    print("Search end:", end)
    duration = end - start
    print("Duration:", duration.total_seconds())
    return search_results


def resend_message(outbox_status_id):
    """
    """

    # NOTE: pointed to comms_db orig until GSM 3
    row = SmsOutboxUserStatus.query \
        .filter_by(stat_id=outbox_status_id).first()

    row.send_status = 0

    DB.session.commit()


def get_ewi_acknowledgements_from_tags(site_id, ts_start, ts_end):
    """
    """

    query = SmsInboxUserTags.query.options(DB.raiseload("*")) \
    .join(SmsTags).join(SmsInboxUsers) \
    .join(UserMobiles) \
    .join(Users) \
    .join(UserOrganizations) \
    .filter(
        DB.and_(
            SmsTags.tag_id == 9,  # EwiResponse
            UserOrganizations.site_id == site_id,
            SmsInboxUsers.ts_sms >= ts_start,
            SmsInboxUsers.ts_sms < ts_end,
        ))

    result = query.all()

    return result


def get_sms_cant_send_ground_meas(site_id, ts_start, ts_end):
    """
    """
    
    query = SmsInboxUserTags.query.options(DB.raiseload("*")) \
    .join(SmsTags).join(SmsInboxUsers) \
    .join(UserMobiles) \
    .join(Users) \
    .join(UserOrganizations) \
    .filter(
        DB.and_(
            SmsTags.tag_id == 11,  #CantSendGroundMeas
            UserOrganizations.site_id == site_id,
            SmsInboxUsers.ts_sms >= ts_start,
            SmsInboxUsers.ts_sms < ts_end,
        ))

    result = query.all()

    return result


def smart_search(
        string=None, tag=None,
        org_ids=None, site_ids=None, offset=0,
        limit=20, only_ewi_recipients=False,
        ts_start=None, ts_end=None, mobile_ids=None,
        only_active_mobile_numbers=False,
        mobile_number=None
):
    """
    """

    sms_inbox = SmsInboxUsers.query.options(DB.raiseload("*"))
    sms_outbox = SmsOutboxUserStatus.query.options(
        DB.joinedload("outbox_message", innerjoin=True).raiseload("*"),
        DB.raiseload("*")
    ).join(SmsOutboxUsers)

    if string:
        sms_inbox = sms_inbox.filter(
            SmsInboxUsers.sms_msg.ilike("%" + string + "%"))
        sms_outbox = sms_outbox.filter(
            SmsOutboxUsers.sms_msg.ilike("%" + string + "%"))

    try:
        tag_value = tag["value"]
        tag_source = tag["source"]
    except KeyError:
        tag_value = None

    if tag_value:
        tag_filter = SmsTags.tag_id == tag_value
        sms_inbox = sms_inbox.join(SmsInboxUserTags).join(
            SmsTags).filter(tag_filter)
        sms_outbox = sms_outbox.join(SmsOutboxUserTags).join(
            SmsTags).filter(tag_filter)

    if ts_start:
        sms_inbox = sms_inbox.filter(SmsInboxUsers.ts_sms >= ts_start)
        sms_outbox = sms_outbox.filter(SmsOutboxUsers.ts_written >= ts_start)

    if ts_end:
        sms_inbox = sms_inbox.filter(SmsInboxUsers.ts_sms <= ts_end)
        sms_outbox = sms_outbox.filter(SmsOutboxUsers.ts_written <= ts_end)

    if only_ewi_recipients or only_active_mobile_numbers or \
            org_ids or site_ids or mobile_ids or mobile_number:
        sms_inbox = sms_inbox.join(
            UserMobiles, SmsInboxUsers.mobile_id == UserMobiles.mobile_id)
        sms_outbox = sms_outbox.join(
            UserMobiles, SmsOutboxUserStatus.mobile_id == UserMobiles.mobile_id)

        if only_active_mobile_numbers:
            status_filter = UserMobiles.status == 1
            sms_inbox = sms_inbox.filter(status_filter)
            sms_outbox = sms_outbox.filter(status_filter)

        if mobile_ids:
            mobile_id_filter = UserMobiles.mobile_id.in_(mobile_ids)
            sms_inbox = sms_inbox.filter(mobile_id_filter)
            sms_outbox = sms_outbox.filter(mobile_id_filter)

        if mobile_number:
            mobile_number_filter = MobileNumbers.sim_num.ilike(
                "%" + mobile_number + "%")
            sms_inbox = sms_inbox.join(
                MobileNumbers).filter(mobile_number_filter)
            sms_outbox = sms_outbox.join(
                MobileNumbers).filter(mobile_number_filter)

        if only_ewi_recipients or org_ids or site_ids:
            sms_inbox = sms_inbox.join(Users)
            sms_outbox = sms_outbox.join(Users)

            if only_ewi_recipients:
                temp_filter = Users.ewi_recipient == 1
                sms_inbox = sms_inbox.filter(temp_filter)
                sms_outbox = sms_outbox.filter(temp_filter)

            if org_ids:
                org_filter = UserOrganizations.org_id.in_(org_ids)
                sms_inbox = sms_inbox.join(
                    UserOrganizations).filter(org_filter)
                sms_outbox = sms_outbox.join(
                    UserOrganizations).filter(org_filter)

            if site_ids:
                if not org_ids:
                    sms_inbox = sms_inbox.join(UserOrganizations)
                    sms_outbox = sms_outbox.join(UserOrganizations)

                site_filter = Sites.site_id.in_(site_ids)
                sms_inbox = sms_inbox.join(Sites).filter(site_filter)
                sms_outbox = sms_outbox.join(Sites).filter(site_filter)

    sms_inbox = sms_inbox.order_by(
        SmsInboxUsers.ts_sms.desc()).limit(limit).offset(offset)
    sms_outbox = sms_outbox.order_by(
        SmsOutboxUsers.ts_written.desc()).limit(limit).offset(offset)

    if tag_value:
        if tag_source == "smsinbox_users":
            search_results = sms_inbox.all()
        else:
            search_results = sms_outbox.all()
    else:
        search_results = sms_inbox.all() + sms_outbox.all()

    return search_results


def format_conversation_result(row):
    """
    """

    if hasattr(row, "read_status"):
        data = {
            "convo_id": row.inbox_id,
            "inbox_id": row.inbox_id,
            "outbox_id": None,
            "mobile_id": row.mobile_id,
            "sms_msg": row.sms_msg,
            # "sms_tags": row["sms_tags"],
            "ts": row.ts_sms.strftime('%Y-%m-%d %H:%M:%S'),
            "ts_received": row.ts_sms.strftime('%Y-%m-%d %H:%M:%S'),
            "ts_written": None,
            "ts_sent": None,
            "source": "inbox",
            "send_status": None,
            "is_per_convo": True
        }
    else:
        data = {
            "convo_id": row.outbox_message.outbox_id,
            "inbox_id": None,
            "outbox_id": row.outbox_message.outbox_id,
            "mobile_id": row.mobile_id,
            "sms_msg": row.outbox_message.sms_msg,
            # "sms_tags": row.outbox_message.sms_tags,
            "ts": row.outbox_message.ts_written.strftime('%Y-%m-%d %H:%M:%S'),
            "ts_received": None,
            "ts_written": row.outbox_message.ts_written.strftime('%Y-%m-%d %H:%M:%S'),
            "ts_sent": row.ts_sent.strftime('%Y-%m-%d %H:%M:%S'),
            "source": "outbox",
            "is_per_convo": True
        }

    return data


def get_messages_on_queue():
    """
    Gets all unprocessed messages on queue
    """

    # NOTE: In the future, resend unsent queued messages
    arr = SmsQueue.query.filter_by(ts_sent=None, ts_cancelled=None).filter(
        SmsQueue.ts_sending > datetime.now()).all()

    return_arr = []
    for row in arr:
        obj = prepare_queue_message(row)
        return_arr.append(obj)

    return return_arr


def prepare_queue_message(row=None, queue_id=None):
    """
    Prepares a message on queue
    """

    if not row:
        row = SmsQueue.query.filter_by(queue_id=queue_id).first()

    obj = SmsQueueSchema().dump(row)
    sms_data = json.loads(row.sms_data)

    obj["sms_msg"] = sms_data["sms_msg"]
    obj["recipient_list"] = sms_data["recipient_list"]

    list_preview = []
    for rec in sms_data["recipient_list"][:5]:
        name = get_user_mobile_details(rec["mobile_id"])
        list_preview.append(name)

    obj["recipient_list_preview"] = list_preview

    return obj
