# -*- coding: utf-8 -*-
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
from airflow.sensors.s3_key_sensor import S3KeySensor
import json
import logging
from airflow.models import Variable
import requests
import os
from airflow.hooks.hive_hooks import HiveCliHook
from plugins.TaskTouchzSuccess import TaskTouchzSuccess
from airflow.operators.python_operator import PythonOperator
from airflow.sensors import OssSensor

args = {
    'owner': 'lishuai',
    'start_date': datetime(2019, 10, 30),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=2),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG('app_oride_cohort_m',
                  schedule_interval="00 02 1 * *",
                  default_args=args,
                  )



##----------------------------------------- 依赖 ---------------------------------------##

#获取变量
code_map=eval(Variable.get("sys_flag"))

#判断ufile(cdh环境)
if code_map["id"].lower()=="ufile":
    dwm_oride_order_base_di_task = UFileSensor(
        task_id='dwm_oride_order_base_di_task',
        filepath='{hdfs_path_str}/country_code=nal/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_order_base_di",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )

    dwm_oride_passenger_base_df_task = UFileSensor(
        task_id='dwm_oride_passenger_base_df_task',
        filepath='{hdfs_path_str}/country_code=nal/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_passenger_base_df",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )

    dwm_oride_driver_base_df_task = UFileSensor(
        task_id='dwm_oride_driver_base_df_task',
        filepath='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_driver_base_df",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )
    dwm_oride_passenger_act_m_task = UFileSensor(
        task_id='dwm_oride_passenger_act_m_task',
        filepath='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_passenger_act_m",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )
    dwm_oride_driver_act_m_task = UFileSensor(
        task_id='dwm_oride_driver_act_m_task',
        filepath='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_driver_act_m",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )
##----------------------------------------- 变量 ---------------------------------------##
    def get_table_info(i):
        table_names = ['app_oride_new_user_cohort_m',
                       'app_oride_new_driver_cohort_m',
                       'app_oride_act_user_cohort_m',
                       'app_oride_act_driver_cohort_m']
        hdfs_paths = "ufile://opay-datalake/oride/oride_dw/"
        return table_names[i], hdfs_paths + table_names[i]

else:
    print("成功")

    dwm_oride_order_base_di_task = OssSensor(
        task_id='dwm_oride_order_base_di_task',
        bucket_key='{hdfs_path_str}/country_code=nal/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_order_base_di",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )

    dwm_oride_passenger_base_df_task = OssSensor(
        task_id='dwm_oride_passenger_base_df_task',
        bucket_key='{hdfs_path_str}/country_code=nal/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_passenger_base_df",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )

    dwm_oride_driver_base_df_task = OssSensor(
        task_id='dwm_oride_driver_base_df_task',
        bucket_key='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_driver_base_df",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )
    dwm_oride_passenger_act_m_task = OssSensor(
        task_id='dwm_oride_passenger_act_m_task',
        bucket_key='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_passenger_act_m",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )
    dwm_oride_driver_act_m_task = OssSensor(
        task_id='dwm_oride_driver_act_m_task',
        bucket_key='{hdfs_path_str}/country_code=NG/dt={pt}/_SUCCESS'.format(
            hdfs_path_str="oride/oride_dw/dwm_oride_driver_act_m",
            pt='{{ds}}'
        ),
        bucket_name='opay-datalake',
        poke_interval=60,
        dag=dag
    )


##----------------------------------------- 变量 ---------------------------------------##
    def get_table_info(i):
        table_names = ['app_oride_new_user_cohort_m',
                       'app_oride_new_driver_cohort_m',
                       'app_oride_act_user_cohort_m',
                       'app_oride_act_driver_cohort_m']
        hdfs_paths = "oss://opay-datalake/oride/oride_dw/"
        return table_names[i], hdfs_paths + table_names[i]

##----------------------------------------- 脚本 ---------------------------------------##

def app_oride_new_user_cohort_m_sql_task(ds):

    HQL='''set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;
    -- set hive.merge.mapredfiles=true;
    INSERT overwrite TABLE oride_dw.{table} partition(country_code,dt)
        --乘客新客留存数据统计【上线后的统计，上线后用每月的数据关联历史所有月的乘客新客数据】
        
        select nvl(month_create_date,-10000) as month_create_date,
            nvl(m.months,-10000) as months,
            nvl(m.city_id,-10000) as city_id,
            nvl(product_id,-10000) as product_id,
            new_user_liucun_cnt, --第一月对应的就是新客
            new_user_liucun_ord_cnt, --新客留存完单量
            new_user_liucun_gmv, --新客留存完单gmv
            new_user_liucun_dis, --新客留存完单里程
            'nal' as country_code,
            '{pt}' as dt
        from (
            select nvl(a.month_create_date,-10000) as month_create_date,
                nvl(
                    if(a.month_create_date<new_user.month_create_date,
                        a.month_create_date-new_user.month_create_date+12,
                        a.month_create_date-new_user.month_create_date)
                ,-10000) as months,
                nvl(a.city_id,-10000) as city_id,
                nvl(a.product_id,-10000) as product_id,
                count(distinct (nvl(new_user.passenger_id,null))) as new_user_liucun_cnt,  --第一月对应的就是新客
                count(if(new_user.passenger_id is not null,a.order_id,null)) as new_user_liucun_ord_cnt, --新客留存完单量
                sum(if(new_user.passenger_id is not null,a.price,0)) as new_user_liucun_gmv, --新客留存完单gmv
                sum(if(new_user.passenger_id is not null,a.distance,0)) as new_user_liucun_dis --新客留存完单里程     
        
            from (
                select passenger_id,city_id,
                    driver_serv_type as product_id,
                    order_id,price,
                    order_onride_distance as distance,
                    month(dt) as month_create_date
                from oride_dw.dwm_oride_order_base_di
                where substr('{pt}',1,7)=substr(dt,1,7)
                and is_finish=1 and city_id<>999001 and driver_id<>1
            )as a
            left join
            (
                select first_finish_city_id as city_id,
                    first_finish_product_id as product_id,
                    passenger_id,
                    month(first_finish_create_date) as month_create_date
                from oride_dw.dwm_oride_passenger_base_df
                where dt=date_sub(add_months('{pt}',1),1)
                and first_finish_ord_id is not null
                and months_between(date_sub(add_months('{pt}',1),1),first_finish_create_date)<=6
                and months_between(date_sub(add_months('{pt}',1),1),first_finish_create_date)>=0
            ) new_user
            on a.city_id=new_user.city_id
            and a.product_id=new_user.product_id
            and a.passenger_id=new_user.passenger_id
        
            group by nvl(a.month_create_date,-10000),
            nvl(
                if(a.month_create_date<new_user.month_create_date,
                    a.month_create_date-new_user.month_create_date+12,
                    a.month_create_date-new_user.month_create_date
                )
            ,-10000),
            nvl(a.city_id,-10000),
            nvl(a.product_id,-10000)
            with cube
        ) m
        where !(nvl(m.month_create_date,-10000)=-10000 or nvl(m.months,-10000)=-10000); 

                 '''.format(
        pt=ds,
        table=get_table_info(0)[0]
    )
    return HQL

def app_oride_new_driver_cohort_m_sql_task(ds):

    HQL='''set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;
    -- set hive.merge.mapredfiles=true;
    INSERT overwrite TABLE oride_dw.{table} partition(country_code,dt)
        --司机新客留存数据统计【上线后的统计，上线后用每月的数据关联历史所有月的司机新客数据,但是由于每天有些订单并不是终态数据，因此每次都需要重新判定新客和活跃】
        
        select nvl(m.month_create_date,-10000) as month_create_date,
            nvl(m.months,-10000) as months,
            nvl(m.city_id,-10000) as city_id,
            nvl(m.product_id,-10000) as product_id,
            new_driver_liucun_cnt,  --第一月对应的就是新客
            new_driver_liucun_ord_cnt, --新客留存完单量
            new_driver_liucun_gmv, --新客留存完单gmv
            new_driver_liucun_dis, --新客留存完单里程
            'nal' as country_code,
            '{pt}' as dt
        from (
            select nvl(a.month_create_date,-10000) as month_create_date,
                nvl(
                    if(a.month_create_date<new_driver.month_create_date,
                        a.month_create_date-new_driver.month_create_date+12,
                        a.month_create_date-new_driver.month_create_date
                    )
                ,-10000) as months,
                nvl(a.city_id,-10000) as city_id,
                nvl(a.product_id,-10000) as product_id,
                count(distinct (nvl(new_driver.driver_id,null))) as new_driver_liucun_cnt,  --第一月对应的就是新客
                count(if(new_driver.driver_id is not null,a.order_id,null)) as new_driver_liucun_ord_cnt, --新客留存完单量
                sum(if(new_driver.driver_id is not null,a.price,0)) as new_driver_liucun_gmv, --新客留存完单gmv
                sum(if(new_driver.driver_id is not null,a.distance,0)) as new_driver_liucun_dis --新客留存完单里程
        
            from(
                select driver_id,city_id,
                    driver_serv_type as product_id,
                    price,order_id,
                    order_onride_distance as distance,
                    month(dt) as month_create_date
                from oride_dw.dwm_oride_order_base_di
                where substr('{pt}',1,7)=substr(dt,1,7)
                and is_finish=1 and city_id<>999001 and driver_id<>1
            )as a
            left join
            (
                select city_id,product_id,driver_id,
                    month(from_unixtime(first_finish_order_create_time,'yyyy-MM-dd')) as month_create_date
                from oride_dw.dwm_oride_driver_base_df
                where dt=date_sub(add_months('{pt}',1),1)
                and first_finish_order_id is not null
                and months_between(date_sub(add_months('{pt}',1),1),from_unixtime(first_finish_order_create_time,'yyyy-MM-dd'))<=6
                and months_between(date_sub(add_months('{pt}',1),1),from_unixtime(first_finish_order_create_time,'yyyy-MM-dd'))>=0
            ) new_driver
            on a.city_id=new_driver.city_id
            and a.product_id=new_driver.product_id
            and a.driver_id=new_driver.driver_id
            
            group by nvl(a.month_create_date,-10000),
            nvl(
                if(a.month_create_date<new_driver.month_create_date,
                    a.month_create_date-new_driver.month_create_date+12,
                    a.month_create_date-new_driver.month_create_date
                )
            ,-10000),
            nvl(a.city_id,-10000),
            nvl(a.product_id,-10000)
            with cube
        ) m
        where !(nvl(m.month_create_date,-10000)=-10000 or nvl(m.months,-10000)=-10000);
                 '''.format(
        pt=ds,
        table=get_table_info(1)[0]
    )
    return HQL

def app_oride_act_user_cohort_m_sql_task(ds):

    HQL='''set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;
    -- set hive.merge.mapredfiles=true;
    INSERT overwrite TABLE oride_dw.{table} partition(country_code,dt)
        --活跃乘客留存数据统计【上线后的统计，上线后用每月的数据关联历史所有月的活跃乘客数据】
        
         select nvl(m.month_create_date,-10000) as month_create_date,
            nvl(m.months,-10000) as months,
            nvl(m.city_id,-10000) as city_id,
            nvl(m.product_id,-10000) as product_id,
            act_user_liucun_cnt,  --第一月对应的就是活跃乘客数
            act_user_liucun_ord_cnt, --活跃乘客留存完单量
            act_user_liucun_gmv, --活跃乘客留存完单gmv
            act_user_liucun_dis, --活跃乘客留存完单里程
            'nal' as country_code,
            '{pt}' as dt
        from(
            select nvl(a.month_create_date,-10000) as month_create_date,
            nvl(
                if(a.month_create_date<act_user.month_create_date,
                    a.month_create_date-act_user.month_create_date+12,
                    a.month_create_date-act_user.month_create_date
                )
            ,-10000) as months,
            nvl(a.city_id,-10000) as city_id,
            nvl(a.product_id,-10000) as product_id,
            count(distinct act_user.passenger_id) as act_user_liucun_cnt,  --第一月对应的就是活跃乘客数
            count(if(act_user.passenger_id is not null,a.order_id,null)) as act_user_liucun_ord_cnt, --活跃乘客留存完单量
            sum(if(act_user.passenger_id is not null,a.price,0)) as act_user_liucun_gmv, --活跃乘客留存完单gmv
            sum(if(act_user.passenger_id is not null,a.distance,0)) as act_user_liucun_dis --活跃乘客留存完单里程
        
            from (
                select passenger_id,
                    city_id,
                    driver_serv_type as product_id,
                    order_id,price,
                    order_onride_distance as distance,
                    month(dt) as month_create_date
                from oride_dw.dwm_oride_order_base_di
                where substr('{pt}',1,7)=substr(dt,1,7)
                and is_finish=1 and city_id<>999001 and driver_id<>1
            )as a
            left join
            (
                select month as month_create_date,
                    city_id,product_id,passenger_id 
                from oride_dw.dwm_oride_passenger_act_m 
                where month('{pt}')-month<=6 and month('{pt}')-month>=0
                group by month,city_id,product_id,passenger_id
            )as act_user
            on a.city_id=act_user.city_id
            and a.product_id=act_user.product_id
            and a.passenger_id=act_user.passenger_id
            where a.month_create_date>=act_user.month_create_date
            group by nvl(a.month_create_date,-10000),
            nvl(
                if(a.month_create_date<act_user.month_create_date,
                    a.month_create_date-act_user.month_create_date+12,
                    a.month_create_date-act_user.month_create_date
                )
            ,-10000),
            nvl(a.city_id,-10000),
            nvl(a.product_id,-10000)
            with cube
        ) m
        where !(nvl(m.month_create_date,-10000)=-10000 or nvl(m.months,-10000)=-10000); 
        
                 '''.format(
        pt=ds,
        table=get_table_info(2)[0]
    )
    return HQL

def app_oride_act_driver_cohort_m_sql_task(ds):

    HQL='''set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;
    -- set hive.merge.mapredfiles=true;
    INSERT overwrite TABLE oride_dw.{table} partition(country_code,dt)
        --活跃司机留存数据统计【上线后的统计，上线后用每月的数据关联历史所有月的活跃司机数据】
        
        select nvl(m.month_create_date,-10000) as month_create_date,
            nvl(m.months,-10000) as months,
            nvl(m.city_id,-10000) as city_id,
            nvl(m.product_id,-10000) as product_id,
            act_driver_liucun_cnt,  --第一月对应的就是活跃司机数
            act_driver_liucun_ord_cnt, --活跃司机留存完单量
            act_driver_liucun_gmv, --活跃司机留存完单gmv
            act_driver_liucun_dis, --活跃司机留存完单里程
            'nal' as country_code,
            '{pt}' as dt
        
        from(
            select nvl(a.month_create_date,-10000) as month_create_date,
                nvl(
                    if(a.month_create_date<act_driver.month_create_date,
                        a.month_create_date-act_driver.month_create_date+12,
                        a.month_create_date-act_driver.month_create_date
                    )
                ,-10000) as months,
                nvl(a.city_id,-10000) as city_id,
                nvl(a.product_id,-10000) as product_id,
                count(distinct act_driver.driver_id) as act_driver_liucun_cnt,  --第一月对应的就是活跃司机数
                count(if(act_driver.driver_id is not null,a.order_id,null)) as act_driver_liucun_ord_cnt, --活跃司机留存完单量
                sum(if(act_driver.driver_id is not null,a.price,0)) as act_driver_liucun_gmv, --活跃司机留存完单gmv
                sum(if(act_driver.driver_id is not null,a.distance,0)) as act_driver_liucun_dis --活跃司机留存完单里程
        
            from (
                select driver_id,
                    city_id,
                    driver_serv_type as product_id,
                    order_id,price,
                    order_onride_distance as distance,
                    month(dt) as month_create_date
                from oride_dw.dwm_oride_order_base_di
                where substr('{pt}',1,7)=substr(dt,1,7)
                and is_finish=1 and city_id<>999001 and driver_id<>1
            )as a
            left join
            (
                select month as month_create_date,
                    city_id,product_id,driver_id 
                from oride_dw.dwm_oride_driver_act_m
                where month('{pt}')-month<=6 and month('{pt}')-month>=0
                group by month,city_id,product_id,driver_id
            ) act_driver
            on a.city_id=act_driver.city_id
            and a.product_id=act_driver.product_id
            and a.driver_id=act_driver.driver_id
            where a.month_create_date>=act_driver.month_create_date
            group by nvl(a.month_create_date,-10000),
            nvl(
                if(a.month_create_date<act_driver.month_create_date,
                    a.month_create_date-act_driver.month_create_date+12,
                    a.month_create_date-act_driver.month_create_date
                )
            ,-10000),
            nvl(a.city_id,-10000),
            nvl(a.product_id,-10000)
            with cube
        ) m
        where !(nvl(m.month_create_date,-10000)=-10000 or nvl(m.months,-10000)=-10000);
         
                 '''.format(
        pt=ds,
        table=get_table_info(3)[0]
    )
    return HQL

# 主流程
def execution_new_user_task(ds, **kargs):
    hive_hook = HiveCliHook()

    #读取sql
    _sql = app_oride_new_user_cohort_m_sql_task(ds)

    logging.info('Executing: %s', _sql)

    #执行hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """

    hdfs_path = get_table_info(0)[1]
    TaskTouchzSuccess().countries_touchz_success(ds, "oride_dw", get_table_info(0)[0], hdfs_path, "true", "true")

def execution_new_driver_task(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = app_oride_new_driver_cohort_m_sql_task(ds)

    # 执行hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    hdfs_path = get_table_info(1)[1]
    TaskTouchzSuccess().countries_touchz_success(ds, "oride_dw", get_table_info(1)[0], hdfs_path, "true", "true")

def execution_act_user_task(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = app_oride_act_user_cohort_m_sql_task(ds)

    # 执行hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    hdfs_path = get_table_info(2)[1]
    TaskTouchzSuccess().countries_touchz_success(ds, "oride_dw", get_table_info(2)[0], hdfs_path, "true", "true")

def execution_act_driver_task(ds, **kargs):
    hive_hook = HiveCliHook()

    # 读取sql
    _sql = app_oride_act_driver_cohort_m_sql_task(ds)

    # 执行hive
    hive_hook.run_cli(_sql)

    # 生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    hdfs_path = get_table_info(3)[1]
    TaskTouchzSuccess().countries_touchz_success(ds, "oride_dw", get_table_info(3)[0], hdfs_path, "true", "true")


app_oride_new_user_cohort_m_task = PythonOperator(
    task_id='app_oride_new_user_cohort_m_task',
    python_callable=execution_new_user_task,
    provide_context=True,
    dag=dag
)

app_oride_new_driver_cohort_m_task = PythonOperator(
    task_id='app_oride_new_driver_cohort_m_task',
    python_callable=execution_new_driver_task,
    provide_context=True,
    dag=dag
)

app_oride_act_user_cohort_m_task = PythonOperator(
    task_id='app_oride_act_user_cohort_m_task',
    python_callable=execution_act_user_task,
    provide_context=True,
    dag=dag
)

app_oride_act_driver_cohort_m_task = PythonOperator(
    task_id='app_oride_act_driver_cohort_m_task',
    python_callable=execution_act_driver_task,
    provide_context=True,
    dag=dag
)


dwm_oride_order_base_di_task>>app_oride_new_user_cohort_m_task
dwm_oride_passenger_base_df_task>>app_oride_new_user_cohort_m_task

dwm_oride_order_base_di_task>>app_oride_new_driver_cohort_m_task
dwm_oride_driver_base_df_task>>app_oride_new_driver_cohort_m_task

dwm_oride_order_base_di_task>>app_oride_act_user_cohort_m_task
dwm_oride_passenger_act_m_task>>app_oride_act_user_cohort_m_task

dwm_oride_order_base_di_task>>app_oride_act_driver_cohort_m_task
dwm_oride_driver_act_m_task>>app_oride_act_driver_cohort_m_task