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
    'start_date': datetime(2019, 12, 1),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('dwm_opay_user_first_trans_repurchase_di',
                  schedule_interval="50 01 * * *",
                  default_args=args
                  )

##----------------------------------------- 依赖 ---------------------------------------##

dwd_opay_user_transaction_record_di_prev_day_task = OssSensor(
    task_id='dwd_opay_user_transaction_record_di_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwd_opay_user_transaction_record_di/country_code=NG",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)


dwm_opay_user_first_trans_df_prev_day_task = OssSensor(
    task_id='dwm_opay_user_first_trans_df_prev_day_task',
    bucket_key='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="opay/opay_dw/dwm_opay_user_first_trans_df/country_code=NG",
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
table_name = "dwm_opay_user_first_trans_repurchase_di"
hdfs_path = "oss://opay-datalake/opay/opay_dw/" + table_name


##---- hive operator ---##
def dwm_opay_user_first_trans_repurchase_di_sql_task(ds):
    HQL = '''
    
    set mapred.max.split.size=1000000;
    set hive.exec.dynamic.partition.mode=nonstrict;
    set hive.exec.parallel=true; --default false

    insert overwrite table {db}.{table} partition(country_code, dt)
    select 
	    t1.sub_consume_scenario, t1.originator_id, order_cnt, order_amt, 
	    if(t2.first_trans_amount >= 10000, 'y', 'n') if_first_trans_over_10000, first_trans_date, first_sub_consume_scenario, first_trans_amount,
	    datediff('{pt}', t2.first_trans_date) gap_day,
	    t1.country_code, t1.dt
	from (
	    select 
	        sub_consume_scenario, user_id as originator_id, sum(amount) as order_amt, count(*) order_cnt, country_code, '{pt}' as dt
	    from opay_dw.dwd_opay_user_transaction_record_di
	    where dt = '{pt}' and order_status = 'SUCCESS'
	    group by sub_consume_scenario, user_id, country_code
	) t1 join (
	    select 
	        sub_consume_scenario as first_sub_consume_scenario, user_id as originator_id, amount as first_trans_amount, date_format(trans_time, 'yyyy-MM-dd') as first_trans_date
	    from opay_dw.dwm_opay_user_first_trans_df
	    where dt = if('{pt}' <= '2020-03-18', '2020-03-18', '{pt}')
	) t2 on t1.originator_id = t2.originator_id
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
    _sql = dwm_opay_user_first_trans_repurchase_di_sql_task(ds)

    logging.info('Executing: %s', _sql)

    # 执行Hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds, db_name, table_name, hdfs_path, "true", "true")


dwm_opay_user_first_trans_repurchase_di_task = PythonOperator(
    task_id='dwm_opay_user_first_trans_repurchase_di_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)

dwm_opay_user_first_trans_df_prev_day_task >> dwm_opay_user_first_trans_repurchase_di_task
dwd_opay_user_transaction_record_di_prev_day_task >> dwm_opay_user_first_trans_repurchase_di_task