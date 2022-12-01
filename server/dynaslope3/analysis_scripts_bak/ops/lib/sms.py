from datetime import timedelta
import pandas as pd


def check_sent(release, sent):
    data_ts = pd.to_datetime(release['data_ts'].values[0])
    release_sent = sent.loc[(sent.ts_written >= data_ts) & (sent.ts_written <= data_ts+timedelta(hours=4)), :]
    sent_sched = pd.merge(release, release_sent, how='left', on=['site_id', 'user_id', 'mobile_id'])
    sent_sched = sent_sched.drop_duplicates(['site_id', 'data_ts', 'user_id', 'mobile_id'])
    return sent_sched

def ewi_sched(sched, recipients, sent, site_names):
    sms_sched = pd.merge(sched, recipients, how='left', on='site_id')
    sms_sched = sms_sched.loc[sms_sched.data_ts > sms_sched.start_ewi_recipient, :]
    if len(sms_sched) != 0:
        per_ts = sms_sched.groupby(['data_ts'], as_index=False)
        sent_sched = per_ts.apply(check_sent, sent=sent).reset_index(drop=True)
        #remove special cases and nonrecipient of extended/routine
        sent_sched = sent_sched.loc[(sent_sched.pub_sym_id - 1 >= sent_sched.alert_level) & ~(((sent_sched.extended == 1)|(sent_sched.event == 0)) & (sent_sched.alert_level == -1)), :]
    else:
        sent_sched = pd.DataFrame()
    return sent_sched