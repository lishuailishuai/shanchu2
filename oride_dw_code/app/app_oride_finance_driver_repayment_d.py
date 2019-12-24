# -*- coding: utf-8 -*-
"""
平台司机数据2019-08-31
"""
import airflow
from airflow.operators.hive_operator import HiveOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.sensors.hive_partition_sensor import HivePartitionSensor
from utils.connection_helper import get_hive_cursor, get_db_conn
from datetime import datetime, timedelta
from airflow.sensors import UFileSensor
from airflow.operators.impala_plugin import ImpalaOperator
import re,sys
import logging
from utils.validate_metrics_utils import *
import time

args = {
    'owner': 'yangmingze',
    'start_date': datetime(2019, 8, 31),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG(
    'app_oride_finance_driver_repayment_d',
    schedule_interval="40 02 * * *",
    default_args=args
)


hive_db = 'oride_dw'
hive_table = 'dwd_oride_finance_driver_repayment_extend_df'

"""
##----------------------------------依赖数据源------------------------------##
"""

#依赖前一天数据是否存在
dwd_oride_finance_driver_repayment_extend_df_tesk = UFileSensor(
    task_id='dwd_oride_finance_driver_repayment_extend_df_tesk',
    filepath='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="oride/oride_dw/dwd_oride_finance_driver_repayment_extend_df/country_code=nal",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)

#依赖前一天数据是否存在
dwm_oride_driver_base_df_tesk = UFileSensor(
    task_id='dwm_oride_driver_base_df_tesk',
    filepath='{hdfs_path_str}/dt={pt}/_SUCCESS'.format(
        hdfs_path_str="oride/oride_dw/dwm_oride_driver_base_df/country_code=nal",
        pt='{{ds}}'
    ),
    bucket_name='opay-datalake',
    poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
    dag=dag
)


"""
##------------------------------------ end --------------------------------##
"""

mysql_table = 'oride_dw.app_oride_finance_driver_repayment_test_d'
#mysql_table = 'test_db.test_oride_finance_driver_repayment_test_d'


##------------------------------------ SQL --------------------------------##

# 从hive读取数据
def get_data_from_hive(ds,**op_kwargs):
    # ds = op_kwargs.get('ds', time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400)))
    hql = '''
        SELECT t1.dt as day, --日期
            NVL(t1.city_id, 0) as city_id, --城市
            NVL(city_name, '') as city_name, --城市名称
            NVL(t1.driver_id, 0) as driver_id, --司机Id
            NVL(regexp_replace(driver_name,'\\\\\\\\',''), '') as driver_name, --司机姓名
            NVL(regexp_replace(bphone_number,'\\\\\\\\',''), '') as driver_mobile, --司机手机号码
            NVL(t1.product_id, 0) as driver_type,--骑手类型：1 ORide-Green, 2 ORide-Street, 3 OTrike
            (CASE
                WHEN balance IS NULL THEN 0
                ELSE balance
            END) as balance, --余额
            (CASE
                WHEN repayment_all IS NULL THEN 0
                ELSE repayment_all
            END) as repayment_total_amount, --还款总额
            NVL(start_date, '') as start_date, --开始还款日期
            (CASE
                WHEN repayment_amount IS NULL THEN 0
                ELSE repayment_amount
            END) as repayment_amount, --每次还款金额
            NVL(numbers, 0) as total_numbers,  --分期总数
            0 AS effective_days, --有效天数：计算骑手正常还款的天数 
            NVL(overdue_payment_cnt, 0) as lose_numbers, --违约期数
            NVL(last_date, t1.dt) as last_back_time, -- 最后一次还款时间
            0 AS today_repayment, -- 今日是否还款：1已还款
            0 AS status, -- 状态
            nvl(driver_finish_order_cnt,0) AS order_numbers, -- 完成订单数量
            nvl(t3.order_agv,0) AS order_agv, -- 3日平均
            fault,
            plate_number, --车牌号
            register_time, -- 司机注册时间
            NVL(regexp_replace(driver_address,'\\\\\\\\',''), '') as driver_address, --司机地址（-1 未知）
            last_week_daily_due, --上周日均应还款金额
            
            --新增新逻辑
            nvl(t1.already_amount, 0 ) already_amount, --已还款金额
            nvl(t1.already_amount / t1.amount ,0) as already_repaid_numbers , --已还款期数
            nvl(if(t1.balance < 0,(t1.all_amount-t1.already_amount) / t1.amount,0),0) as conversion_overdue_days, --换算逾期天数
            nvl(t1.all_amount,0) as all_amount --总贷款金额
            
        FROM (SELECT 
                a.*, b.phone_number as bphone_number 
            FROM (select * FROM {hive_db}.{hive_table} WHERE dt = '{pt}') a 
            JOIN (select * from oride_dw.dim_oride_driver_base where dt='{pt}') b ON a.driver_id = b.driver_id
            ) t1
        
        LEFT OUTER JOIN
            
            (SELECT product_id,
                    city_id,
                    driver_id,
                    driver_finish_order_cnt
             FROM oride_dw.dwm_oride_driver_base_df
             WHERE dt = '{pt}'
             and city_id<>'999001' --去除测试数据
             and driver_id not in(3835,
             3963,
             3970,
             4702,
             5559,
             5902,
             7669,
             29105, --以上都是录错城市的司机
             10722, --测试数据
             1)    --北京城市测试数据
             ) t2 
        ON t1.driver_id=t2.driver_id
          AND t1.city_id=t2.city_id
          AND t1.product_id=t2.product_id
        LEFT OUTER JOIN --所有骑手的3日平均接单数
        (SELECT driver_id,
                ROUND(sum(driver_finish_order_cnt)/3) AS order_agv --3日平均完单数
        
         FROM oride_dw.dwm_oride_driver_base_df
         WHERE dt BETWEEN '{prev_3_day}' AND '{pt}'
           AND city_id<>'999001'
        GROUP BY driver_id) t3
        ON t1.driver_id=t3.driver_id

        group by t1.dt,
            NVL(t1.city_id, 0),
            NVL(city_name, ''),
            NVL(t1.driver_id, 0),
            NVL(regexp_replace(driver_name,'\\\\\\\\',''), ''),
            NVL(regexp_replace(bphone_number,'\\\\\\\\',''), ''),
            NVL(t1.product_id, 0),
            balance,
            repayment_all,
            NVL(start_date, ''),
            repayment_amount,
            NVL(numbers, 0),
            NVL(overdue_payment_cnt, 0),
            NVL(last_date, t1.dt),
            nvl(driver_finish_order_cnt,0),
            nvl(t3.order_agv,0),
            fault,
            plate_number,
            register_time,
            NVL(regexp_replace(driver_address,'\\\\\\\\',''), ''),
            last_week_daily_due,
            t1.already_amount,
            t1.all_amount,
            t1.amount
    '''.format(
        hive_db=hive_db,
        hive_table=hive_table,
        pt=ds,
        now_day=airflow.macros.ds_add(ds, +1),
        prev_3_day=airflow.macros.ds_add(ds, -2),
    )

    logging.info(hql)
    hive_cursor = get_hive_cursor()
    hive_cursor.execute(hql)
    hive_data = hive_cursor.fetchall()

    mysql_conn = get_db_conn('mysql_bi')
    mcursor = mysql_conn.cursor()


    __data_only_mysql(
        mcursor,
        "day='{pt}'".format(pt=ds)
        )

    __data_to_mysql(
        mcursor,
        hive_data,
        [
            'day', 'city_id', 'city_name', 'driver_id', 'driver_name', 'driver_mobile', 'driver_type',
            'balance', 'repayment_total_amount', 'start_date', 'repayment_amount', 'total_numbers',
            'effective_days', 'lose_numbers', 'last_back_time', 'today_repayment', 'status','order_numbers','order_agv','fault','plate_number','register_time','driver_address','last_week_daily_due','already_amount','already_repaid_numbers','conversion_overdue_days','all_amount'
        ],
        'day=VALUES(day)'
    )

    hive_cursor.close()
    mcursor.close()


# 数据集写入mysql前删除之前数据，保证数据唯一
def __data_only_mysql(conn, column):
    isql = 'delete from {table} {where_dt} ;'.format(
        table=mysql_table,
        where_dt='where'+' '+column
    )
    try:
        logging.info(isql)
        conn.execute(isql)
    except BaseException as e:
        logging.info(e)
        sys.exit(1)
        return


# 数据集写入mysql
def __data_to_mysql(conn, data, column, update=''):
    isql = 'insert into {table} ({columns})'.format(
        table=mysql_table,
        columns=','.join(column)
    )
    esql = '{0} values {1} on duplicate key update {2}'
    sval = ''
    cnt = 0
    try:
        for (day, city_id, city_name, driver_id, driver_name, driver_mobile, driver_type,
                balance, repayment_total_amount, start_date, repayment_amount, total_numbers,
                effective_days, lose_numbers, last_back_time, today_repayment, status,order_numbers,order_agv,fault,plate_number,register_time,driver_address,last_week_daily_due,already_amount,already_repaid_numbers,conversion_overdue_days,all_amount) in data:

            row = [
                day, city_id, city_name, driver_id, driver_name.replace("'", "\\'"), driver_mobile, driver_type,
                balance, repayment_total_amount, start_date, repayment_amount, total_numbers,
                effective_days, lose_numbers, last_back_time, today_repayment, status,order_numbers,order_agv,fault,plate_number,register_time,driver_address.replace("'", " "),last_week_daily_due,already_amount,already_repaid_numbers,conversion_overdue_days,all_amount
            ]
            if sval == '':
                sval = '(\'{}\')'.format('\',\''.join([str(x) for x in row]))
            else:
                sval += ',(\'{}\')'.format('\',\''.join([str(x) for x in row]))
            cnt += 1
            if cnt >= 1000:
                #logging.info(esql.format(isql, sval, update))
                conn.execute(esql.format(isql, sval, update))
                cnt = 0
                sval = ''

        if cnt > 0 and sval != '':
            conn.execute(esql.format(isql, sval, update))
    except BaseException as e:
        logging.info(e)
        sys.exit(1)
        return


get_data_from_hive_task = PythonOperator(
    task_id='get_data_from_hive_task',
    python_callable=get_data_from_hive,
    provide_context=True,
    dag=dag
)


dwd_oride_finance_driver_repayment_extend_df_tesk>>get_data_from_hive_task
dwm_oride_driver_base_df_tesk >> get_data_from_hive_task
