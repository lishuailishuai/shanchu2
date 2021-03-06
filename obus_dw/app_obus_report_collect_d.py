# -*- coding: utf-8 -*-
"""
obus 汇总/分城市
"""
import airflow
from airflow.operators.python_operator import PythonOperator
from airflow.operators.impala_plugin import ImpalaOperator
from datetime import datetime, timedelta
import time
from utils.connection_helper import get_hive_cursor, get_db_conn, get_db_conf
from utils.validate_metrics_utils import *
from airflow.sensors.s3_key_sensor import S3KeySensor
from airflow.operators.bash_operator import BashOperator
from airflow.sensors import OssSensor
import logging


args = {
    'owner': 'wuduo',
    'start_date': datetime(2019, 8, 25),
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'email': ['bigdata_dw@opay-inc.com'],
    'email_on_failure': True,
    'email_on_retry': False,
}

dag = airflow.DAG(
    'app_obus_report_collect_d',
    schedule_interval="00 09 * * *",
    concurrency=5,
    max_active_runs=1,
    default_args=args
)

"""
依赖采集完成
"""
#等待采集dag全部任务完成
dependence_ods_sqoop_data_driver_df = OssSensor(
    task_id='dependence_ods_sqoop_data_driver_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_driver_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_conf_cycle_df = OssSensor(
    task_id='dependence_ods_sqoop_conf_cycle_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_conf_cycle_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_data_order_df = OssSensor(
    task_id='dependence_ods_sqoop_data_order_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_order_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_conf_station_df = OssSensor(
    task_id='dependence_ods_sqoop_conf_station_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_conf_station_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_data_order_payment_df = OssSensor(
    task_id='dependence_ods_sqoop_data_order_payment_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_order_payment_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_data_user_recharge_df = OssSensor(
    task_id='dependence_ods_sqoop_data_user_recharge_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_user_recharge_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_data_user_df = OssSensor(
    task_id='dependence_ods_sqoop_data_user_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_user_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

dependence_ods_sqoop_data_ticket_df = OssSensor(
    task_id='dependence_ods_sqoop_data_ticket_df',
    bucket_key='obus_dw_sqoop/ods_sqoop_data_ticket_df/country_code=nal/dt={pt}/_SUCCESS'.format(pt='{{ ds }}'),
    bucket_name='opay-datalake',
    dag=dag
)

"""
end
"""


def get_data_from_impala(**op_kwargs):
    ds = op_kwargs.get('ds', time.strftime('%Y-%m-%d', time.localtime(time.time()-86400)))
    sql = '''
        WITH
        --分城市 
        cycle_data as 
        (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                cy.city_id,
                count(distinct cy.id) as total_lines,                                           --总线路数
                count(distinct dr.id) as total_drivers,                                         --线路总司机数
                count(distinct if(serv_mode='1', dr.id, null)) as serv_drivers,                 --线路上司机数量
                count(distinct if(serv_mode='0', dr.id, null)) as no_serv_drivers               --线路下司机数量
            from (select 
                    cycle_id, 
                    id, 
                    serv_mode 
                from obus_dw_ods.ods_sqoop_data_driver_df 
                where dt='{pt}' and 
                    from_unixtime(login_time, 'yyyy-MM-dd') = '{pt}'
                ) as dr
            inner join (select 
                    id,
                    city_id
                from obus_dw_ods.ods_sqoop_conf_cycle_df 
                where dt='2019-08-17' and 
                    status = '0'
                ) as cy 
            on dr.cycle_id = cy.id 
            group by cy.city_id
        ),
        --不分城市
        cycle_data_all as 
        (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(distinct cy.id) as total_lines,                                           --总线路数
                count(distinct dr.id) as total_drivers,                                         --线路总司机数
                count(distinct if(serv_mode=1, dr.id, null)) as serv_drivers,                 --线路上司机数量
                count(distinct if(serv_mode=0, dr.id, null)) as no_serv_drivers               --线路下司机数量
            from (select 
                    cycle_id, 
                    id, 
                    serv_mode 
                from obus_dw_ods.ods_sqoop_data_driver_df 
                where dt='{pt}' and 
                    from_unixtime(login_time, 'yyyy-MM-dd') = '{pt}'
                ) as dr
            inner join (select 
                    id,
                    city_id
                from obus_dw_ods.ods_sqoop_conf_cycle_df 
                where dt='2019-08-17' and 
                    status = 0
                ) as cy 
            on dr.cycle_id = cy.id 
        ),
        --分城市
        order_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                city_id,
                count(1) as line_orders,                                                                --线路总下单数
                sum(if(status in (1,2), 1, 0)) as line_finished_orders,                                  --线路总完单数
                sum(if(status in (1,2), price, 0)) as line_gmv                                          --线路收益
            from obus_dw_ods.ods_sqoop_data_order_df 
            where dt='{pt}' and 
                from_unixtime(cast(create_time as bigint), 'yyyy-MM-dd') = '{pt}'
            group by city_id
        ),
        --不分城市
        order_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(1) as line_orders,
                sum(if(status in (1,2), 1, 0)) as line_finished_orders,
                sum(if(status in (1,2), price, 0)) as line_gmv
            from obus_dw_ods.ods_sqoop_data_order_df 
            where dt='{pt}' and 
                from_unixtime(cast(create_time as bigint), 'yyyy-MM-dd') = '{pt}'
        ),
        --分城市
        station_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                city_id,
                count(distinct id) as total_stations                                                          --总站点数
            from obus_dw_ods.ods_sqoop_conf_station_df 
            where dt='{pt}' 
            group by city_id
        ),
        --不分城市
        station_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(distinct id) as total_stations
            from obus_dw_ods.ods_sqoop_conf_station_df 
            where dt='{pt}' 
        ),
        --分城市
        users_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                city_id,
                count(1) as users                                                                           --新用户数量
            from (select 
                    city_id,
                    user_id,
                    create_time,
                    row_number() over(partition by user_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    user_id > 0
                ) as t
            where from_unixtime(t.create_time, 'yyyy-MM-dd')='{pt}' and 
                orders=1 
            group by t.city_id
        ),
        --不分城市
        users_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(1) as users                                                                           --新用户数量
            from (select 
                    city_id,
                    user_id,
                    create_time,
                    row_number() over(partition by user_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    user_id > 0
                ) as t
            where from_unixtime(t.create_time, 'yyyy-MM-dd')='{pt}' and 
                orders=1 
        ),
        --分城市
        app_users_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                do.city_id,
                sum(if(dp.mode=1 and do.orders=1, 1, 0)) as obusapp_new_users,                                              ---ObusAPP新用户数量
                count(distinct if(dp.mode=1, do.user_id, null)) as money_ballet_users                                       --今日钱包使用人数
            from (select 
                    id,
                    city_id,
                    create_time,
                    user_id,
                    row_number() over(partition by user_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    user_id > 0
                ) as do 
            join (select 
                    id,
                    mode
                from obus_dw_ods.ods_sqoop_data_order_payment_df 
                where dt='{pt}' and 
                    from_unixtime(create_time, 'yyyy-MM-dd')='{pt}'
                ) as dp 
            on do.id = dp.id 
            where from_unixtime(do.create_time, 'yyyy-MM-dd') = '{pt}'
            group by do.city_id 
        ),
        --不分城市
        app_users_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                sum(if(dp.mode=1 and do.orders=1, 1, 0)) as obusapp_new_users,                                              ---ObusAPP新用户数量
                count(distinct if(dp.mode=1, do.user_id, null)) as money_ballet_users                                       --今日钱包使用人数
            from (select 
                    id,
                    city_id,
                    create_time,
                    user_id,
                    row_number() over(partition by user_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    user_id > 0
                ) as do 
            join (select 
                    id,
                    mode
                from obus_dw_ods.ods_sqoop_data_order_payment_df 
                where dt='{pt}' and 
                    from_unixtime(create_time, 'yyyy-MM-dd')='{pt}'
                ) as dp 
            on do.id = dp.id 
            where from_unixtime(do.create_time, 'yyyy-MM-dd') = '{pt}'
        ),
        --分城市
        app_ticket_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                do.city_id,
                sum(if(dp.mode=2 and do.orders=1, 1, 0)) as ticket_new_users                                                 ---首次使用公交卡新用户数量
            from (select 
                    id,
                    city_id,
                    create_time,
                    ticket_id,
                    row_number() over(partition by ticket_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    ticket_id > 0
                ) as do 
            join (select 
                    id,
                    ticket_id,
                    mode
                from obus_dw_ods.ods_sqoop_data_order_payment_df 
                where dt='{pt}' and 
                    from_unixtime(create_time, 'yyyy-MM-dd')='{pt}'
                ) as dp 
            on do.id = dp.id and do.ticket_id = dp.ticket_id 
            where from_unixtime(do.create_time, 'yyyy-MM-dd') = '{pt}'
            group by do.city_id 
        ),
        --不分城市
        app_ticket_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                sum(if(dp.mode=2 and do.orders=1, 1, 0)) as ticket_new_users                                                ---首次使用公交卡新用户数量
            from (select 
                    id,
                    city_id,
                    create_time,
                    ticket_id,
                    row_number() over(partition by ticket_id order by arrive_time) orders
                from obus_dw_ods.ods_sqoop_data_order_df 
                where dt='{pt}' and 
                    status in (1,2) and 
                    ticket_id > 0
                ) as do 
            join (select 
                    id,
                    ticket_id,
                    mode
                from obus_dw_ods.ods_sqoop_data_order_payment_df 
                where dt='{pt}' and 
                    from_unixtime(create_time, 'yyyy-MM-dd')='{pt}'
                ) as dp 
            on do.id = dp.id and do.ticket_id = dp.ticket_id 
            where from_unixtime(do.create_time, 'yyyy-MM-dd') = '{pt}'
        ),
        --分城市
        recharge_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                du.city_id,
                count(distinct if(rc.status=1 and from_unixtime(rc.create_time,'yyyy-MM-dd')='{pt}', rc.user_id, null)) as recharge_users,              --用户钱包充值人数
                count(distinct rc.user_id) as online_uv,                                                                                                --用户钱包总数量=线上uv
                sum(if(rc.status=1 and rc.recharge=1 and from_unixtime(rc.create_time,'yyyy-MM-dd')='{pt}', 1, 0)) as money_ballet_recharge_users       --今日钱包新充值人数
            from (select 
                    user_id,
                    status,
                    create_time, 
                    row_number() over(partition by user_id order by create_time) recharge
                from obus_dw_ods.ods_sqoop_data_user_recharge_df 
                where dt='{pt}' and 
                    user_id > 0
                ) as rc 
            join (select 
                    city_id,
                    id 
                from obus_dw_ods.ods_sqoop_data_user_df 
                where dt='{pt}'
                ) as du 
            on rc.user_id = du.id 
            group by du.city_id 
        ),
        --不分城市
        recharge_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(distinct if(rc.status=1 and from_unixtime(rc.create_time,'yyyy-MM-dd')='{pt}', rc.user_id, null)) as recharge_users,              --用户钱包充值人数
                count(distinct rc.user_id) as online_uv,                                                                                                --用户钱包总数量=线上uv
                sum(if(rc.status=1 and rc.recharge=1 and from_unixtime(rc.create_time,'yyyy-MM-dd')='{pt}', 1, 0)) as money_ballet_recharge_users       --今日钱包新充值人数
            from (select 
                    user_id,
                    status,
                    create_time, 
                    row_number() over(partition by user_id order by create_time) recharge
                from obus_dw_ods.ods_sqoop_data_user_recharge_df 
                where dt='{pt}' and 
                    user_id > 0
                ) as rc 
        ),
        --分城市
        ticket_data as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                city_id,
                count(1) as tied_tickets                                                --绑卡数
            from obus_dw_ods.ods_sqoop_data_ticket_df 
            where dt='{pt}' and 
                status=0 and 
                from_unixtime(bind_time, 'yyyy-MM-dd') = '{pt}' 
            group by city_id
        ),
        --不分城市
        ticket_data_all as (
            select 
                from_unixtime(unix_timestamp('{pt}','yyyy-MM-dd'), 'yyyyMMdd') as dt,
                0 as city_id,
                count(1) as tied_tickets                                                --绑卡数
            from obus_dw_ods.ods_sqoop_data_ticket_df 
            where dt='{pt}' and 
                status=0 and 
                from_unixtime(bind_time, 'yyyy-MM-dd') = '{pt}' 
        )
        --结果集
        select 
            cycle_data.dt,
            cycle_data.city_id,
            nvl(dc.name,''),
            cycle_data.total_lines,
            cycle_data.total_drivers,
            cycle_data.serv_drivers,
            cycle_data.no_serv_drivers,
            IF(order_data.line_orders IS NULL, 0, order_data.line_orders),
            IF(order_data.line_finished_orders IS NULL, 0, order_data.line_finished_orders),
            IF(order_data.line_gmv IS NULL, 0, order_data.line_gmv),
            IF(station_data.total_stations IS NULL, 0, station_data.total_stations),
            IF(users_data.users IS NULL, 0, users_data.users),
            IF(app_users_data.obusapp_new_users IS NULL, 0, app_users_data.obusapp_new_users),
            IF(app_ticket_data.ticket_new_users IS NULL, 0, app_ticket_data.ticket_new_users),
            IF(app_users_data.money_ballet_users IS NULL, 0, app_users_data.money_ballet_users),
            IF(recharge_data.recharge_users IS NULL, 0, recharge_data.recharge_users),
            IF(recharge_data.online_uv IS NULL, 0, recharge_data.online_uv),
            IF(recharge_data.money_ballet_recharge_users IS NULL, 0, recharge_data.money_ballet_recharge_users),
            IF(ticket_data.tied_tickets IS NULL, 0, ticket_data.tied_tickets) 
        from (select * from cycle_data union select * from cycle_data_all) as cycle_data 
        left join (select * from order_data union select * from order_data_all) as order_data 
            on cycle_data.dt = order_data.dt and cycle_data.city_id=order_data.city_id 
        left join (select * from station_data union select * from station_data_all) as station_data 
            on station_data.dt = cycle_data.dt and station_data.city_id = cycle_data.city_id 
        left join (select * from users_data union select * from users_data_all) as users_data 
            on users_data.dt = cycle_data.dt and users_data.city_id = cycle_data.city_id 
        left join (select * from app_users_data union select * from app_users_data_all) as app_users_data 
            on app_users_data.dt = cycle_data.dt and app_users_data.city_id = cycle_data.city_id 
        left join (select * from recharge_data union select * from recharge_data_all) as recharge_data 
            on recharge_data.dt = cycle_data.dt and recharge_data.city_id = cycle_data.city_id 
        left join (select * from ticket_data union select * from ticket_data_all) as ticket_data 
            on ticket_data.dt = cycle_data.dt and ticket_data.city_id = cycle_data.city_id 
        left join (select * from app_ticket_data union select * from app_ticket_data_all) as app_ticket_data 
            on app_ticket_data.dt = cycle_data.dt and app_ticket_data.city_id = cycle_data.city_id 
        left join (select id, name from obus_dw_ods.ods_sqoop_conf_city_df where dt='{pt}' and validate=1) as dc 
            on cycle_data.city_id = dc.id
            
    '''.format(
        pt=ds
    )
    logging.info(sql)
    hive_cursor = get_hive_cursor()
    hive_cursor.execute(sql)
    result = hive_cursor.fetchall()

    mysql_conn = get_db_conn('mysql_bi')
    mcursor = mysql_conn.cursor()
    __data_to_mysql(mcursor, result,
                ['dt','city_id','city','total_lines_double','total_drivers','serv_drivers',
                    'no_serv_drivers','lines_orders_double','lines_finished_orders_double',
                    'line_gmv_double','total_stations','new_users','obusapp_new_users','ticket_new_users',
                    'money_ballet_users','recharge_users','online_uv','money_ballet_recharge_users','tied_cards'],
                '''
                    total_lines_double=values(total_lines_double),
                    total_drivers=values(total_drivers),
                    serv_drivers=values(serv_drivers),
                    no_serv_drivers=values(no_serv_drivers),
                    lines_orders_double=values(lines_orders_double),
                    lines_finished_orders_double=values(lines_finished_orders_double),
                    total_stations=values(total_stations),
                    line_gmv_double=values(line_gmv_double),
                    new_users=values(new_users),
                    obusapp_new_users=values(obusapp_new_users),
                    ticket_new_users=values(ticket_new_users),
                    recharge_users=values(recharge_users),
                    online_uv=values(online_uv),
                    money_ballet_users=values(money_ballet_users),
                    tied_cards=values(tied_cards),
                    money_ballet_recharge_users=values(money_ballet_recharge_users)
                '''
    )

    hive_cursor.close()
    mcursor.close()


def __data_to_mysql(conn, data, column, update=''):
    isql = 'insert into obus_dw.app_obus_report_collect_d ({})'.format(','.join(column))
    esql = '{0} values {1} on duplicate key update {2}'
    sval = ''
    cnt = 0
    try:
        for (dt, city_id, name, total_lines, total_drivers, serv_drivers, no_serv_drivers, line_orders,
                line_finished_orders, line_gmv, total_stations, users, obusapp_new_users, ticket_new_users,
                money_ballet_users, recharge_users, online_uv, money_ballet_recharge_users,tied_tickets) in data:

            row = [dt, city_id, name, total_lines, total_drivers, serv_drivers, no_serv_drivers, line_orders,
                    line_finished_orders, line_gmv, total_stations, users, obusapp_new_users, ticket_new_users,
                    money_ballet_users, recharge_users, online_uv, money_ballet_recharge_users,tied_tickets]
            if sval == '':
                sval = '(\'{}\')'.format('\',\''.join([str(x) for x in row]))
            else:
                sval += ',(\'{}\')'.format('\',\''.join([str(x) for x in row]))
            cnt += 1
            if cnt >= 1000:
                logging.info(esql.format(isql, sval, update))
                conn.execute(esql.format(isql, sval, update))
                cnt = 0
                sval = ''

        if cnt > 0 and sval != '':
            logging.info(esql.format(isql, sval, update))
            conn.execute(esql.format(isql, sval, update))
    except BaseException as e:
        logging.info(e)
        return


get_data_from_impala_task = PythonOperator(
    task_id='get_data_from_impala_task',
    python_callable=get_data_from_impala,
    provide_context=True,
    dag=dag
)

dependence_ods_sqoop_data_driver_df >> get_data_from_impala_task
dependence_ods_sqoop_conf_cycle_df >> get_data_from_impala_task
dependence_ods_sqoop_data_order_df >> get_data_from_impala_task
dependence_ods_sqoop_conf_station_df >> get_data_from_impala_task
dependence_ods_sqoop_data_order_payment_df >> get_data_from_impala_task
dependence_ods_sqoop_data_user_recharge_df >> get_data_from_impala_task
dependence_ods_sqoop_data_user_df >> get_data_from_impala_task
dependence_ods_sqoop_data_ticket_df >> get_data_from_impala_task
