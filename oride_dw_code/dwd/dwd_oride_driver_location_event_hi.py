# -*- coding: utf-8 -*-
import airflow
from datetime import datetime, timedelta
from airflow.operators.hive_operator import HiveOperator
from airflow.operators.impala_plugin import ImpalaOperator
from utils.connection_helper import get_hive_cursor
from airflow.operators.python_operator import PythonOperator
from airflow.contrib.hooks.redis_hook import RedisHook
from airflow.hooks.hive_hooks import HiveCliHook, HiveServer2Hook
from airflow.operators.hive_to_mysql import HiveToMySqlTransfer
from airflow.operators.mysql_operator import MySqlOperator
from airflow.operators.dagrun_operator import TriggerDagRunOperator
from airflow.sensors.external_task_sensor import ExternalTaskSensor
from airflow.operators.bash_operator import BashOperator
from airflow.sensors.named_hive_partition_sensor import NamedHivePartitionSensor
from airflow.sensors.hive_partition_sensor import HivePartitionSensor
from airflow.sensors import UFileSensor
from airflow.sensors import OssSensor
from plugins.TaskTimeoutMonitor import TaskTimeoutMonitor
from plugins.TaskTouchzSuccess import TaskTouchzSuccess
import json
import logging
from airflow.models import Variable
import requests
import os

args = {
    'owner': 'linan',
    'start_date': datetime(2019, 5, 20),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('dwd_oride_driver_location_event_hi',
                  schedule_interval="40 * * * *",
                  default_args=args,
                  )

##----------------------------------------- 变量 ---------------------------------------##

db_name="oride_dw"
table_name="dwd_oride_driver_location_event_hi"

##----------------------------------------- 依赖 ---------------------------------------##

#获取变量
code_map=eval(Variable.get("sys_flag"))

#判断ufile(cdh环境)
if code_map["id"].lower()=="ufile":

    # 依赖前一小时分区
    dwd_oride_client_event_detail_hi_hour_task = UFileSensor(
        task_id='dwd_oride_client_event_detail_hi_hour_task',
        filepath='{hdfs_path_str}/country_code=nal/dt={pt}/hour={hour}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwd_oride_client_event_detail_hi",
            pt='{{ds}}',
            hour='{{ execution_date.strftime("%H") }}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
        dag=dag
    )
# 路径
    hdfs_path="ufile://opay-datalake/oride/oride_dw/"+table_name
else:
    print("成功")

    dwd_oride_client_event_detail_hi_hour_task = OssSensor(
        task_id='dwd_oride_client_event_detail_hi_hour_task',
        bucket_key='{hdfs_path_str}/country_code=nal/dt={pt}/hour={hour}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwd_oride_client_event_detail_hi",
            pt='{{ds}}',
            hour='{{ execution_date.strftime("%H") }}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
        dag=dag
    )
    # 路径
    hdfs_path = "oss://opay-datalake/oride/oride_dw/" + table_name

##----------------------------------------- 任务超时监控 ---------------------------------------##

def fun_task_timeout_monitor(ds, execution_date, dag, **op_kwargs):
    dag_ids = dag.dag_id

    tb = [
        {"dag":dag,"db": "oride_dw", "table": "{dag_name}".format(dag_name=dag_ids),
         "partition": "country_code=nal/dt={pt}/hour={hour}".format(pt=ds, hour=execution_date.strftime("%H")),
         "timeout": "1200"}
    ]

    TaskTimeoutMonitor().set_task_monitor(tb)


task_timeout_monitor = PythonOperator(
    task_id='task_timeout_monitor',
    python_callable=fun_task_timeout_monitor,
    provide_context=True,
    dag=dag
)


##----------------------------------------- 脚本 ---------------------------------------##


def dwd_oride_location_driver_event_hi_sql_task(ds, execution_date):
    HQL = '''
    set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;

    INSERT OVERWRITE TABLE {db}.{table} partition(country_code,dt,hour)
    SELECT  t.order_id --订单id 
           ,t.driver_id --司机id 
           ,replace(concat_ws(',',collect_set(if(accept_order_click_lat is null,'',accept_order_click_lat))),',','')                                 AS accept_order_click_lat --accept_order_click，事件，纬度 
           ,replace(concat_ws(',',collect_set(if(accept_order_click_lng is null,'',accept_order_click_lng))),',','')                                 AS accept_order_click_lng --accept_order_click，事件，经度 
           ,replace(concat_ws(',',collect_set(if(confirm_arrive_click_arrived_lat is null,'',confirm_arrive_click_arrived_lat))),',','')             AS confirm_arrive_click_arrived_lat --confirm_arrive_click_arrived，事件，纬度 
           ,replace(concat_ws(',',collect_set(if(confirm_arrive_click_arrived_lng is null,'',confirm_arrive_click_arrived_lng))),',','')             AS confirm_arrive_click_arrived_lng --confirm_arrive_click_arrived，事件，经度 
           ,replace(concat_ws(',',collect_set(if(pick_up_passengers_sliding_arrived_lat is null,'',pick_up_passengers_sliding_arrived_lat))),',','') AS pick_up_passengers_sliding_arrived_lat --pick_up_passengers_sliding_arrived，事件，纬度 
           ,replace(concat_ws(',',collect_set(if(pick_up_passengers_sliding_arrived_lng is null,'',pick_up_passengers_sliding_arrived_lng))),',','') AS pick_up_passengers_sliding_arrived_lng --pick_up_passengers_sliding_arrived，事件，经度 
           ,replace(concat_ws(',',collect_set(if(start_ride_sliding_lat is null,'',start_ride_sliding_lat))),',','')                                 AS start_ride_sliding_lat --start_ride_sliding，事件，纬度 
           ,replace(concat_ws(',',collect_set(if(start_ride_sliding_lng is null,'',start_ride_sliding_lng))),',','')                                 AS start_ride_sliding_lng --start_ride_sliding，事件，经度 
           ,replace(concat_ws(',',collect_set(if(start_ride_sliding_arrived_lat is null,'',start_ride_sliding_arrived_lat))),',','')                 AS start_ride_sliding_arrived_lat --start_ride_sliding_arrived，事件，纬度 
           ,replace(concat_ws(',',collect_set(if(start_ride_sliding_arrived_lng is null,'',start_ride_sliding_arrived_lng))),',','')                 AS start_ride_sliding_arrived_lng --start_ride_sliding_arrived，事件，经度 
           ,'nal'                                                                                                                                    AS country_code 
           ,'{now_day}'                                                                                                                              AS dt 
           ,'{now_hour}'                                                                                                                             AS hour
    FROM 
    (
        SELECT  get_json_object(event_value,'$.order_id') order_id 
               ,user_id                                                                                         AS driver_id 
               ,if(event_name = 'accept_order_click',get_json_object(event_value,'$.lat'),null)                 AS accept_order_click_lat 
               ,if(event_name = 'accept_order_click',get_json_object(event_value,'$.lng'),null)                 AS accept_order_click_lng 
               ,if(event_name = 'confirm_arrive_click_arrived',get_json_object(event_value,'$.lat'),null)       AS confirm_arrive_click_arrived_lat 
               ,if(event_name = 'confirm_arrive_click_arrived',get_json_object(event_value,'$.lng'),null)       AS confirm_arrive_click_arrived_lng 
               ,if(event_name = 'pick_up_passengers_sliding_arrived',get_json_object(event_value,'$.lat'),null) AS pick_up_passengers_sliding_arrived_lat 
               ,if(event_name = 'pick_up_passengers_sliding_arrived',get_json_object(event_value,'$.lng'),null) AS pick_up_passengers_sliding_arrived_lng 
               ,if(event_name = 'start_ride_sliding',get_json_object(event_value,'$.lat'),null)                 AS start_ride_sliding_lat 
               ,if(event_name = 'start_ride_sliding',get_json_object(event_value,'$.lng'),null)                 AS start_ride_sliding_lng 
               ,if(event_name = 'start_ride_sliding_arrived',get_json_object(event_value,'$.lat'),null)         AS start_ride_sliding_arrived_lat 
               ,if(event_name = 'start_ride_sliding_arrived',get_json_object(event_value,'$.lng'),null)         AS start_ride_sliding_arrived_lng
        FROM oride_dw.dwd_oride_client_event_detail_hi
        WHERE dt = '{now_day}' 
        AND hour = '{now_hour}' 
        AND event_name IN ( 'accept_order_click', 'confirm_arrive_click_arrived', 'pick_up_passengers_sliding_arrived', 'start_ride_sliding', 'start_ride_sliding_arrived' )  
    ) t
    WHERE t.order_id is not null 
    GROUP BY  t.order_id 
             ,t.driver_id 
    ;

'''.format(
        pt=ds,
        now_day=ds,
        now_hour=execution_date.strftime("%H"),
        table=table_name,
        db=db_name
    )
    return HQL


# 熔断数据，如果数据重复，报错
def check_key_data_task(ds, execution_date):
    cursor = get_hive_cursor()

    # 主键重复校验
    check_sql = '''
    SELECT count(1)-count(distinct (concat(order_id,'_',driver_id))) as cnt
      FROM {db}.{table}
      WHERE dt='{pt}' and hour ='{now_hour}'
      and country_code in ('nal')
    '''.format(
        pt=ds,
        now_day=ds,
        now_hour=execution_date.strftime("%H"),
        table=table_name,
        db=db_name
    )

    logging.info('Executing 主键重复校验: %s', check_sql)

    cursor.execute(check_sql)

    res = cursor.fetchone()

    if res[0] > 1:
        flag = 1
        raise Exception("Error The primary key repeat !", res)
        sys.exit(1)
    else:
        flag = 0
        print("-----> Notice Data Export Success ......")

    return flag


# 主流程
def execution_data_task_id(ds, execution_date, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = dwd_oride_location_driver_event_hi_sql_task(ds, execution_date)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)

    # 熔断数据
    # check_key_data_task(ds, execution_date)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "false",
                                                 execution_date.strftime("%H"))


dwd_oride_driver_location_event_hi_task = PythonOperator(
    task_id='dwd_oride_driver_location_event_hi_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

dwd_oride_client_event_detail_hi_hour_task >> dwd_oride_driver_location_event_hi_task
