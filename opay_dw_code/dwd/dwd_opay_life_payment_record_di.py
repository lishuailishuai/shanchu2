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
from airflow.sensors import OssSensor
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
    'start_date': datetime(2019, 11, 11),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('dwd_opay_life_payment_record_di',
                  schedule_interval="20 01 * * *",
                  default_args=args,
                  )

##----------------------------------------- 依赖 ---------------------------------------##
ods_sqoop_base_user_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_user_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_user/user",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_merchant_df_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_merchant_df_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop/opay_merchant/merchant",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_betting_topup_record_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_betting_topup_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/betting_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_tv_topup_record_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_tv_topup_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/tv_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_electricity_topup_record_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_electricity_topup_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/electricity_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_airtime_topup_record_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_airtime_topup_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/airtime_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_sqoop_base_mobiledata_topup_record_di_prev_day_task = OssSensor(
    task_id='ods_sqoop_base_mobiledata_topup_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop_di/opay_transaction/mobiledata_topup_record",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

dim_opay_life_payment_commission_df_prev_day_task = OssSensor(
    task_id='dim_opay_life_payment_commission_df_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dim_opay_life_payment_commission_df/country_code=NG",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)


##----------------------------------------- 任务超时监控 ---------------------------------------##
def fun_task_timeout_monitor(ds, dag, **op_kwargs):
    dag_ids = dag.dag_id

    msg = [
        {"dag":dag, "db": "opay_dw", "table": "{dag_name}".format(dag_name=dag_ids),
         "partition": "country_code=NG/dt={pt}".format(pt=ds), "timeout": "3000"}
    ]

    TaskTimeoutMonitor().set_task_monitor(msg)


task_timeout_monitor = PythonOperator(
    task_id='task_timeout_monitor',
    python_callable=fun_task_timeout_monitor,
    provide_context=True,
    dag=dag
)

##----------------------------------------- 变量 ---------------------------------------##
db_name = "opay_dw"
table_name = "dwd_opay_life_payment_record_di"
hdfs_path = "oss://opay-datalake/opay/opay_dw/" + table_name
config = eval(Variable.get("opay_time_zone_config"))

def dwd_opay_life_payment_record_di_sql_task(ds):
    HQL = '''
    
    set mapred.max.split.size=1000000;
    set hive.exec.dynamic.partition.mode=nonstrict;
    set hive.exec.parallel=true;
    with 
        dim_merchant_data as (
            select 
                merchant_id, merchant_name, merchant_type
            from opay_dw_ods.ods_sqoop_base_merchant_df
            where dt = if('{pt}' <= '2019-12-11', '2019-12-11', '{pt}')
        ),
        dim_user_merchant_data as (
            select 
                trader_id, trader_name, trader_role, trader_kyc_level, trader_type, if(state is null or state = '', '-', state) as state
            from (
                select 
                    user_id as trader_id, concat(first_name, ' ', middle_name, ' ', surname) as trader_name, `role` as trader_role, 
                    kyc_level as trader_kyc_level, 'USER' as trader_type, state,
                    row_number() over(partition by user_id order by update_time desc) rn
                from opay_dw_ods.ods_sqoop_base_user_di
                where dt <= '{pt}'
            ) uf where rn = 1
            union all
            select 
                merchant_id as trader_id, merchant_name as trader_name, merchant_type as trader_role, '-' as trader_kyc_level, 'MERCHANT' as trader_type, '-' as state
            from dim_merchant_data
        ),
        dim_lp_commission_data as (
            select 
                sub_service_type, recharge_service_provider, fee_rate
            from opay_dw.dim_opay_life_payment_commission_df where dt = '{pt}'
        )
    insert overwrite table {db}.{table} 
    partition(country_code, dt)

    select 
        t1.order_no, t1.amount, t1.currency, 
        t2.trader_type as originator_type, t2.trader_role as originator_role, t2.trader_kyc_level as originator_kyc_level, t1.originator_id, t2.trader_name as originator_name,
        'MERCHANT' as affiliate_type, t3.merchant_type as affiliate_role, t3.merchant_id as affiliate_id, t3.merchant_name as affiliate_name,
        t1.recharge_service_provider, replace(t1.recharge_account, '+234', '') as recharge_account, t1.recharge_account_name, t1.recharge_set_meal,
        t1.create_time, t1.update_time, t1.country, 'Life Payment' as top_service_type, t1.sub_service_type,
        t1.order_status, t1.error_code, t1.error_msg, nvl(t1.client_source, '-'), t1.pay_way, t1.pay_status, t1.top_consume_scenario, t1.sub_consume_scenario, t1.pay_amount,
        t1.fee_amount, t1.fee_pattern, t1.outward_id, t1.outward_type,
        if(t4.fee_rate is null or t1.order_status != 'SUCCESS', 0, round(t1.amount * t4.fee_rate, 2)) as provider_share_amount, t2.state,
        'NG' as country_code,
        '{pt}' dt

    from (
        select 
            order_no, amount, currency, user_id as originator_id, 
            merchant_id as affiliate_id, 
            tv_provider as recharge_service_provider, recipient_tv_account_no as recharge_account, recipient_tv_account_name as recharge_account_name, tv_plan as recharge_set_meal,
            default.localTime("{config}", 'NG',create_time, 0) as create_time,
            default.localTime("{config}", 'NG',update_time, 0) as update_time,  
            country, 'TV' sub_service_type, 
            order_status, error_code, error_msg, client_source, pay_channel as pay_way, pay_status, 'TV' as top_consume_scenario, 'TV' as sub_consume_scenario, amount as pay_amount,
            nvl(fee, 0) as fee_amount, nvl(fee_pattern, '-') as fee_pattern, nvl(outward_id, '-') as outward_id, nvl(outward_type, '-') as outward_type
        from opay_dw_ods.ods_sqoop_base_tv_topup_record_di
        where dt = '{pt}'
        union all
        select 
            order_no, amount, currency, user_id as originator_id,
            merchant_id as affiliate_id, 
            betting_provider as recharge_service_provider, recipient_betting_account as recharge_account, recipient_betting_name as recharge_account_name, '-' as recharge_set_meal,
            default.localTime("{config}", 'NG',create_time, 0) as create_time,
            default.localTime("{config}", 'NG',update_time, 0) as update_time,  
            country, 'Betting' sub_service_type,
            order_status, error_code, error_msg, client_source, pay_channel as pay_way, pay_status, 'Betting' as top_consume_scenario, 'Betting' as sub_consume_scenario, 
            if(actual_pay_amount is null or actual_pay_amount = 0, amount, actual_pay_amount) as pay_amount, 
            nvl(fee_amount, 0) as fee_amount, nvl(fee_pattern, '-') as fee_pattern, nvl(outward_id, '-') as outward_id, nvl(outward_type, '-') as outward_type
        from opay_dw_ods.ods_sqoop_base_betting_topup_record_di
        where dt = '{pt}' and betting_provider != '' and betting_provider != 'supabet' and betting_provider is not null
        union all
        select 
            order_no, amount, currency, user_id as originator_id,
            merchant_id as affiliate_id,
            telecom_perator as recharge_service_provider,
            recipient_mobile as recharge_account, '-' as recharge_account_name, '-' as recharge_set_meal,
            default.localTime("{config}", 'NG',create_time, 0) as create_time,
            default.localTime("{config}", 'NG',update_time, 0) as update_time,  
            country, 'Mobiledata' sub_service_type,
            order_status, error_code, error_msg, client_source, pay_channel as pay_way, pay_status, 'Mobiledata' as top_consume_scenario, 'Mobiledata' as sub_consume_scenario,
            amount as pay_amount,
            nvl(fee_amount, 0) as fee_amount, nvl(fee_pattern, '-') as fee_pattern, nvl(out_ward_id, '-') as outward_id, nvl(out_ward_type, '-') as outward_type
        from opay_dw_ods.ods_sqoop_base_mobiledata_topup_record_di
        where dt = '{pt}'   
        union all
        select 
            order_no, amount, currency, user_id as originator_id,
            merchant_id as affiliate_id,
            telecom_perator as recharge_service_provider, recipient_mobile as recharge_account, '-' as recharge_account_name, '-' as recharge_set_meal,
            default.localTime("{config}", 'NG',create_time, 0) as create_time,
            default.localTime("{config}", 'NG',update_time, 0) as update_time,  
            country, 'Airtime' sub_service_type,
            order_status, error_code, error_msg, client_source, pay_channel as pay_way, pay_status, 'Airtime' as top_consume_scenario, 'Airtime' as sub_consume_scenario,
            if(actual_pay_amount is null or actual_pay_amount = 0, amount, actual_pay_amount) as pay_amount,
            nvl(fee_amount, 0) as fee_amount, nvl(fee_pattern, '-') as fee_pattern, nvl(out_ward_id, '-') as outward_id, nvl(out_ward_type, '-') as outward_type
        from opay_dw_ods.ods_sqoop_base_airtime_topup_record_di
        where dt = '{pt}' 
        union all
        select 
            order_no, amount, currency, user_id as originator_id,
            merchant_id as affiliate_id,
            recipient_elec_perator as recharge_service_provider, recipient_elec_account as recharge_account, '-' as recharge_account_name, electricity_payment_plan as recharge_set_meal,
            default.localTime("{config}", 'NG',create_time, 0) as create_time,
            default.localTime("{config}", 'NG',update_time, 0) as update_time, 
            country, 'Electricity' sub_service_type,
            order_status, error_code, error_msg, client_source, pay_channel as pay_way, pay_status, 'Electricity' as top_consume_scenario, 'Electricity' as sub_consume_scenario,
            amount as pay_amount,
            nvl(fee_amount, 0) as fee_amount, nvl(fee_pattern, '-') as fee_pattern, nvl(out_ward_id, '-') as outward_id, nvl(out_ward_type, '-') as outward_type
        from opay_dw_ods.ods_sqoop_base_electricity_topup_record_di
        where dt = '{pt}'
    ) t1 
    left join dim_user_merchant_data t2 on t1.originator_id = t2.trader_id
    left join dim_merchant_data t3 on t1.affiliate_id = t3.merchant_id
    left join dim_lp_commission_data t4 on t4.sub_service_type = t1.sub_service_type and t4.recharge_service_provider = t1.recharge_service_provider 
    '''.format(
        pt=ds,
        table=table_name,
        db=db_name,
        config=config
    )
    return HQL


# 主流程
def execution_data_task_id(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = dwd_opay_life_payment_record_di_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")


dwd_opay_life_payment_record_di_task = PythonOperator(
    task_id='dwd_opay_life_payment_record_di_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

ods_sqoop_base_user_di_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_merchant_df_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_electricity_topup_record_di_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_airtime_topup_record_di_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_tv_topup_record_di_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_mobiledata_topup_record_di_prev_day_task >> dwd_opay_life_payment_record_di_task
dim_opay_life_payment_commission_df_prev_day_task >> dwd_opay_life_payment_record_di_task
ods_sqoop_base_betting_topup_record_di_prev_day_task >> dwd_opay_life_payment_record_di_task