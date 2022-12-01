"""
Sets memcache for Dynaslope 3. Mainly symbol maps.
"""

from src.models.monitoring import (
    PublicAlertSymbols as pas, OperationalTriggerSymbols as ots,
    InternalAlertSymbols as ias, TriggerHierarchies as th,
    PublicAlertSymbolsSchema as pasS, OperationalTriggerSymbolsSchema as otsS,
    InternalAlertSymbolsSchema as iasS, TriggerHierarchiesSchema as thS,
    CbewslEwiTemplate as cewi, CbewslEwiTemplateSchema as cewiS)
from src.models.ewi import (
    BulletinResponses as br, BulletinResponsesSchema as brS,
    BulletinTriggers as bt, BulletinTriggersSchema as btS)
from src.models.dynamic_variables import (
    DynamicVariables as dv, DynamicVariablesSchema as dvS)
from src.models.analysis import (
    SiteMarkers as sm, SiteMarkersSchema as smS)
from src.models.inbox_outbox import (
    SmsTags as st, SmsTagsSchema as stS,
    SmsPriority as sp, SmsPrioritySchema as spS
)
from src.models.organizations import (
    Organizations as org, OrganizationsSchema as orgS
)
from src.utils.extra import set_data_to_memcache


def main():
    """
    """

    table_list = {
        "public_alert_symbols": (pas, pasS(many=True)),
        "operational_trigger_symbols": (ots, otsS(many=True)),
        "internal_alert_symbols": (ias, iasS(many=True)),
        "trigger_hierarchies": (th, thS(many=True)),
        "dynamic_variables": (dv, dvS(many=True)),
        "bulletin_responses": (br, brS(many=True)),
        "bulletin_triggers": (bt, btS(many=True)),
        "site_markers": (sm, smS(many=True)),
        "sms_tags": (st, stS(many=True)),
        "sms_priority": (sp, spS(many=True)),
        "organizations": (org, orgS(many=True)),
        "cbewsl_ewi_template": (cewi, cewiS(many=True))
    }

    for key in table_list:
        table = table_list[key][0].query.all()
        table_data = table_list[key][1].dump(table)

        set_data_to_memcache(
            name=key.upper(), data=table_data, raise_if_empty=True)
