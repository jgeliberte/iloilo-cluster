"""
File containing class representation of
tables of smsinbox_users, smsoutbox_users and smsoutbox_user_status
"""

from datetime import datetime
from marshmallow import fields, EXCLUDE
from instance.config import SCHEMA_DICT
from connection import DB, MARSHMALLOW
from src.models.mobile_numbers import UserMobiles, UserMobilesSchema

class SmsInboxUsers(DB.Model):
    """
    Class representation of smsinbox_users table
    """

    __tablename__ = "smsinbox_users"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    inbox_id = DB.Column(DB.Integer, primary_key=True)
    ts_sms = DB.Column(DB.DateTime, default=datetime.now)
    ts_stored = DB.Column(DB.DateTime, default=datetime.now)
    mobile_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['comms_db_3']}.user_mobiles.mobile_id"))
    sms_msg = DB.Column(DB.String(1000))
    read_status = DB.Column(DB.Integer, default=0)

    mobile_details = DB.relationship(UserMobiles,
                                     backref=DB.backref(
                                         "inbox_messages", lazy="dynamic"),
                                     lazy="select")
    sms_tags = DB.relationship(
        "SmsInboxUserTags", backref="inbox_message", lazy="subquery")

    def __repr__(self):
        return f"Type <{self.__class__.__name__}>"


class SmsTags(DB.Model):
    """
    Class representation of smsinbox_users table
    """

    __tablename__ = "sms_tags"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    tag_id = DB.Column(DB.Integer, primary_key=True)
    tag = DB.Column(DB.String(30), nullable=False)
    source = DB.Column(DB.String(30), nullable=False)
    description = DB.Column(DB.String(300))

    def __repr__(self):
        return f"Type <{self.__class__.__name__}>"


class SmsInboxUserTags(DB.Model):
    """
    Class representation of smsinbox_users table
    """

    __tablename__ = "smsinbox_user_tags"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    siu_tag_id = DB.Column(DB.Integer, primary_key=True)
    inbox_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['comms_db_3']}.smsinbox_users.inbox_id"))
    tag_id = DB.Column(DB.Integer, DB.ForeignKey(
        f"{SCHEMA_DICT['comms_db_3']}.sms_tags.tag_id"))
    user_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['commons_db']}.users.user_id"))
    ts = DB.Column(DB.DateTime, default=datetime.now)

    tag = DB.relationship("SmsTags",
                          backref=DB.backref(
                              "smsinbox_user_tags", lazy="subquery"),
                          lazy="select")

    def __repr__(self):
        return f"Type <{self.__class__.__name__}>"


class SmsOutboxUsers(DB.Model):
    """
    Class representation of smsoutbox_users table
    """

    __tablename__ = "smsoutbox_users"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    outbox_id = DB.Column(DB.Integer, primary_key=True)
    ts_written = DB.Column(DB.DateTime, default=datetime.now)
    source = DB.Column(DB.String(45))
    sms_msg = DB.Column(DB.String(1000))

    send_status = DB.relationship("SmsOutboxUserStatus",
                                  backref=DB.backref(
                                      "outbox_message", lazy="select"),
                                  lazy="subquery")
    sms_tags = DB.relationship(
        "SmsOutboxUserTags", backref="outbox_message", lazy="subquery")

    def __repr__(self):
        return f"Type <{self.sms_msg}>"


class SmsOutboxUserStatus(DB.Model):
    """
    Class representation of smsoutbox_user_status table
    """

    __tablename__ = "smsoutbox_user_status"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    stat_id = DB.Column(DB.Integer, primary_key=True)
    outbox_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['comms_db_3']}.smsoutbox_users.outbox_id"))
    mobile_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['comms_db_3']}.user_mobiles.mobile_id"))
    ts_sent = DB.Column(DB.DateTime, default=None)
    send_status = DB.Column(DB.Integer, nullable=False, default=0)
    gsm_id = DB.Column(DB.Integer, nullable=False)
    # NOTE: check SmsPriority for default
    priority = DB.Column(DB.Integer, nullable=False, default=7)

    mobile_details = DB.relationship(UserMobiles,
                                     backref=DB.backref(
                                         "outbox_messages", lazy="dynamic"),
                                     lazy="select")

    def __repr__(self):
        return f"Type <{self.__class__.__name__}>"


class SmsOutboxUserTags(DB.Model):
    """
    Class representation of smsinbox_users table
    """

    __tablename__ = "smsoutbox_user_tags"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    sou_tag_id = DB.Column(DB.Integer, primary_key=True)
    outbox_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['comms_db_3']}.smsoutbox_users.outbox_id"))
    tag_id = DB.Column(DB.Integer, DB.ForeignKey(
        f"{SCHEMA_DICT['comms_db_3']}.sms_tags.tag_id"))
    user_id = DB.Column(
        DB.Integer, DB.ForeignKey(f"{SCHEMA_DICT['commons_db']}.users.user_id"))
    ts = DB.Column(DB.DateTime, default=datetime.now)

    tag = DB.relationship("SmsTags",
                          backref=DB.backref(
                              "smsoutbox_user_tags", lazy="subquery"),
                          lazy="select")

    def __repr__(self):
        return f"Type <{self.__class__.__name__}>"


class SmsUserUpdates(DB.Model):
    """
    Class representation of smsinbox_users table
    """

    __tablename__ = "sms_user_updates"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    update_id = DB.Column(DB.Integer, primary_key=True)
    mobile_id = DB.Column(DB.Integer)
    update_source = DB.Column(DB.String(20))
    pk_id = DB.Column(DB.Integer)
    processed = DB.Column(DB.Boolean, default=False)

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Update ID: {self.update_id}"
                f" Mobile ID: {self.mobile_id} Source: {self.update_source}"
                f" Primary Key ID: {self.pk_id}")


class ViewLatestMessages(DB.Model):
    """
    """

    __tablename__ = "view_latest_messages"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    convo_id = DB.Column(DB.Integer, primary_key=True)
    max_time = DB.Column(DB.DateTime)
    mobile_id = DB.Column(DB.Integer)
    sms_msg = DB.Column(DB.String(3000))
    gsm_id = DB.Column(DB.Integer, default=None)
    source = DB.Column(DB.String(10))

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Convo ID: {self.convo_id}"
                f" Max Time: {self.max_time} Mobile ID: {self.mobile_id}"
                f" SMS: {self.sms_msg} GSM ID: {self.gsm_id} Source: {self.source}")


class ViewLatestMessagesMobileID(DB.Model):
    """
    """

    __tablename__ = "view_latest_messages_mobile_id"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    mobile_id = DB.Column(DB.Integer, primary_key=True)
    max_ts = DB.Column(DB.DateTime)

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Mobile ID: {self.mobile_id}"
                f" Max TS: {self.max_ts}")


class ViewLatestUnsentMsgsPerMobileID(DB.Model):
    """
    """

    __tablename__ = "view_latest_unsent_msgs_per_mobile_id"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    mobile_id = DB.Column(DB.Integer, primary_key=True)
    convo_id = DB.Column(DB.Integer)
    inbox_id = DB.Column(DB.Integer)
    outbox_id = DB.Column(DB.Integer)
    send_status = DB.Column(DB.Integer)
    gsm_id = DB.Column(DB.Integer)
    ts = DB.Column(DB.DateTime)
    ts_sent = DB.Column(DB.DateTime)
    ts_written = DB.Column(DB.DateTime)
    sms_msg = DB.Column(DB.String(3000))
    source = DB.Column(DB.String(20))
    msg_source = DB.Column(DB.String(10))

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Mobile ID: {self.mobile_id}"
                f" Max TS: {self.max_ts}")


class SmsPriority(DB.Model):
    """
    """

    __tablename__ = "sms_priority"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    priority_id = DB.Column(DB.Integer, primary_key=True)
    name = DB.Column(DB.String(100), nullable=False)
    keyword = DB.Column(DB.String(30), nullable=False)
    list_as_option = DB.Column(DB.Boolean, default=True, nullable=False)
    remarks = DB.Column(DB.String(500))

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Priority ID: {self.priority_id}"
                f" Name: {self.name}")


class SmsQueue(DB.Model):
    """
    """

    __tablename__ = "sms_queue"
    __bind_key__ = "comms_db_3"
    __table_args__ = {"schema": SCHEMA_DICT[__bind_key__]}

    queue_id = DB.Column(DB.Integer, primary_key=True)
    ts = DB.Column(DB.DateTime, nullable=False, default=datetime.now)
    task_id = DB.Column(DB.String(40), nullable=False)
    sms_data = DB.Column(DB.String(32000), nullable=False)
    user_id = DB.Column(DB.Integer, DB.ForeignKey(
        f"{SCHEMA_DICT['commons_db']}.users.user_id"), nullable=False)
    ts_sending = DB.Column(DB.DateTime)
    ts_sent = DB.Column(DB.DateTime)
    ts_cancelled = DB.Column(DB.DateTime)
    cancelled_by = DB.Column(DB.Integer)

    def __repr__(self):
        return (f"Type <{self.__class__.__name__}> Priority ID: {self.queue_id}"
                f" TS: {self.ts}")


class GetSMSInboxForQASchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation SMS inbox for QA
    """
    timestamp = fields.DateTime("%Y-%m-%d %H:%M:%S")
    inbox_id = fields.Integer()
    message = fields.String()
    sender = fields.String()
    affiliation = fields.String()
    site_code = fields.String()
    tag = fields.String()

class SmsInboxUsersSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """

    mobile_id = fields.Integer()
    mobile_details = MARSHMALLOW.Nested(UserMobilesSchema)
    sms_tags = MARSHMALLOW.Nested("SmsInboxUserTagsSchema",
                                  many=True)  # NOTE EXCLUDE exclude=["outbox_message"]

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsInboxUsers
        unknown = EXCLUDE


class SmsOutboxUsersSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """
    send_status = MARSHMALLOW.Nested("SmsOutboxUserStatusSchema", many=True)
    sms_tags = MARSHMALLOW.Nested("SmsOutboxUserTagsSchema",
                                  many=True)  # NOTE EXCLUDE exclude=["outbox_message"]

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsOutboxUsers
        unknown = EXCLUDE


class SmsOutboxUserStatusSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """
    mobile_id = fields.Integer()
    outbox_message = fields.Nested(SmsOutboxUsersSchema,
                                   exclude=("send_status", ))
    mobile_details = MARSHMALLOW.Nested(UserMobilesSchema)

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsOutboxUserStatus
        unknown = EXCLUDE


class ViewLatestMessagesSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """

    class Meta:
        """Saves table class structure as schema model"""
        model = ViewLatestMessages


class TempLatestMessagesSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """

    convo_id = fields.Integer()
    mobile_id = fields.Integer()
    inbox_id = fields.Integer()
    outbox_id = fields.Integer()
    sms_msg = fields.String()
    ts = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_received = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_written = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_sent = fields.DateTime("%Y-%m-%d %H:%M:%S")
    source = fields.String()
    send_status = fields.Integer()
    msg_source = fields.String()


class SmsTagsSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsTags
        exclude = ["smsinbox_user_tags", "smsoutbox_user_tags"]
        unknown = EXCLUDE


class SmsInboxUserTagsSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of Users class
    """

    tag_id = fields.Integer()
    tag = MARSHMALLOW.Nested("SmsTagsSchema")
    user_id = fields.Integer()

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsInboxUserTags
        unknown = EXCLUDE


class SmsOutboxUserTagsSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of SmsTags class
    """

    tag_id = fields.Integer()
    tag = MARSHMALLOW.Nested("SmsTagsSchema")
    user_id = fields.Integer()

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsOutboxUserTags
        unknown = EXCLUDE


class SmsPrioritySchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of SmsPriority class
    """

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsPriority
        unknown = EXCLUDE


class SmsQueueSchema(MARSHMALLOW.SQLAlchemyAutoSchema):
    """
    Schema representation of SmsQueue class
    """

    ts = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_sending = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_sent = fields.DateTime("%Y-%m-%d %H:%M:%S")
    ts_cancelled = fields.DateTime("%Y-%m-%d %H:%M:%S")

    class Meta:
        """Saves table class structure as schema model"""
        model = SmsQueue
        unknown = EXCLUDE
