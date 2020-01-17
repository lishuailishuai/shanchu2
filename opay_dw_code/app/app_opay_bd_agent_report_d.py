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

dag = airflow.DAG('app_opay_bd_agent_report_d',
                  schedule_interval="00 03 * * *",
                  default_args=args
                  )

##----------------------------------------- 依赖 ---------------------------------------##
dwm_opay_bd_agent_cico_d_task = OssSensor(
    task_id='app_opay_bd_agent_cico_d_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwm_opay_bd_agent_cico_d/country_code=NG",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

dim_opay_bd_relation_df_task = OssSensor(
    task_id='dim_opay_bd_relation_df_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dim_opay_bd_relation_df/country_code=nal",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

ods_bd_admin_users_df_prev_day_task = OssSensor(
    task_id='ods_bd_admin_users_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay_dw_sqoop/opay_agent_crm/bd_admin_users",
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
table_name="app_opay_bd_agent_report_d"
hdfs_path="oss://opay-datalake/opay/opay_dw/"+table_name

##---- hive operator ---##
def app_opay_bd_agent_report_d_sql_task(ds):
    HQL='''
    
    set mapred.max.split.size=1000000;
    set hive.exec.dynamic.partition.mode=nonstrict;
    set hive.exec.parallel=true; --default false
    set hive.exec.parallel=true; --default false
    with 
        bd_data as (
            select 
                id as bd_admin_user_id, username as bd_admin_user_name, user_mobile as bd_admin_user_mobile,
                department_id as bd_admin_dept_id, job_id as bd_admin_job_id, leader_id as bd_admin_leader_id
            from opay_dw_ods.ods_sqoop_base_bd_admin_users_df 
            where dt = '{pt}' and job_id > 0
        ),
        bd_relation_data as (
            select 
                bd_admin_user_id, 
                nvl(job_bd_user_id, '-') as job_bd_user_id,
                nvl(job_bdm_user_id, '-') as job_bdm_user_id,
                nvl(job_rm_user_id, '-') as job_rm_user_id,
                nvl(job_cm_user_id, '-') as job_cm_user_id,
                nvl(job_hcm_user_id, '-') as job_hcm_user_id,
                nvl(job_pic_user_id, '-') as job_pic_user_id
            from opay_dw.dim_opay_bd_relation_df 
            where dt = '${pt}'
        ),
        cube_data as (
            select 
                nvl(t0.job_bd_user_id, 'ALL') as job_bd_user_id, 
                nvl(t0.job_bdm_user_id, 'ALL') as job_bdm_user_id, 
                nvl(t0.job_rm_user_id, 'ALL') as job_rm_user_id,
                nvl(t0.job_cm_user_id, 'ALL') as job_cm_user_id,
                nvl(t0.job_hcm_user_id, 'ALL') as job_hcm_user_id, 
                nvl(job_pic_user_id, 'ALL') as job_pic_user_id, 
                sum(audited_agent_cnt_his) as audited_agent_cnt_his, 
                sum(audited_agent_cnt_m) audited_agent_cnt_m, 
                sum(audited_agent_cnt) audited_agent_cnt,
                sum(rejected_agent_cnt_m) rejected_agent_cnt_m,
                sum(rejected_agent_cnt) rejected_agent_cnt,
                sum(ci_suc_order_cnt) ci_suc_order_cnt,
                sum(ci_suc_order_amt) ci_suc_order_amt,
                sum(ci_suc_order_cnt_m) ci_suc_order_cnt_m,
                sum(ci_suc_order_amt_m) ci_suc_order_amt_m,
                sum(co_suc_order_cnt) co_suc_order_cnt,
                sum(co_suc_order_amt) co_suc_order_amt,
                sum(co_suc_order_cnt_m) co_suc_order_cnt_m,
                sum(co_suc_order_amt_m) co_suc_order_amt_m
            from bd_relation_data t0 join (
                select
                    *
                from opay_dw.dwm_opay_bd_agent_cico_d
                where dt = '${pt}'
            ) t1 on t0.bd_admin_user_id = t1.bd_admin_user_id
            group by t0.job_bd_user_id, t0.job_bdm_user_id, t0.job_rm_user_id, t0.job_cm_user_id, t0.job_hcm_user_id, job_pic_user_id
            grouping sets(
                t0.job_bd_user_id, t0.job_bdm_user_id, t0.job_rm_user_id, 
                t0.job_cm_user_id, t0.job_hcm_user_id, job_pic_user_id
            )
        )
        insert overwrite table {db}.{table} partition(country_code='NG', dt='{pt}')
        select 
            bd.bd_admin_user_id, bd.bd_admin_user_name, bd.bd_admin_user_mobile, 
            bd.bd_admin_dept_id, bd.bd_admin_job_id, bd.bd_admin_leader_id,
            audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
            rejected_agent_cnt_m, rejected_agent_cnt,
            ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
            co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
        from (
            select 
                job_bd_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_bd_user_id != 'ALL' and job_bd_user_id != '-'
            union all
            select 
                job_bdm_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_bdm_user_id != 'ALL' and job_bdm_user_id != '-'
            union all
            select 
                job_rm_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_rm_user_id != 'ALL' and job_rm_user_id != '-'
            union all
             select 
                job_cm_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_cm_user_id != 'ALL' and job_cm_user_id != '-'
            union all
             select 
                job_hcm_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_hcm_user_id != 'ALL' and job_hcm_user_id != '-'
            union all
             select 
                job_pic_user_id as bd_admin_user_id, audited_agent_cnt_his, audited_agent_cnt_m, audited_agent_cnt,
                rejected_agent_cnt_m, rejected_agent_cnt,
                ci_suc_order_cnt, ci_suc_order_amt, ci_suc_order_cnt_m, ci_suc_order_amt_m,
                co_suc_order_cnt, co_suc_order_amt, co_suc_order_cnt_m, co_suc_order_amt_m
            from cube_data 
            where job_pic_user_id != 'ALL' and job_pic_user_id != '-'
        ) report 
        left join bd_data bd on report.bd_admin_user_id = bd.id 
        
       
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
    _sql = app_opay_bd_agent_report_d_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)



    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")

app_opay_bd_agent_report_d_task = PythonOperator(
    task_id='app_opay_bd_agent_report_d_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

dwm_opay_bd_agent_cico_d_task >> app_opay_bd_agent_report_d_task
ods_bd_admin_users_df_prev_day_task >> app_opay_bd_agent_report_d_task
dim_opay_bd_relation_df_task >> app_opay_bd_agent_report_d_task