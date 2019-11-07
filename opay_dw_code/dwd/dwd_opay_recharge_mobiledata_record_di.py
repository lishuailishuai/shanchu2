import airflow
from datetime import datetime, timedelta
from airflow.operators.hive_operator import HiveOperator
from airflow.operators.impala_plugin import ImpalaOperator
from utils.connection_helper import get_hive_cursor
from airflow.operators.python_operator import PythonOperator
from airflow.contrib.hooks.redis_hook import RedisHook
from airflow.hooks.hive_hooks import HiveCliHook
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


dag = airflow.DAG('dwd_opay_recharge_mobiledata_record_di',
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

##----------------------------------------- 任务超时监控 ---------------------------------------##
def fun_task_timeout_monitor(ds,dag,**op_kwargs):

    dag_ids=dag.dag_id

    msg = [
        {"db": "opay_dw", "table":"{dag_name}".format(dag_name=dag_ids), "partition": "country_code=NG/dt={pt}".format(pt=ds), "timeout": "3000"}
    ]

    TaskTimeoutMonitor().set_task_monitor(msg)

task_timeout_monitor= PythonOperator(
    task_id='task_timeout_monitor',
    python_callable=fun_task_timeout_monitor,
    provide_context=True,
    dag=dag
)

##----------------------------------------- 变量 ---------------------------------------##

table_name = "dwd_opay_recharge_mobiledata_record_di"
hdfs_path="ufile://opay-datalake/opay/opay_dw/" + table_name


##---- hive operator ---##
fill_dwd_opay_recharge_mobiledata_record_di_task = HiveOperator(
    task_id='fill_dwd_opay_recharge_mobiledata_record_di_task',
    hql='''
    set hive.exec.dynamic.partition.mode=nonstrict;
     
    insert overwrite table dwd_opay_recharge_mobiledata_record_di 
    partition(country_code, dt)
    select 
        order_di.id,
        order_di.order_no,
        order_di.user_id,
        if(order_di.create_time < nvl(user_di.agent_upgrade_time, '9999-01-01 00:00:00'), 'customer', 'agent') user_role,
        order_di.merchant_id,
        order_di.amount,
        order_di.country,
        order_di.currency,
        order_di.recipient_mobile recharge_account,
        order_di.telecom_perator service_provider,
       case order_di.telecom_perator
            when 'DataAir' then '301'
            when 'DataEti' then '302'
            when 'DataGlo' then '303'
            when 'DataMtn' then '304'
            else '300'
            end as service_provider_id,
        order_di.pay_channel,
        order_di.pay_status,
        order_di.order_status,
        order_di.error_code,
        order_di.error_msg,
        order_di.fee_amount,
        order_di.fee_pattern,
        order_di.out_ward_id,
        order_di.out_ward_type,
        order_di.recipient_email,
        order_di.current_balance,
        order_di.till_date_balance,
        order_di.audit_no,
        order_di.confirm_code,
        order_di.out_channel_id,
        order_di.out_channel_order_no out_order_no,
        order_di.business_no channel_order_no,
        order_di.create_time,
        order_di.update_time,
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
        order_di.dt
    from opay_dw_ods.ods_sqoop_base_mobiledata_topup_record_di order_di
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
        pt='{{ds}}'
    ),
    schema='opay_dw',
    dag=dag
)
##---- hive operator end ---##

##---- hive operator ---##
dwd_opay_recharge_mobiledata_record_di_task = HiveOperator(
    task_id='dwd_opay_recharge_mobiledata_record_di_task',
    hql='''
    set hive.exec.dynamic.partition.mode=nonstrict;
     
    insert overwrite table dwd_opay_recharge_mobiledata_record_di 
    partition(country_code, dt)
    select 
        order_di.id,
        order_di.order_no,
        order_di.user_id,
        if(order_di.create_time < nvl(user_di.agent_upgrade_time, '9999-01-01 00:00:00'), 'customer', 'agent') user_role,
        order_di.merchant_id,
        order_di.amount,
        order_di.country,
        order_di.currency,
        order_di.recipient_mobile recharge_account,
        order_di.telecom_perator service_provider,
       case order_di.telecom_perator
            when 'DataAir' then '301'
            when 'DataEti' then '302'
            when 'DataGlo' then '303'
            when 'DataMtn' then '304'
            else '300'
            end as service_provider_id,
        order_di.pay_channel,
        order_di.pay_status,
        order_di.order_status,
        order_di.error_code,
        order_di.error_msg,
        order_di.fee_amount,
        order_di.fee_pattern,
        order_di.out_ward_id,
        order_di.out_ward_type,
        order_di.recipient_email,
        order_di.current_balance,
        order_di.till_date_balance,
        order_di.audit_no,
        order_di.confirm_code,
        order_di.out_channel_id,
        order_di.out_channel_order_no out_order_no,
        order_di.business_no channel_order_no,
        order_di.create_time,
        order_di.update_time,
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
        order_di.dt
    from
    (
        select 
            id,
            order_no,
            user_id,
            merchant_id,
            channel_order_no,
            amount,
            country,
            currency,
            recipient_mobile,
            telecom_perator,
            pay_channel,
            pay_status,
            order_status,
            error_code,
            error_msg,
            fee_amount,
            fee_pattern,
            out_ward_id,
            out_ward_type,
            recipient_email,
            current_balance,
            till_date_balance,
            audit_no,
            confirm_code,
            out_channel_id,
            out_channel_order_no,
            business_no,
            create_time,
            update_time,
            dt
        from opay_dw_ods.ods_sqoop_base_mobiledata_topup_record_di
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
        pt='{{ds}}'
    ),
    schema='opay_dw',
    dag=dag
)

#生成_SUCCESS
def check_success(ds,dag,**op_kwargs):

    dag_ids=dag.dag_id

    msg = [
        {"table":"{dag_name}".format(dag_name=dag_ids),"hdfs_path": "{hdfsPath}/country_code=NG/dt={pt}".format(pt=ds,hdfsPath=hdfs_path)}
    ]

    TaskTouchzSuccess().set_touchz_success(msg)

touchz_data_success= PythonOperator(
    task_id='touchz_data_success',
    python_callable=check_success,
    provide_context=True,
    dag=dag
)

dim_opay_user_base_di_prev_day_task >> dwd_opay_recharge_mobiledata_record_di_task
dwd_opay_recharge_mobiledata_record_di_task >> touchz_data_success