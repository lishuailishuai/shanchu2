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
    'start_date': datetime(2020, 1, 13),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('dim_opay_bd_admin_user_df',
                  schedule_interval="00 01 * * *",
                  default_args=args
                  )

##----------------------------------------- 依赖 ---------------------------------------##

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
table_name="dim_opay_bd_admin_user_df"
hdfs_path="oss://opay-datalake/opay/opay_dw/"+table_name
config = eval(Variable.get("opay_time_zone_config"))

##---- hive operator ---##
def dim_opay_bd_admin_user_df_sql_task(ds):
    HQL='''
    
    set mapred.max.split.size=1000000;
    set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;
    insert overwrite table {db}.{table} partition (country_code = 'NG', dt = '{pt}')
    select
        id as bd_admin_user_id, username as bd_admin_user_name, mobile as bd_admin_mobile,
        job_id as bd_admin_job_id, leader_id as bd_admin_leader_id, opay_user,
        staff_code, name, password, department_id, email, status, remember_token, avatar,
        fcm_token, create_user_id as bd_admin_create_user_id, update_user_id as bd_admin_update_user_id,
        default.localTime("{config}", 'NG', created_at, 0) as create_time,
        default.localTime("{config}", 'NG', updated_at, 0) as update_time
    from opay_dw_ods.ods_sqoop_base_bd_admin_users_df
    where dt = '{pt}' AND created_at < '{pt} 23:00:00'
    '''.format(
        pt=ds,
        table=table_name,
        db=db_name,
        config=config
    )
    return HQL

##---- hive operator end ---##

def execution_data_task_id(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = dim_opay_bd_admin_user_df_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)



    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")

dim_opay_bd_admin_user_df_task = PythonOperator(
    task_id='dim_opay_bd_admin_user_df_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

ods_bd_admin_users_df_prev_day_task >> dim_opay_bd_admin_user_df_task