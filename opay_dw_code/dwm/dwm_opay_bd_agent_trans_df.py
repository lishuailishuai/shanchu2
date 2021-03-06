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
from airflow.sensors import OssSensor
import json
import logging
from airflow.models import Variable
import requests
import os

args = {
    'owner': 'xiedong',
    'start_date': datetime(2020, 1, 16),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('dwm_opay_bd_agent_trans_df',
                  schedule_interval="30 01 * * *",
                  default_args=args
                  )

##----------------------------------------- 依赖 ---------------------------------------##
dwd_opay_cico_record_di_task = OssSensor(
    task_id='dwd_opay_cico_record_di_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwd_opay_cico_record_di/country_code=NG",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

dwd_opay_bd_agent_change_log_di_task = OssSensor(
    task_id='dwd_opay_bd_agent_change_log_di_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwd_opay_bd_agent_change_log_di/country_code=nal",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)
dwd_opay_pos_transaction_record_di_task = OssSensor(
    task_id='dwd_opay_pos_transaction_record_di_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwd_opay_pos_transaction_record_di/country_code=NG",
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
        {"dag":dag, "db": "opay_dw", "table":"{dag_name}".format(dag_name=dag_ids), "partition": "country_code=NG/dt={pt}".format(pt=ds), "timeout": "3000"}
    ]

    TaskTimeoutMonitor().set_task_monitor(msg)

task_timeout_monitor= PythonOperator(
    task_id='task_timeout_monitor',
    python_callable=fun_task_timeout_monitor,
    provide_context=True,
    dag=dag
)

##----------------------------------------- 变量 ---------------------------------------##
db_name="opay_dw"
table_name="dwm_opay_bd_agent_trans_df"
hdfs_path="oss://opay-datalake/opay/opay_dw/"+table_name

##---- hive operator ---##
def dwm_opay_bd_agent_trans_df_sql_task(ds):
    HQL='''
    
    set mapred.max.split.size=1000000;
    set hive.exec.dynamic.partition.mode=nonstrict;
    set hive.exec.parallel=true; --default false
    
	insert overwrite table {db}.{table} partition(country_code='NG', dt='{pt}')
	select 
        coalesce(
            pos_trans_data.bd_admin_user_id, 
            pos_distinct_data.bd_admin_user_id, 
            agent_data.bd_admin_user_id, 
            cico_data.bd_admin_user_id, 
            terminal_data.bd_admin_user_id) as bd_admin_user_id, 
        coalesce(
            pos_trans_data.business_date, 
            pos_distinct_data.business_date, 
            agent_data.business_date, 
            cico_data.business_date, 
            terminal_data.business_date) as business_date, 
        nvl(agent_data.audit_suc_cnt, 0) as audit_suc_cnt, 
        nvl(agent_data.audit_fail_cnt, 0) as audit_fail_cnt,
        nvl(ci_suc_order_cnt, 0) as ci_suc_order_cnt,
        nvl(ci_suc_order_amt, 0) as ci_suc_order_amt,
        nvl(co_suc_order_cnt, 0) as co_suc_order_cnt,
        nvl(co_suc_order_amt, 0) as co_suc_order_amt,
        nvl(bind_terminal_agent_cnt_his, 0) as bind_terminal_agent_cnt_his,
        nvl(bind_terminal_agent_cnt_m, 0) as bind_terminal_agent_cnt_m,
        nvl(pos_suc_amt, 0) as pos_suc_amt,
        nvl(pos_suc_cnt, 0) as pos_suc_cnt,
        nvl(pos_agent_cnt_m, 0) as pos_agent_cnt_m,
        nvl(pos_agent_cnt, 0) as pos_agent_cnt
    from (
        select 
            bd_admin_user_id, dt as business_date, 
            sum(if(to_agent_status = 1, 1, 0)) as audit_suc_cnt,
            sum(if(to_agent_status = 2, 1, 0)) as audit_fail_cnt
        from opay_dw.dwd_opay_bd_agent_change_log_di
        where dt <= '{pt}'
        group by bd_admin_user_id, dt
    ) agent_data full join (
        select 
            bd_admin_user_id, create_date as business_date, 
            sum(if(sub_service_type='Cash In', amount, 0)) as ci_suc_order_amt,
            sum(if(sub_service_type='Cash In', 1, 0)) as ci_suc_order_cnt,
            sum(if(sub_service_type='Cash Out', amount, 0)) as co_suc_order_amt,
            sum(if(sub_service_type='Cash Out', 1, 0)) as co_suc_order_cnt
        from (
            select
                bd_admin_user_id, sub_service_type, amount, date_format(create_time, 'yyyy-MM-dd') as create_date, row_number() over(partition by order_no order by update_time desc) rn
            from opay_dw.dwd_opay_cico_record_di
            where dt between date_format('{pt}', 'yyyy-MM-01') and '{pt}' and order_status = 'SUCCESS' and sub_service_type in ('Cash In', 'Cash Out') and bd_agent_status = 1
        ) t0 where rn = 1 and date_format(create_date, 'yyyy-MM') = date_format('{pt}', 'yyyy-MM')
        group by bd_admin_user_id, create_date
    ) cico_data on agent_data.bd_admin_user_id = cico_data.bd_admin_user_id and agent_data.business_date = cico_data.business_date
    -- terminal
    full join (
        select
            t0.bd_admin_user_id, 
            '{pt}' as business_date,
            count(distinct t1.owner_id) as bind_terminal_agent_cnt_his,
            count(distinct if(date_format(t1.create_time, 'yyyy-MM')=date_format('{pt}', 'yyyy-MM'), t1.owner_id, null)) as bind_terminal_agent_cnt_m
        from
        (
            select 
                user_id, bd_admin_user_id
            from opay_dw.dim_opay_bd_agent_df
            where dt = '{pt}' and agent_status = 1
        ) t0 left join (
            select
                owner_id, create_time
            from opay_dw.dim_opay_terminal_base_df 
            where dt = '{pt}'
        ) t1 on t0.user_id = t1.owner_id
        group by t0.bd_admin_user_id
    ) terminal_data on cico_data.bd_admin_user_id = terminal_data.bd_admin_user_id and cico_data.business_date = terminal_data.business_date
    -- pos trans
    full join (
        select 
            bd_admin_user_id, 
            create_date as business_date, 
            sum(amount) as pos_suc_amt,
            count(*) as pos_suc_cnt
        from (
            select
                bd_admin_user_id, amount, date_format(create_time, 'yyyy-MM-dd') as create_date, 
                row_number() over(partition by order_no order by update_time desc) rn
            from opay_dw.dwd_opay_pos_transaction_record_di
            where dt between date_format('{pt}', 'yyyy-MM-01') and '{pt}' and order_status = 'SUCCESS' and bd_agent_status = 1
        ) t0 where rn = 1 and date_format(create_date, 'yyyy-MM') = date_format('{pt}', 'yyyy-MM')
        group by bd_admin_user_id, create_date
    ) pos_trans_data on terminal_data.bd_admin_user_id = pos_trans_data.bd_admin_user_id and terminal_data.business_date = pos_trans_data.business_date
    -- pos distinct
    full join (
        select 
            bd_admin_user_id, 
            '{pt}' as business_date,
            count(distinct t0.originator_id) as pos_agent_cnt_m,
            count(distinct if(create_date='{pt}', t0.originator_id, null)) as pos_agent_cnt
        from (
            select
                bd_admin_user_id, originator_id,date_format(create_time, 'yyyy-MM-dd') as create_date, 
                row_number() over(partition by order_no order by update_time desc) rn
            from opay_dw.dwd_opay_pos_transaction_record_di
            where dt between date_format('{pt}', 'yyyy-MM-01') and '{pt}' and bd_agent_status = 1
        ) t0 where rn = 1 and date_format(create_date, 'yyyy-MM') = date_format('{pt}', 'yyyy-MM')
        group by bd_admin_user_id
    ) pos_distinct_data on pos_trans_data.bd_admin_user_id = pos_distinct_data.bd_admin_user_id 
        and pos_trans_data.business_date = pos_distinct_data.business_date
    '''.format(
        pt=ds,
        table=table_name,
        db=db_name
    )
    return HQL

##---- hive operator end ---##

def execution_data_task_id(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = dwm_opay_bd_agent_trans_df_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)



    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")

dwm_opay_bd_agent_trans_df_task = PythonOperator(
    task_id='dwm_opay_bd_agent_trans_df_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

dwd_opay_cico_record_di_task >> dwm_opay_bd_agent_trans_df_task
dwd_opay_bd_agent_change_log_di_task >> dwm_opay_bd_agent_trans_df_task
dwd_opay_pos_transaction_record_di_task >> dwm_opay_bd_agent_trans_df_task