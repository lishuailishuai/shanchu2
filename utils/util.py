# -*- coding: utf-8 -*-
from utils.connection_helper import get_hive_cursor
from datetime import datetime, timedelta
from plugins.comwx import ComwxApi
from plugins.DingdingAlert import DingdingAlert
import pendulum

repair_table_query = '''
MSCK REPAIR TABLE %s
'''
work_times = 15 * 3600
driver_online_time_key = "online_time:time:2:{driver_id}:{dt}"
# dt format YYYYmmDD


def mapper(x):
    if x is None:
        x = 0
    return x


def raw_data_mapper(x):
    res = 0
    try:
        res = int(x)
    except:
        pass
    return res


def query_repair_table(sql):
    cursor = get_hive_cursor()
    cursor.execute(sql)
    cursor.close()


def query_hive_data(sql):
    cursor = get_hive_cursor()
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    return result


def n_days_ago(n_time, days):
    now_time = datetime.strptime(n_time, '%Y-%m-%d')
    delta = timedelta(days=days)
    n_days = now_time - delta
    return n_days.strftime("%Y-%m-%d")


def double_digit(x):
    if x < 10:
        return "0" + str(x)
    return str(x)


def time_transfer(seconds):
    hour = seconds // 3600
    minute = (seconds % 3600) // 60
    sec = seconds % 60
    res = ""
    if hour > 0:
        res = "{hour}h:{min}m:{sec}s".format(hour=str(hour),
                                                       min=str(minute), sec=double_digit(sec))
    elif minute > 0:
        res = "{min}m:{sec}s".format(min=str(minute), sec=double_digit(sec))
    elif sec > 0:
        res = "{sec}s".format(sec=str(sec))
    return res

def on_success_callback(context):
    # 定时最大执行延时12小时
    max_delayed_time=43200
    # 正常执行时间
    next_execution_dt = pendulum.parse(str(context['next_execution_date']))
    next_execution_ts = next_execution_dt.int_timestamp
    # 当前时间
    now_dt = pendulum.parse('now')
    now_ts = now_dt.int_timestamp

    time_diff = now_ts - next_execution_ts

    if time_diff >= max_delayed_time:
        # 钉钉报警
        dingding_alert = DingdingAlert('https://oapi.dingtalk.com/robot/send?access_token=928e66bef8d88edc89fe0f0ddd52bfa4dd28bd4b1d24ab4626c804df8878bb48')
        task = "{dag}.{task}".format(dag=context['task_instance'].dag_id, task=context['task_instance'].task_id)
        msg="任务回溯操作{task},计划执行时间：{ne},当前执行时间：{nt}".format(
            task=task,
            ne=next_execution_dt,
            nt=now_dt
        )
        dingding_alert.send('DW {msg} 产出超时'.format(
            msg=msg
        ))
