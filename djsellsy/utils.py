import datetime


def date_str_to_ts(date_str, date_format='%d/%m/%Y %H:%M:%S'):
    date = datetime.datetime.strptime(date_str, date_format)
    date_ts = date.timestamp()
    return int(date_ts)
