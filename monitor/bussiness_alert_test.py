# coding: utf-8
import airflow
from airflow.operators.python_operator import PythonOperator
from airflow.hooks.mysql_hook import MySqlHook
from airflow.models import Variable
import logging
import os
from plugins.DingdingAlert import DingdingAlert
import paramiko
from scp import SCPClient
import time
import datetime, time
import requests
from influxdb import InfluxDBClient
import json
import redis
import random

args = {
    'owner': 'yangmingze',
    'start_date': datetime.datetime(2020, 3, 22),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': datetime.timedelta(minutes=1),
    # 'email': ['bigdata_dw@opay-inc.com'],
    # 'email_on_failure': True,
    # 'email_on_retry': False,
}

dag = airflow.DAG(
    'bussiness_alert_test',
    schedule_interval="*/10 * * * *",
    concurrency=20,
    max_active_runs=1,
    default_args=args)

UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 默认预警地址
defalut_dingding_alert = "https://oapi.dingtalk.com/robot/send?access_token=ce1272d8448e8bd80cd8f2e6eb37ae1be13690013ebaf708517c7ae7162101bd"

#  metrics_name 指标名称，建议使用指标主题范围加业务线或渠道做区分,
#  influx_sql, (字段名称一定要写别名，绑定预警模板名称,在airflow 变量中设置模板)
#  alert_value_name [小于判断比例，大于判断比例],
#  compare_day 对比回推天数,
#  alert_1_level_address_name 一级预警地址,
#  alert_2_level_address_name 二级预警地址,
#  是否关闭预警，预警模板
# alert_mode 判断大于小于规则关系（1 小于，2 大于，3 大于和小于）
metrcis_list = [

    ####### 交易相关指标
    ## Airtime
    # 1
    (
        'Trade_Airtime',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'airtime_topup_record' AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 2
    (
        'Trade_Airtime_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'airtime_topup_record' AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Betting
    # 3
    (
        'Trade_Betting',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'betting_topup_record' AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 5
    (
        'Trade_Betting_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'betting_topup_record'  AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Electricity
    # 6
    (
        'Trade_Electricity',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'electricity_topup_record'  AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 7
    (
        'Trade_Electricity_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'electricity_topup_record' AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## TV
    # 8
    (
        'Trade_TV',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'tv_topup_record' AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 9
    (
        'Trade_TV_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'tv_topup_record'  AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Mobiledata
    # 10
    (
        'Trade_Mobiledata',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'mobiledata_topup_record'   AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 11
    (
        'Trade_Mobiledata_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'mobiledata_topup_record' AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Cash_In
    # 12
    (
        'Trade_Cash_In',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'cash_in_record' AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 13
    (
        'Trade_Cash_In_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'cash_in_record' AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Cash_Out
    # 14
    (
        'Trade_Cash_Out',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'cash_out_record' AND "__op" = 'c') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 15
    (
        'Trade_Cash_Out_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'cash_out_record' AND "order_status" = 'SUCCESS') and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## ACTransfer
    # 16
    (
        'Trade_ACTransfer',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'user_transfer_card_record' or "__source_table" = 'merchant_transfer_card_record') AND "__op" = 'c' and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 17
    (
        'Trade_ACTransfer_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'user_transfer_card_record' or "__source_table" = 'merchant_transfer_card_record') AND "order_status" = 'SUCCESS' and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## Pos
    # 18
    (
        'Trade_Pos',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'user_pos_transaction_record' or "__source_table" = 'merchant_pos_transaction_record') AND "__op" = 'c' and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    # 19
    (
        'Trade_Pos_Success',
        '''SELECT count(distinct("order_no")) AS "trade_success_cnt" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'user_pos_transaction_record' or "__source_table" = 'merchant_pos_transaction_record')  AND "order_status" = 'SUCCESS' and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),

    ## TopupWithCard
    # 20
    (
        'Trade_TopupWithCard',
        '''SELECT count(distinct("order_no")) AS "trade_cnt",count(distinct("user_id")) AS "trade_user_cnt" ,sum("amount") AS "trade_amount" FROM "OPAY_TRANSACTION_OP_EVENT" WHERE ("__source_table" = 'user_topup_record' or "__source_table" = 'merchant_topup_record') AND "__op" = 'c' and time > {time} GROUP BY time(10m) ''',
        'trade_alert_value',
        7,
        'trade_alert_level_1_address',
        'trade_alert_level_2_address',
        False,
        3
    ),


]


def get_redis_client():
    redis_client = redis.Redis(host='r-d7o4oicvcs16n22tnu.redis.eu-west-1.rds.aliyuncs.com', port=6379, db=4,
                               decode_responses=True)
    return redis_client


def alert(metrics_name, last_value, compare_value, alert_value, last_seconds, compare_day_ago_second,
          alert_1_level_name,
          alert_2_level_name,
          is_close_alert,
          alert_template_name):
    time = datetime.datetime.fromtimestamp(int(last_seconds)).strftime(DATE_FORMAT)
    compare_time = datetime.datetime.fromtimestamp(int(compare_day_ago_second)).strftime(DATE_FORMAT)

    logging.info(" =========  监控业务线指标名称  : {}  ".format(metrics_name))

    dingding_level_1_alert = None
    alert_template = Variable.get(alert_template_name)
    alert_value_1 = alert_value[0]
    alert_value_2 = alert_value[1]

    redis_client = get_redis_client()

    # 是否手动关闭预警
    if is_close_alert:
        dingding_level_1_alert = DingdingAlert(defalut_dingding_alert)

        dingding_level_1_alert.send(alert_template.format(
            time=time,
            compare_time=compare_time,
            metrics_name=metrics_name,
            last_value=last_value,
            compare_value=compare_value,
            alert_value_1="{}%".format(alert_value_1),
            alert_value_2="{}%".format(alert_value_2))
        )
        logging.info(" =========  进入关闭预警流程 ....... ")

    else:
        logging.info(" =========  进入 LEVEL 1  预警 .......")

        dingding_level_1_alert = DingdingAlert(Variable.get(alert_1_level_name))
        dingding_level_1_alert.send(alert_template.format(
            time=time,
            compare_time=compare_time,
            metrics_name=metrics_name,
            last_value=last_value,
            compare_value=compare_value,
            alert_value_1="{}%".format(alert_value_1),
            alert_value_2="{}%".format(alert_value_2))
        )

        logging.info(" =========  LEVEL 1 预警成功 ....... ")

        key = "{}_{}".format(metrics_name, alert_template_name)

        alert_times = redis_client.get(key)

        logging.info(" =========  预警记录次数 : {}  ".format(alert_times))

        if alert_times == None:
            alert_times = 1
        else:
            alert_times = int(alert_times)

        if alert_times >= 4:
            logging.info(" =========  进入 LEVEL 2  预警 .......")
            dingding_level_2_alert = DingdingAlert(Variable.get(alert_2_level_name))
            dingding_level_2_alert.send(alert_template.format(
                time=time,
                compare_time=compare_time,
                metrics_name=metrics_name,
                last_value=last_value,
                compare_value=compare_value,
                alert_value_1="{}%".format(alert_value_1),
                alert_value_2="{}%".format(alert_value_2))
            )
            logging.info(" =========  LEVEL 2 预警成功 ....... ")

        alert_times += 1
        redis_client.set(key, alert_times)

    redis_client.close()


# 清除之前所有记录预警次数
def clear_error_times(metrics_name, alert_template_name):
    redis_client = get_redis_client()

    key = "{}_{}".format(metrics_name, alert_template_name)
    redis_client.set(key, 0)
    logging.info(" =========  未发现异常，清除预警累计次数  {}  ..... ".format(key))

    redis_client.close()


# 判断小于
def handle_mode_1(metrics_name, last_value, compare_value, alert_value_1, alert_value_2, last_time,
                  compare_day_ago_second,
                  alert_1_level_name,
                  alert_2_level_name,
                  is_close_alert,
                  template_name
                  ):
    if last_value < int(compare_value * alert_value_1):
        alert_value_1 = int(alert_value_1 * 100)
        # alert(metrics_name, last_value, compare_value, [alert_value_1, ''], last_time,
        #       compare_day_ago_second,
        #       alert_1_level_name,
        #       alert_2_level_name, is_close_alert, template_name)
    else:
        clear_error_times(metrics_name, template_name)


# 判断大于
def handle_mode_2(metrics_name, last_value, compare_value, alert_value_1, alert_value_2, last_time,
                  compare_day_ago_second,
                  alert_1_level_name,
                  alert_2_level_name,
                  is_close_alert,
                  template_name
                  ):
    if last_value > int(compare_value * alert_value_2):
        alert_value_2 = int(alert_value_2 * 100)
        # alert(metrics_name, last_value, compare_value, ['', alert_value_2], last_time,
        #       compare_day_ago_second,
        #       alert_1_level_name,
        #       alert_2_level_name, is_close_alert, template_name)
    else:
        clear_error_times(metrics_name, template_name)


# 判断大于和小于情况
def handle_mode_3(metrics_name, last_value, compare_value, alert_value_1, alert_value_2, last_time,
                  compare_day_ago_second,
                  alert_1_level_name,
                  alert_2_level_name,
                  is_close_alert,
                  template_name
                  ):
    if last_value < int(compare_value * alert_value_1) or last_value > int(compare_value * alert_value_2):

        alert_value_1 = int(alert_value_1 * 100)
        alert_value_2 = int(alert_value_2 * 100)

        # alert(metrics_name, last_value, compare_value, [alert_value_1, alert_value_2], last_time,
        #       compare_day_ago_second,
        #       alert_1_level_name,
        #       alert_2_level_name, is_close_alert, template_name)
    else:
        clear_error_times(metrics_name, template_name)


def monitor_task(ds, metrics_name, influx_db_query_sql, alert_value_name, compare_day, alert_1_level_name,
                 alert_2_level_name, is_close_alert, mode,influx_db_id, **kwargs):
    last_time = 0
    data_map = dict()

    ## 增加随机数延迟

    # sleep = random.randint(10, 300)
    #
    # time.sleep(sleep)
    # logging.info(" =========  随机时间等待 : {} s ".format(sleep))

    #influx_client = InfluxDBClient('10.52.5.233', 8086, 'bigdata', 'opay321', 'serverDB')

    influx_client=influx_db_id

    date_time = datetime.datetime.strptime(ds, '%Y-%m-%d')
    time_condition = (date_time - datetime.timedelta(days=(compare_day + 1)))
    time_condition = int(time.mktime(time_condition.timetuple()))
    time_condition = "{}000000000".format(time_condition)

    logging.info(" =========  time_condition : {}".format(time_condition))

    alert_values = eval(Variable.get(alert_value_name))
    alert_value_1 = alert_values[0]
    alert_value_2 = alert_values[1]

    query_sql = influx_db_query_sql.format(time=time_condition)
    logging.info(" =========  query sql : {} ".format(query_sql))

    res = influx_client.query(query_sql)
    raw = res.raw
    series = raw.get('series')

    if series is None:
        logging.info(" =========  No data  ".format(str(raw)))
        return

    values = series[0]['values']
    columns = series[0]['columns']

    for i in range(len(values)):
        line = values[i]
        timestamp = line[0]
        utcTime = datetime.datetime.strptime(timestamp, UTC_FORMAT)
        timesecond = int(time.mktime(utcTime.timetuple()))
        data_map[timesecond] = line
        last_time = timesecond

        ## 获取倒数第二最新时间
        if i == len(values) - 2:
            break

    date = datetime.datetime.utcfromtimestamp(last_time)
    compare_day_ago = date - datetime.timedelta(days=compare_day)

    compare_day_ago_second = int(time.mktime(compare_day_ago.timetuple()))

    last_obj = data_map[last_time]
    compare_obj = data_map[compare_day_ago_second]

    for i in range(len(last_obj)):
        if i == 0:
            continue

        last_metrcis_value = None
        compare_metrcis_value = None
        if last_obj[i] is None:
            last_metrcis_value = 0
        else:
            last_metrcis_value = int(last_obj[i])

        if compare_obj[i] is None:
            compare_metrcis_value = 0
        else:
            compare_metrcis_value = int(compare_obj[i])

        logging.info(" =========  最新数据  时间 ：{}  , 指标值： {}  ".format(
            datetime.datetime.fromtimestamp(int(last_time)).strftime(DATE_FORMAT), last_metrcis_value))
        logging.info(" =========  对比日数据  时间 ：{}  , 指标值： {}  ".format(
            datetime.datetime.fromtimestamp(int(compare_day_ago_second)).strftime(DATE_FORMAT), compare_metrcis_value))
        logging.info(" =========  预警阈值比例值  ： {}   {}  ".format(alert_value_1, alert_value_2))
        logging.info(" =========  处理 mode  ： {}    ".format(mode))

        if mode == 1:
            handle_mode_1(metrics_name, last_metrcis_value, compare_metrcis_value, alert_value_1, alert_value_2,
                          last_time,
                          compare_day_ago_second,
                          alert_1_level_name,
                          alert_2_level_name, is_close_alert, columns[i])
        elif mode == 2:
            handle_mode_2(metrics_name, last_metrcis_value, compare_metrcis_value, alert_value_1, alert_value_2,
                          last_time,
                          compare_day_ago_second,
                          alert_1_level_name,
                          alert_2_level_name, is_close_alert, columns[i])
        elif mode == 3:
            handle_mode_3(metrics_name, last_metrcis_value, compare_metrcis_value, alert_value_1, alert_value_2,
                          last_time,
                          compare_day_ago_second,
                          alert_1_level_name,
                          alert_2_level_name, is_close_alert, columns[i])

    influx_client.close()


# def influx_conn():

#     influx_client=InfluxDBClient('10.52.5.233', 8086, 'bigdata', 'opay321', 'serverDB')

#     return influx_client


conn_conf_dict={}

for metrics_name, influx_db_query_sql, alert_value_name, compare_day, alert_1_level_name, alert_2_level_name, is_close_alert, mode in metrcis_list:

    conn_id="info"

    if conn_id not in conn_conf_dict:

        conn_conf_dict[conn_id] =InfluxDBClient('10.52.5.233', 8086, 'bigdata', 'opay321', 'serverDB')
        print("++++++++-----------------++++++++++")
        #influx_client=conn_conf_dict[conn_id]



    monitor = PythonOperator(
        task_id='monitor_task_{}'.format(metrics_name),
        python_callable=monitor_task,
        provide_context=True,
        op_kwargs={
            'metrics_name': metrics_name,
            'influx_db_query_sql': influx_db_query_sql,
            'alert_value_name': alert_value_name,
            'compare_day': compare_day,
            'alert_1_level_name': alert_1_level_name,
            'alert_2_level_name': alert_2_level_name,
            'is_close_alert': is_close_alert,
            'mode': mode,
            'influx_db_id':conn_conf_dict[conn_id]
        },
        dag=dag
    )
