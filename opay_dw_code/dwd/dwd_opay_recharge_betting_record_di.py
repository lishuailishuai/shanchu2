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
from plugins.TaskTimeoutMonitor import TaskTimeoutMonitor
from plugins.TaskTouchzSuccess import TaskTouchzSuccess
import json
import logging
from airflow.models import Variable
import requests
import os

##
# 央行月报汇报指标
#
args = {
    'owner': 'xiedong',
    'start_date': datetime(2019, 11, 2),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}


dag = airflow.DAG('dwd_opay_recharge_betting_record_di',
                  schedule_interval="00 03 * * *",
                  default_args=args,
                  catchup=False)

##----------------------------------------- 依赖 ---------------------------------------##
dim_opay_user_base_di_prev_day_task = UFileSensor(
    task_id='dim_opay_user_base_di_prev_day_task',
    filepath='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dim_opay_user_base_di/country_code=NG",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_betting_topup_record_di_prev_day_task = UFileSensor(
    task_id='ods_sqoop_base_betting_topup_record_di_prev_day_task',
    filepath='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/betting_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)


##----------------------------------------- 变量 ---------------------------------------##
db_name = "opay_dw"
table_name = "dwd_opay_recharge_betting_record_di"
hdfs_path="ufile://opay-datalake/opay/opay_dw/" + table_name


def dwd_opay_recharge_betting_record_di_sql_task(ds):
    HQL='''
    set hive.exec.dynamic.partition.mode=nonstrict;
    set hive.exec.parallel=true;
    insert overwrite table {db}.{table} 
    partition(country_code, dt)
    select 
        order_di.id,
        order_di.order_no,
        order_di.user_id,
        if(order_di.create_time < nvl(user_di.agent_upgrade_time, '9999-01-01 00:00:00'), 'customer', 'agent') user_role,
        order_di.pay_channel,
        order_di.merchant_id,
        order_di.out_order_no,
        order_di.amount,
        order_di.country,
        order_di.currency,
        order_di.pay_status,
        order_di.order_status,
        order_di.fee_amount,
        order_di.fee_pattern,
        order_di.error_msg,
        order_di.betting_provider as service_provider,
        case upper(order_di.betting_provider)
            when 'BET9JA' then '201'
            when 'SUPABET' then '202'
            when 'NAIRABET' then '203'
            else '200'
            end as service_provider_id,
        order_di.recipient_betting_account as recharge_account,
        order_di.recipient_betting_name as recharge_account_name,
        order_di.outward_id,
        order_di.outward_type,
        order_di.out_channel_id,
        order_di.create_time,
        order_di.update_time,
        order_di.business_no as channel_order_no,
        case order_di.country
            when 'NG' then 'NG'
            when 'NO' then 'NO'
            when 'GH' then 'GH'
            when 'BW' then 'BW'
            when 'GH' then 'GH'
            when 'KE' then 'KE'
            when 'MW' then 'MW'
            when 'MZ' then 'MZ'
            when 'PL' then 'PL'
            when 'ZA' then 'ZA'
            when 'SE' then 'SE'
            when 'TZ' then 'TZ'
            when 'UG' then 'UG'
            when 'US' then 'US'
            when 'ZM' then 'ZM'
            when 'ZW' then 'ZW'
            else 'NG'
            end as country_code,
        '{pt}' dt
    from
    (
        select 
            id,
                order_no,
                user_id,
                merchant_id,
                out_order_no,
                amount,
                country,
                currency,
                pay_channel,
                pay_status,
                order_status,
                fee_amount,
                fee_pattern,
                error_msg,
                betting_provider,
                recipient_betting_account,
                recipient_betting_name,
                outward_id,
                outward_type,
                out_channel_id,
                create_time,
                update_time,
                user_role,
                business_no
        from opay_dw_ods.ods_sqoop_base_betting_topup_record_di
        where dt = '{pt}'
    ) order_di
    left join
    (
        select * from 
        (
            select user_id, role, agent_upgrade_time, row_number() over(partition by user_id order by update_time desc) rn 
            from opay_dw.dim_opay_user_base_di
        ) user_temp where rn = 1
    ) user_di
    on user_di.user_id = order_di.user_id
    '''.format(
        pt=ds,
        table=table_name,
        db=db_name
    )
    return HQL



# 主流程
def execution_data_task_id(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = dwd_opay_recharge_betting_record_di_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)


    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")


dwd_opay_recharge_betting_record_di_task = PythonOperator(
    task_id='dwd_opay_recharge_betting_record_di_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

dim_opay_user_base_di_prev_day_task >> dwd_opay_recharge_betting_record_di_task
ods_sqoop_base_betting_topup_record_di_prev_day_task >> dwd_opay_recharge_betting_record_di_task