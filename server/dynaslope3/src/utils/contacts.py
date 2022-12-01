"""
Contacts Functions Utility File
"""

from datetime import datetime
from sqlalchemy.orm import joinedload, contains_eager
from connection import DB
from src.models.users import (
    Users, UserEmails, UserLandlines,
    UsersRelationship, UsersRelationshipSchema,
    UserEwiRestrictions
)
from src.models.mobile_numbers import (
    UserMobiles, UserMobilesSchema,
    MobileNumbers, BlockedMobileNumbers,
    BlockedMobileNumbersSchema
)
from src.models.organizations import (
    Organizations, UserOrganizations
)
from src.models.gsm import SimPrefixes, SimPrefixesSchema
from src.models.sites import Sites
from src.utils.extra import var_checker, retrieve_data_from_memcache
from src.models.bulletin_recipients import BulletinRecipients
from src.utils.monitoring import get_monitoring_triggers


def get_org_ids(scopes=None, org_names=None):
    """
        Returns org ids as need by other APIs

        scopes (list):  list of scope e.g. [0, 1] 0 -> community, 1 -> barangay
        org_names (list):  list of org_names e.g. ["lewc", "lgu"]
    """
    orgs = Organizations
    base = orgs.query.options(DB.raiseload("*")).order_by(DB.asc(orgs.scope))

    if scopes:
        base = base.filter(orgs.scope.in_(scopes))

    if org_names:
        base = base.filter(orgs.name.in_(org_names))

    org_ids = base.all()

    org_id_list = []
    for item in org_ids:
        org_id_list.append(item.org_id)

    return org_id_list


def get_mobile_numbers(return_schema=False, mobile_ids=None, site_ids=None,
                       org_ids=None, only_ewi_recipients=False, only_active_mobile_numbers=True,
                       mobile_number=None, only_active_users=False):
    """
    """

    base_query = UserMobiles.query.join(Users) \
        .options(
            joinedload("user").subqueryload("organizations")
            .joinedload("site").raiseload("*")) \
        .order_by(Users.last_name, UserMobiles.priority)

    if mobile_ids:
        base_query = base_query.filter(UserMobiles.mobile_id.in_(mobile_ids))

    if org_ids:
        base_query = base_query.join(UserOrganizations) \
            .filter(UserOrganizations.org_id.in_(org_ids))

    if site_ids:
        if org_ids:
            base_query = base_query.join(Sites)
        else:
            base_query = base_query.join(UserOrganizations) \
                .join(Sites)

        base_query = base_query.filter(Sites.site_id.in_(site_ids))

    if only_ewi_recipients:
        base_query = base_query.filter(Users.ewi_recipient == 1)

    if only_active_users:
        base_query = base_query.filter(Users.status == 1)

    if mobile_number:
        base_query = base_query.join(MobileNumbers).filter(
            MobileNumbers.sim_num.ilike("%" + mobile_number + "%"))

    # default is to get only active mobile numbers
    if only_active_mobile_numbers:
        base_query = base_query.filter(UserMobiles.status == 1)

    mobile_numbers = base_query.all()

    if return_schema:
        mobile_numbers = UserMobilesSchema(many=True).dump(mobile_numbers)

    return mobile_numbers


def get_all_contacts(return_schema=False):
    """
    Function that get all contacts
    """
    query_start = datetime.now()

    mobile_numbers = []

    if return_schema:
        mobile_numbers = get_recipients(
            return_schema_format=return_schema,
            only_ewi_recipients=False,
            include_inactive_numbers=True,
            include_ewi_restrictions=True,
            include_inactive_users=True)

    query_end = datetime.now()
    print("GET CONTACTS RUNTIME: ", query_end - query_start)

    return mobile_numbers


def get_recipients_option(site_ids=None,
                          only_ewi_recipients=False,
                          org_ids=None,
                          only_active_users=False):

    query_start = datetime.now()

    mobile_numbers = get_mobile_numbers(
        site_ids=site_ids, org_ids=org_ids, only_ewi_recipients=only_ewi_recipients,
        only_active_users=only_active_users)
    result = UserMobilesSchema(many=True) \
        .dump(mobile_numbers)
    # NOTE EXCLUDE: "mobile_number.blocked_mobile" exclude=["landline_numbers", "emails"]

    recipients_options = []
    for row in result:
        user = row["user"]
        orgs = user["organizations"]

        label = f'{user["last_name"]}, {user["first_name"]}'
        final_org = ""
        if orgs:
            temp = orgs[0]
            org = temp["organization"]
            scope = org["scope"]
            org_name = org["name"].upper()
            site = temp["site"]

            if scope == 0:
                final_org = f'{site["site_code"].upper()} {org_name}'
            elif scope == 1:
                if org_name == "LGU":
                    org_name = f"B{org_name}"
                final_org = f'{site["site_code"].upper()} {org_name}'
            elif scope == 2:
                if org_name == "LGU":
                    org_name = f"M{org_name}"
                final_org = f'{site["municipality"]} {org_name}'
            elif scope == 3:
                if org_name == "LGU":
                    org_name = f"P{org_name}"
                final_org = f'{site["province"]} {org_name}'
            elif scope == 4:
                final_org = f'Region {site["region"]} {org_name}'
            elif scope == 4:
                final_org = f"National {org_name}"

        temp = {
            **row["mobile_number"],
            "label": label,
            "org": final_org,
        }

        recipients_options.append(temp)

    query_end = datetime.now()
    print("GET RECIPIENTS OPTIONS RUNTIME: ", query_end - query_start)

    return recipients_options


def get_contacts_per_site(site_ids=None,
                          site_codes=None, only_ewi_recipients=True,
                          include_ewi_restrictions=False, org_ids=None,
                          return_schema_format=True,
                          include_inactive_numbers=False,
                          include_inactive_users=False):
    """
    Function that get contacts per site
    """

    user_per_site_result = get_recipients(
        site_ids=site_ids, site_codes=site_codes,
        only_ewi_recipients=only_ewi_recipients,
        include_ewi_restrictions=include_ewi_restrictions,
        org_ids=org_ids, return_schema_format=return_schema_format,
        include_inactive_numbers=include_inactive_numbers,
        include_inactive_users=include_inactive_users, joined=True)

    return user_per_site_result


def save_user_information(data):
    """
    Function that save user information
    """
    user_id = data["user_id"]
    first_name = data["first_name"]
    last_name = data["last_name"]
    middle_name = data["middle_name"]
    nickname = data["nickname"]
    emails = data["emails"]
    ewi_recipient = data["ewi_recipient"]
    ground_reminder_recipient = data["ground_reminder_recipient"]
    status = data["status"]
    salutation = None
    birthday = None
    sex = None

    if "birthday" in data:
        birthday = data["birthday"]
    if "salutation" in data:
        salutation = data["salutation"]
    if "sex" in data:
        sex = data["sex"]

    if user_id == 0:
        insert_user = Users(
            first_name=first_name, last_name=last_name,
            middle_name=middle_name, nickname=nickname,
            ewi_recipient=ewi_recipient, birthday=birthday,
            sex=sex, status=status, salutation=salutation,
            ground_reminder_recipient=ground_reminder_recipient
        )

        DB.session.add(insert_user)
        DB.session.flush()
        user_id = insert_user.user_id

    else:
        update = Users.query.options(DB.raiseload("*")).get(user_id)
        update.first_name = first_name
        update.last_name = last_name
        update.middle_name = middle_name
        update.nickname = nickname
        update.ewi_recipient = ewi_recipient
        update.ground_reminder_recipient = ground_reminder_recipient
        update.status = status
        update.birthday = birthday
        update.sex = sex
        update.salutation = salutation

    try:
        emails_to_delete = data["delete_emails"]
    except KeyError:
        emails_to_delete = None

    save_user_email(emails, user_id, emails_to_delete)

    try:
        ewi_restriction = data["restriction"]
        save_user_ewi_restriction(ewi_restriction, user_id)
    except KeyError:
        pass

    return user_id


def save_user_email(emails, user_id, delete_list=None):
    """
    Function that save user email
    """

    if emails:
        for row in emails:
            row_type = type(row)
            if row_type == str:
                insert_email = UserEmails(user_id=user_id, email=row)
                DB.session.add(insert_email)
            else:
                if row["email_id"] == 0:
                    insert_email = UserEmails(
                        user_id=user_id, email=row["email"])
                    DB.session.add(insert_email)
                else:
                    update_email = UserEmails.query.get(row["email_id"])
                    update_email.email = row["email"]

    if delete_list is not None:
        delete_len = len(delete_list)
        if delete_len > 0:
            for row in delete_list:
                UserEmails.query.filter_by(
                    user_id=user_id, email=row["email"]).delete()

    return True


def save_user_contact_numbers(data, user_id):
    """
    Function that save user contact numbers
    """

    mobile_numbers = data["mobile_numbers"]
    try:
        landline_numbers = data["landline_numbers"]
    except KeyError:
        landline_numbers = []

    mobile_numbers_len = len(mobile_numbers)
    landline_number_len = len(landline_numbers)

    mobile_ids = []
    if mobile_numbers_len > 0:
        for row in mobile_numbers:
            mobile_id = row["mobile_number"]["mobile_id"]
            sim_num = row["mobile_number"]["sim_num"]
            gsm_id = row["mobile_number"]["gsm_id"]
            status = row["status"]
            to_insert_user_mobiles = False
            if mobile_id == 0:
                check_sim_num = MobileNumbers.query.filter_by(
                    sim_num=sim_num).first()

                if check_sim_num is None:
                    # gsm_id = get_gsm_id_by_prefix(sim_num)
                    insert_mobile_number = MobileNumbers(
                        sim_num=sim_num, gsm_id=gsm_id)
                    DB.session.add(insert_mobile_number)
                    DB.session.flush()
                    last_inserted_mobile_id = insert_mobile_number.mobile_id
                else:
                    last_inserted_mobile_id = check_sim_num.mobile_id

                to_insert_user_mobiles = True
            else:
                update_mobile = MobileNumbers.query.get(mobile_id)
                update_mobile.sim_num = sim_num
                # update_mobile.gsm_id = get_gsm_id_by_prefix(sim_num)
                update_mobile.gsm_id = gsm_id
                last_inserted_mobile_id = mobile_id

                update_user_mobile = UserMobiles.query.filter_by(
                    user_id=user_id, mobile_id=mobile_id).first()

                if update_user_mobile:
                    update_user_mobile.status = status
                else:
                    to_insert_user_mobiles = True

            if to_insert_user_mobiles:
                insert_user_mobile = UserMobiles(
                    user_id=user_id,
                    mobile_id=last_inserted_mobile_id,
                    status=status
                )

                DB.session.add(insert_user_mobile)

            mobile_ids.append(last_inserted_mobile_id)

    if landline_number_len > 0:
        for row in landline_numbers:
            landline_id = row["landline_id"]
            landline_num = row["landline_num"]
            area_code = row["area_code"]
            pte_code = row["pte_code"]

            if landline_id == 0:
                insert_landline_number = UserLandlines(
                    user_id=user_id, landline_num=landline_num,
                    area_code=area_code, pte_code=pte_code)
                DB.session.add(insert_landline_number)
            else:
                update_landline = UserLandlines.query.get(landline_id)
                update_landline.landline_num = landline_num
                update_landline.area_code = area_code
                update_landline.pte_code = pte_code

    DB.session.flush()
    return mobile_ids


def save_user_affiliation(data, user_id):
    """
    Function that save user affiliation
    NOTE: Improve this because it destroys and creates
    new user_org rows every save
    """

    if data:
        # print(data)
        location = data["location"]
        site = data["site"]
        scope = data["scope"]
        office = data["office"]
        multi_sites = data["multi_sites"]

        org = Organizations.query.options(DB.raiseload("*")).filter(
            Organizations.scope == scope, Organizations.name == office).first()
        org_id = org.org_id

        site_ids = []
        org_name = office
        modifier = ""

        uo_query = UserOrganizations.query.options(DB.raiseload("*")).filter(
            UserOrganizations.user_id == user_id)

        uo_row = uo_query.first()

        primary_contact = None
        if uo_row:
            primary_contact = uo_row.primary_contact

        uo_query.delete()

        if scope in (0, 1):
            site_ids.append(site["value"])
            modifier = "b" if org_name == "lgu" else ""
        elif scope == 2:
            modifier = "m"
            filter_var = Sites.municipality == location
        elif scope == 3:
            modifier = "p"
            filter_var = Sites.province == location
        elif scope == 4:
            filter_var = Sites.region == location

        if office == "lgu":
            org_name = str(modifier + office)

        if scope not in (0, 1, 5):
            result = Sites.query.options(
                DB.raiseload("*")).filter(filter_var).all()
            for site in result:
                site_ids.append(site.site_id)

        if scope == 5:
            site_ids = map(lambda x: x["value"], multi_sites)

        for site_id in site_ids:
            insert_org = UserOrganizations(
                user_id=user_id,
                site_id=site_id,
                org_name=org_name,
                org_id=org_id,
                primary_contact=primary_contact
            )

            DB.session.add(insert_org)

    return True


def save_user_ewi_restriction(restriction, user_id):
    """
    Function that save user ewi restriction
    """

    UserEwiRestrictions.query.filter(
        UserEwiRestrictions.user_id == user_id).delete()

    if restriction != 0:
        save_restriction_query = UserEwiRestrictions(
            user_id=user_id, alert_level=restriction)
        DB.session.add(save_restriction_query)

    return True


def attach_mobile_number_to_existing_user(mobile_id, user_id, status):
    """
    """

    row = UserMobiles(
        user_id=user_id,
        mobile_id=mobile_id,
        status=status
    )

    DB.session.add(row)
    DB.session.commit()


def get_gsm_id_by_prefix(mobile_number):
    """
    Function that get prefix gsm id
    """
    prefix = mobile_number[2:5]

    sim_prefix_query = SimPrefixes.query.filter(
        SimPrefixes.prefix == prefix).first()

    result = SimPrefixesSchema().dump(sim_prefix_query)
    gsm_id = 0

    result_length = len(result)
    if result_length == 0:
        gsm_id = 0
    else:
        gsm_id = result["gsm_id"]

    return gsm_id


def get_ground_data_reminder_recipients(site_id):
    """
    """

    recipients = get_recipients(
        site_ids=[site_id], only_ewi_recipients=False,
        only_ground_reminder_recipients=True,
        joined=True)

    return recipients


def ground_data_reminder_migration():
    """
    """

    query = UsersRelationship.query.options(
        DB.subqueryload("organizations").joinedload(
            "organization").raiseload("*"),
        DB.raiseload("*")).all()

    for x in query:
        if x.organizations:
            if x.organizations[0].org_id == 1:
                x.ground_reminder_recipient = x.ewi_recipient
            else:
                x.ground_reminder_recipient = 0
        else:
            x.ground_reminder_recipient = 0

    DB.session.commit()

    return "Done"


def get_blocked_numbers(return_schema=True):
    """
    Function that gets blocked numbers
    """

    query = BlockedMobileNumbers.query.all()

    if return_schema:
        result = BlockedMobileNumbersSchema(many=True).dump(query)
    else:
        result = query

    return result


def save_blocked_number(data):
    """
    Function that save block number
    """

    now = datetime.now()
    current_datetime = now.strftime("%Y-%m-%d %H:%M:%S")
    mobile_id = data["mobile_id"]
    reporter_id = data["reporter_id"]
    reason = data["reason"]

    insert_query = BlockedMobileNumbers(mobile_id=mobile_id, reason=reason,
                                        reporter_id=reporter_id, ts=current_datetime)
    DB.session.add(insert_query)

    print("")
    print(f"Blocked mobile ID {mobile_id} successfully")
    print("")

    return True


def get_all_sim_prefix():
    """
    Function that gets sim prefixes
    """

    query = SimPrefixes.query.all()
    result = SimPrefixesSchema(many=True).dump(query)

    return result


def get_recipients(site_ids=None,
                   site_codes=None, only_ewi_recipients=True,
                   only_ground_reminder_recipients=False,
                   include_ewi_restrictions=False, org_ids=None,
                   return_schema_format=True,
                   include_inactive_numbers=False,
                   order_by_scope=False,
                   include_inactive_users=False,
                   joined=False, for_bulletin=False):
    """
    Refactored function of getting recipients
    """

    query = UsersRelationship.query.options(
        DB.subqueryload("mobile_numbers").joinedload(
            "mobile_number").raiseload("*"),
        DB.subqueryload("organizations").joinedload(
            "organization").raiseload("*"),
        DB.subqueryload("organizations").joinedload("site")
        .raiseload("*"),
        DB.subqueryload("emails"),
        DB.raiseload("*"))

    if joined:
        query = query.join(UserOrganizations).join(
            Sites).join(Organizations).join(UserMobiles)

    # "mobile_numbers.mobile_number.blocked_mobile"]
    schema_exclusions = ["teams", "ewi_restriction"]

    if site_ids:
        query = query.filter(Sites.site_id.in_(site_ids))

    if site_codes:
        query = query.filter(Sites.site_code.in_(site_codes))

    if org_ids:
        query = query.filter(
            UserOrganizations.org_id.in_(org_ids)
        )

    if only_ewi_recipients:
        query = query.filter(UsersRelationship.ewi_recipient == 1)

    if only_ground_reminder_recipients:
        query = query.filter(UsersRelationship.ground_reminder_recipient == 1)

    if include_ewi_restrictions:
        query = query.options(DB.joinedload("ewi_restriction"))
        schema_exclusions.remove("ewi_restriction")

    if not include_inactive_numbers:
        query = query.filter(UserMobiles.status == 1).options(
            contains_eager(UsersRelationship.mobile_numbers))

    if not include_inactive_users:
        query = query.filter(UsersRelationship.status == 1)

    if order_by_scope:
        query = query.order_by(Organizations.scope)
    else:
        query = query.order_by(UsersRelationship.last_name)

    if for_bulletin:
        query = query.filter(Organizations.name == "phivolcs")

    user_per_site_result = query.all()

    if return_schema_format:
        user_per_site_result = UsersRelationshipSchema(
            many=True, exclude=schema_exclusions) \
            .dump(user_per_site_result)

    return user_per_site_result


def save_primary(data):
    """
    Function that save primary contact
    """

    for contact in data:
        is_primary_contact = contact["primary_contact"] == 1 and True or False
        organizations = contact["contact_person"]["organizations"]

        for organization in organizations:
            user_org_id = organization["user_org_id"]
            org_id = organization["organization"]["org_id"]
            site_id = organization["site"]["site_id"]
            update_query = UserOrganizations.query.get(user_org_id)

            if is_primary_contact:
                update_query.primary_contact = 1

                for other_users in UserOrganizations.query.filter_by(
                        site_id=site_id, org_id=org_id):
                    if other_users.user_org_id != user_org_id:
                        other_users.primary_contact = 0
            else:
                update_query.primary_contact = 0

    return True


def get_bulletin_recipients(
        site_codes=None,
        is_live_mode=False,
        is_onset=False,
        p_a_level=0,
        event_id=0):
    """
    """

    emails = []
    bulletin_recipients = get_recipients(site_codes=site_codes,
                                         joined=True,
                                         for_bulletin=True,
                                         order_by_scope=True)

    if bulletin_recipients:
        for row in bulletin_recipients:
            user_emails = row["emails"]

            if user_emails:
                for email in user_emails:
                    emails.append(email["email"])

    triggers = get_monitoring_triggers(
        event_id=event_id, load_options="end_of_shift")
    has_earthquake_trigger = False

    group_filter = []
    if triggers:
        eq_th = retrieve_data_from_memcache("trigger_hierarchies", filters_dict={
            "trigger_source": "earthquake"}, retrieve_one=True)
        eq_internal_id = None
        for row in eq_th["trigger_symbols"]:
            if row["internal_alert_symbol"]:
                eq_internal_id = row["internal_alert_symbol"]["internal_sym_id"]

        for trigger in triggers:
            internal_sym_id = trigger.internal_sym_id

            if internal_sym_id == eq_internal_id:
                if not has_earthquake_trigger:
                    has_earthquake_trigger = True
                    group_filter.append("earthquake")

    recipient_query = BulletinRecipients.query
    if is_live_mode:
        group_filter.append("heads")
        if is_onset and p_a_level > 0:
            group_filter.append("dyna")
    else:
        group_filter.append("devs")

    if group_filter:
        recipient_query = recipient_query.filter(
            BulletinRecipients.recipient_group.in_(group_filter)).all()
        for recipient in recipient_query:
            emails.append(recipient.email_address)

    return emails
