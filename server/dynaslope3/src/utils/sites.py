"""
Utility file for Sites Table
Contains functions for getting and accesing Sites table only
"""

from connection import DB
from src.models.sites import Sites, SitesSchema, Seasons, SeasonsSchema


def get_sites_data(
        site_code=None, site_id=None,
        include_inactive=False, raise_load=False):
    """
    Description:
        Function that gets basic site data by site code or site id;
        If both, site_code and site_id is present, site_code will be prioritized
    Params:
        site_code (str or list of str): site code or list of site codes
        site_id (int or list of int):   site id or list of site ids
        include_inactive (bool):        include inactive sites
        raise_load (bool):              remove all relationship to speed up queries
    Returns:
        Site object
    """

    final_query = Sites.query

    if raise_load:
        final_query = final_query.options(DB.raiseload("*"))

    if site_code is None and site_id is None:
        if not include_inactive:
            final_query = final_query.filter_by(active=True)
        final_query = final_query.order_by(Sites.site_code)
        site = final_query.all()
    elif site_code:
        if isinstance(site_code, (list,)):
            site = final_query.filter(Sites.site_code.in_(site_code)).all()
        else:
            site = final_query.filter_by(site_code=site_code).first()
    else:
        if isinstance(site_id, (list,)):
            site = final_query.filter(Sites.site_id.in_(site_id)).all()
        else:
            site = final_query.filter_by(site_id=site_id).first()

    return site


def get_site_events(site_code):
    """
    Function that returns site data and all monitoring events
    """
    site = Sites.query.filter_by(site_code=site_code).first()
    events = site.events.all()

    return site, events


def get_all_geographical_selection_per_category(category, include_inactive):
    """
    """

    attr = getattr(Sites, category)

    subquery = DB.session.query(DB.func.min(
        Sites.site_id).label("min_id"), attr)

    if not include_inactive:
        subquery = subquery.filter_by(active=1)

    subquery = subquery.group_by(attr).subquery()

    selection = DB.session.query(Sites).join(
        subquery, Sites.site_id == subquery.c.min_id).order_by(attr).all()

    return selection


def build_site_address(site_info, limit_to_barangay=False):
    """
    Params:
        site_info (class):          Site class
        limit_to_barangay (bool):   default False, limit address
                                    up to barangay only
    Return:
        Address of a site (string)
    """

    address = ""
    purok = site_info.purok
    sitio = site_info.sitio

    if purok:
        address += f"Purok {purok}, "

    if sitio:
        address += f"Sitio {sitio}, "

    address += f"Brgy. {site_info.barangay}"

    if not limit_to_barangay:
        address += f", {site_info.municipality}, {site_info.province}"

    return address


def get_site_season(site_code=None, site_id=None, return_schema_format=True):
    """
    """

    query = Sites.query.options(
        DB.joinedload("season_months", innerjoin=True)
        .subqueryload("routine_schedules"),
        DB.raiseload("*")
    )

    is_many = True
    if site_code or site_id:
        is_many = False

        if site_code:
            query = query.filter_by(site_code=site_code)

        if site_id:
            query = query.filter_by(site_id=site_id)

        result = query.first()
    else:
        result = query.all()

    if return_schema_format:
        # NOTE INCLUDE include=["season_months"]
        schema = SitesSchema(many=is_many)
        temp = schema.dump(result)
        if not is_many:
            temp["season_months"] = SeasonsSchema(
                exclude=["sites"]).dump(result.season_months)
        result = temp

    return result


def get_seasons():
    """
    """
    query = Seasons.query.all()
    result = SeasonsSchema(
        many=True,
        exclude=[
            "routine_schedules", "sites"
        ]
    ).dump(query)

    return result


def save_site_info(data):
    """
    """

    update = Sites.query.get(data["site_id"])
    update.purok = data["purok"]
    update.sitio = data["sitio"]
    update.barangay = data["barangay"]
    update.municipality = data["municipality"]
    update.province = data["province"]
    update.region = data["region"]
    update.psgc = data["psgc"]
    update.active = data["active"]
    update.households = data["households"]
    update.season = data["season"]

    return True
