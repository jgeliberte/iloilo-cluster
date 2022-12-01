
"""
"""

from instance.config import SCHEMA_DICT
from marshmallow import fields
from connection import DB, MARSHMALLOW


class BulletinResponses(DB.Model):
    """
    Class representation of bulletin_responses table
    """

    __tablename__ = "bulletin_responses"
    __bind_key__ = "ewi_db"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    pub_sym_id = DB.Column(DB.Integer, DB.ForeignKey(
        f"{SCHEMA_DICT['ewi_db']}.public_alert_symbols.pub_sym_id"), primary_key=True)
    recommended = DB.Column(DB.String(200))
    lewc_lgu = DB.Column(DB.String(200))
    community = DB.Column(DB.String(200))

    public_alert_symbol = DB.relationship(
        "PublicAlertSymbols", backref=DB.backref("bulletin_response", lazy="dynamic"),
        lazy="joined", innerjoin=True)

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Public Symbol ID: {self.pub_sym_id}"
                f" Recommended Response: {self.recommended} LEWC/LGU Response: {self.lewc_lgu}"
                f" Community Response: {self.community}")


class BulletinTriggers(DB.Model):
    """
    Class representation of bulletin_triggers table
    """

    __tablename__ = "bulletin_triggers"
    __bind_key__ = "ewi_db"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    internal_sym_id = DB.Column(DB.Integer, DB.ForeignKey(
        f"{SCHEMA_DICT['ewi_db']}.internal_alert_symbols.internal_sym_id"), primary_key=True)
    description = DB.Column(DB.String(100))
    cause = DB.Column(DB.String(50))
    template = DB.Column(DB.String(100))
    sms = DB.Column(DB.String(200))
    lowering_fyi = DB.Column(DB.String(300))

    internal_sym = DB.relationship(
        "InternalAlertSymbols", backref=DB.backref("bulletin_trigger", lazy="dynamic"),
        lazy="joined", innerjoin=True)

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> internal_sym_id: {self.internal_sym_id}"
                f" description: {self.description} cause: {self.cause}"
                f" template: {self.template} sms: {self.sms}")


class BulletinResponsesSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of BulletinResponses class
    """

    pub_sym_id = fields.Integer()
    public_alert_symbol = MARSHMALLOW.Nested("PublicAlertSymbolsSchema")

    class Meta:
        """Saves table class structure as schema model"""
        model = BulletinResponses


class BulletinTriggersSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of BulletinTriggers class
    """

    internal_sym_id = fields.Integer()
    internal_sym = MARSHMALLOW.Nested("InternalAlertSymbolsSchema")

    class Meta:
        """Saves table class structure as schema model"""
        model = BulletinTriggers

class OnDemandIdentifier:
    def __init__(self, release_id):
        self.release_id = release_id

    def identifier(self):
        ret_val = []
        try:
            res = DB.engine.execute('SELECT ewi_db.monitoring_on_demand.eq_id FROM ewi_db.monitoring_releases ' \
                            'INNER JOIN ewi_db.monitoring_triggers USING (release_id) ' \
                            'INNER JOIN ewi_db.monitoring_triggers_misc USING (trigger_id) ' \
                            'INNER JOIN ewi_db.monitoring_on_demand USING (od_id) WHERE ' \
                            f'release_id = {self.release_id};')
            for row in res:
                ret_val.append({
                    'od_eq_id': row
                })
            ret_val = ret_val[0]
        except Exception as e:
            print(e)
            ret_val = -1
        finally:
            return ret_val