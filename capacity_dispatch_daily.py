import airflow
from datetime import datetime, timedelta
from airflow.operators.bash_operator import BashOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.hive_operator import HiveOperator
from airflow.utils.email import send_email
import logging
from airflow.models import Variable
from utils.connection_helper import get_hive_cursor

args = {
    'owner': 'root',
    'start_date': datetime(2019, 6, 14),
    'depends_on_past': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = airflow.DAG(
    'capacity_dispatch_daily',
    schedule_interval="30 02 * * *",
    default_args=args)

import_log_file = BashOperator(
    task_id='import_log_file',
    bash_command='''
        log_path="/data/app_log"
        dt="{{ ds_nodash }}"
        mkdir -p ${log_path}/${dt}
        # pull log file
        scp -P 622 root@124.156.118.128:/data/app/dispatcher/logs/${dt}.log ${log_path}/${dt}/gw1.log
        scp -P 2522 root@124.156.118.128:/data/app/dispatcher/logs/${dt}.log ${log_path}/${dt}/gw2.log
        scp -P 22722 root@124.156.118.128:/data/app/dispatcher/logs/${dt}.log ${log_path}/${dt}/gw3.log
    ''',
    dag=dag,
)

dispatch_table = HiveOperator(
    task_id='dispatch_table',
    hql='''
        insert overwrite table oride_bi.server_magic_dispatch_detail
        partition(dt='{{ ds }}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        driver_id
        from  
        oride_source.server_magic 
        lateral view explode(split(substr(get_json_object(event_values, '$.driver_ids'),1,length(get_json_object(event_values, '$.driver_ids'))-2),',')) driver_ids as driver_id
        where  dt = '{{ ds }}' and event_name='dispatch_chose_driver' 
        ''',
    schema='oride_source',
    dag=dag)

filter_table = HiveOperator(
    task_id='filter_table',
    hql='''
        insert overwrite table oride_bi.server_magic_filter_detail
        partition(dt='{{ ds }}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        get_json_object(event_values, '$.driver_id') as `driver_id`,
        get_json_object(event_values, '$.reason') as `reason`
        from  
        oride_source.server_magic 
        where  dt = '{{ ds }}' and event_name='dispatch_filter_driver' 
        ''',
    schema='oride_source',
    dag=dag)

assign_table = HiveOperator(
    task_id='assign_table',
    hql='''
        insert overwrite table oride_bi.server_magic_assign_detail
        partition(dt='{{ ds }}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        driver_id
        from  
        oride_source.server_magic 
        lateral view explode(split(substr(get_json_object(event_values, '$.driver_ids'),1,length(get_json_object(event_values, '$.driver_ids'))-2),',')) driver_ids as driver_id
        where  dt = '{{ ds }}' and event_name='dispatch_assign_driver' 
        ''',
    schema='oride_source',
    dag=dag)

push_table = HiveOperator(
    task_id='push_table',
    hql='''
        insert overwrite table oride_bi.server_magic_push_detail
        partition(dt='{{ ds }}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        get_json_object(event_values, '$.driver_id') as `driver_id`
        from  
        oride_source.server_magic 
        where  dt = '{{ ds }}' and event_name='dispatch_push_driver' 
        and get_json_object(event_values, '$.success') = 1
        ''',
    schema='oride_source',
    dag=dag)


def insert_data(ds, **kwargs):
    cursor = get_hive_cursor()

    sql = '''
        insert overwrite table oride_bi.server_magic_dispatch_detail
        partition(dt='{dt}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        driver_id
        from  
        oride_source.server_magic 
        lateral view explode(split(substr(get_json_object(event_values, '$.driver_ids'),1,length(get_json_object(event_values, '$.driver_ids'))-2),',')) driver_ids as driver_id
        where  dt = '{dt}' and event_name='dispatch_chose_driver' 
        '''.format(dt=ds)

    logging.info(sql)
    cursor.execute(sql)
    res = cursor.fetchall()

    sql = '''
        insert overwrite table oride_bi.server_magic_filter_detail
        partition(dt='{dt}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        get_json_object(event_values, '$.driver_id') as `driver_id`,
        get_json_object(event_values, '$.reason') as `reason`
        from  
        oride_source.server_magic 
        where  dt = '{dt}' and event_name='dispatch_filter_driver' 


    '''.format(dt=ds)

    logging.info(sql)
    cursor.execute(sql)
    res = cursor.fetchall()

    sql = '''
        insert overwrite table oride_bi.server_magic_assign_detail
        partition(dt='{dt}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        driver_id
        from  
        oride_source.server_magic 
        lateral view explode(split(substr(get_json_object(event_values, '$.driver_ids'),1,length(get_json_object(event_values, '$.driver_ids'))-2),',')) driver_ids as driver_id
        where  dt = '{dt}' and event_name='dispatch_assign_driver' 

    '''.format(dt=ds)

    logging.info(sql)
    cursor.execute(sql)
    res = cursor.fetchall()

    sql = '''
        insert overwrite table oride_bi.server_magic_push_detail
        partition(dt='{dt}')
        select 
        get_json_object(event_values, '$.order_id') order_id, 
        get_json_object(event_values, '$.round') as `round`, 
        get_json_object(event_values, '$.user_id') as `user_id`,
        get_json_object(event_values, '$.driver_id') as `driver_id`
        from  
        oride_source.server_magic 
        where  dt = '{dt}' and event_name='dispatch_push_driver' 
        and get_json_object(event_values, '$.success') = 1

    '''.format(dt=ds)

    logging.info(sql)
    cursor.execute(sql)
    res = cursor.fetchall()
    cursor.close()
    return


def send_report_email(ds_nodash, ds, **kwargs):
    cursor = get_hive_cursor()
    sql = '''
        select 
        tt.dt,
        tt.counts report_times,
        concat(cast(round(tt.driver_id_not_found * 100/tt.counts,2) as string),'%') not_found_driver_rate,
        concat(cast(round((tt.counts - tt.push_driver_num) * 100/tt.counts,2) as string),'%') filter_driver_rate,
        concat(cast(round(tt.push_driver_num * 100/tt.counts,2) as string),'%') push_driver_rate,
        concat(cast(round(tt.accept_driver_time_num * 100/tt.counts,2) as string),'%') accept_driver_time_rate,

        concat(cast(round(tt.not_idle_rate * 100,2) as string),'%') not_idle_rate,
        concat(cast(round(tt.assigned_another_job_rate * 100,2) as string),'%') assigned_another_job_rate,
        concat(cast(round(tt.assigned_this_order_rate * 100,2) as string),'%') assigned_this_order_rate,
        concat(cast(round(tt.not_in_service_mode_rate * 100,2) as string),'%') not_in_service_mode_rate,


        round(pp.push_avg,1) push_avg,
        round(pp.push_order_avg,1) push_order_avg,
        round(tt.order_push_driver_avg,1) order_push_driver_avg,
        round(tt.accept_driver_time_avg,1) accept_driver_time_avg,
        concat(cast(round(tt.accept_driver_time_avg * 100/pp.push_avg,2) as string),'%') obey_rate

        from 
        (
            select 
            t.dt dt,
            count(1) counts,
            count(if(assign_driver_num is not null and assign_driver_num <> 0,assign_driver_num,null)) push_driver_num,
            count(if(driver_id = 0,null,driver_id)) accept_driver_time_num,
            sum(not_idle_num)/sum(assigned_another_job_num + not_in_service_mode_num + not_idle_num + assigned_this_order_before) not_idle_rate,
            sum(assigned_another_job_num)/sum(assigned_another_job_num + not_in_service_mode_num + not_idle_num + assigned_this_order_before) assigned_another_job_rate,
            sum(assigned_this_order_before)/sum(assigned_another_job_num + not_in_service_mode_num + not_idle_num + assigned_this_order_before) assigned_this_order_rate,
            sum(if(assign_driver_num is not null and assign_driver_num <> 0,assign_driver_num,0))/count(if(assign_driver_num is not null  and assign_driver_num <> 0,assign_driver_num,null)) order_push_driver_avg,
            sum(not_in_service_mode_num)/sum(assigned_another_job_num + not_in_service_mode_num + not_idle_num + assigned_this_order_before) not_in_service_mode_rate,
            count(if(driver_id = 0,null,driver_id))/count(distinct(if(driver_id = 0,null,driver_id))) accept_driver_time_avg,
            sum(if(driver_id_not_found = 0,1,0)) driver_id_not_found

            from
            (
            select
                ofc.dt,
                ofc.order_id,
                ofc.round,
                sum(if(ofb.reason='assigned_another_job', 1, 0)) as assigned_another_job_num,
                sum(if(ofb.reason='not_in_service_mode', 1, 0)) as not_in_service_mode_num,
                sum(if(ofb.reason='not_idle', 1, 0)) as not_idle_num,
                sum(if(ofb.reason='assigned_this_order_before', 1, 0)) as assigned_this_order_before,
                max(oa.driver_num) as assign_driver_num,
                max(oa.round) as assign_time,
                if(max(ofc.driver_id) is null,0,max(ofc.driver_id)) as driver_id,
                count(ofc.driver_id_not_found) driver_id_not_found
                from
                (
                    select
                        a.dt,
                        a.order_id,
                        a.round,
                        if (rank() over(partition by order_id order by round desc ) =1, b.driver_id, 0) as driver_id,
                        a.driver_id driver_id_not_found

                    from oride_bi.server_magic_dispatch_detail a
                    left join oride_db.data_order b ON b.id=a.order_id and b.dt='{dt}' and from_unixtime(b.create_time,'yyyy-MM-dd') between '{start_date}' and '{dt}'
                    where a.dt between '{start_date}' and '{dt}'
                ) ofc
                left join
                (
                    select
                        dt,
                        order_id,
                        reason,
                        round
                    from oride_bi.server_magic_filter_detail
                    where dt between '{start_date}' and '{dt}'
                ) ofb on ofb.dt=ofc.dt and ofb.order_id=ofc.order_id and ofb.round=ofc.round
                left join
                (
                select
                        dt,
                        round,
                        order_id,
                        count(driver_id) driver_num
                    from
                        oride_bi.server_magic_push_detail
                        where dt between '{start_date}' and '{dt}'
                        group by dt,
                        round,
                        order_id
                ) oa on oa.dt=ofc.dt and oa.order_id=ofc.order_id and oa.round=ofc.round
                where ofc.dt between '{start_date}' and '{dt}'
                group by
                ofc.dt,
                ofc.order_id,
                ofc.round
            ) t
            group by t.dt
        ) tt
        left join (
            select 
            p.dt dt,
            sum(order_num)/count(1) push_avg, 
            sum(order_num_dis)/count(1) push_order_avg
            from 
            (
                select
                    dt dt,
                    driver_id,
                    count(order_id) order_num,
                    count(distinct(order_id)) order_num_dis
                from
                    oride_bi.server_magic_push_detail
                where dt between '{start_date}' and '{dt}'
                group by dt,driver_id
            ) p
            group by p.dt
        ) pp on tt.dt = pp.dt
    '''.format(dt=ds,
               start_date=airflow.macros.ds_add(ds, -5))

    html = ''

    html_head = '''
                    <html>
            <head>
            <title></title>
            <style type="text/css">
                table
                {
                    font-family: "Trebuchet MS", Arial, Helvetica, sans-serif;
                    border-collapse: collapse;
                    margin: 0 auto;
                    text-align: left;
                }
                table td, table th
                {
                    border: 1px solid #cad9ea;
                    color: #666;
                    height: 30px;
                    padding: 5px 10px 5px 5px;
                }
                table thead th
                {
                    background-color: #4CAF50;
                    color: white;
                    width: 100px;
                }
                table tr:nth-child(odd)
                {
                    background: #fff;
                }
                table tr:nth-child(even)
                {
                    background: #F5FAFA;
                }
            </style>
            </head>
            <body>


            '''

    html_tail = '''
                </body>
            </html>
            '''

    html += html_head

    logging.info(sql)
    cursor.execute(sql)
    res = cursor.fetchall()

    html_fmt_1_head = '''
        <table width="95%" class="table">
                <caption>
                    <h2></h2>
                </caption>
                <thead>
                    <tr>
                        <th colspan="6" style="text-align: center;">订单播报过程点分布</th>
                    </tr>
                    <tr>
                        <th>日期</th>
                        <th>播报轮数</th>
                        <th>圈选不到司机</th>
                        <th>圈选后司机都被过滤</th>
                        <th>订单指派给司机</th>
                        <th>司机成功接单</th>
                    </tr>
                </thead>
    '''

    html += html_fmt_1_head
    html_fmt_1_tail = '</table>'

    i = 0
    while i < len(res):
        [date, report_round_num, not_found_driver_num, driver_filterd_num, send_to_driver_num,
         driver_accept_num] = list(res[i])[0:6]

        html_fmt_1 = '''
                <tr>
                    <td>{date}</td>
                    <td>{report_round_num}</td>
                    <td>{not_found_driver_num}</td>
                    <td>{driver_filterd_num}</td>
                    <td>{send_to_driver_num}</td>
                    <td>{driver_accept_num}</td>
                </tr>

        '''
        html_fmt_1 = html_fmt_1.format(
            dt=ds,
            date=date,
            report_round_num=report_round_num,
            not_found_driver_num=not_found_driver_num,
            driver_filterd_num=driver_filterd_num,
            send_to_driver_num=send_to_driver_num,
            driver_accept_num=driver_accept_num
        )

        html += html_fmt_1
        i += 1

    html + html_fmt_1_tail

    html_fmt_2_head = '''
        <table width="95%" class="table">
                        <caption>
                            <h2></h2>
                        </caption>
                        <thead>
                            <tr>
                                <th colspan="5" style="text-align: center;">司机被过滤原因分布</th>
                            </tr>
                            <tr>
                                <th>日期</th>
                                <th>正在干活</th>
                                <th>被其他订单锁住</th>
                                <th>被指派过</th>
                                <th>不在接单状态</th>
                            </tr>
                        </thead>
    '''
    html_fmt_2_tail = '</table>'

    html += html_fmt_2_head

    i = 0
    while i < len(res):
        list_temp = list(res[i])

        date = list_temp[0]
        in_work = list_temp[6]
        in_lock = list_temp[7]
        has_send = list_temp[8]
        not_in_service = list_temp[9]

        html_fmt_2 = '''

                        <tr>
                            <td>{date}</td>
                            <td>{in_work}</td>
                            <td>{in_lock}</td>
                            <td>{has_send}</td>
                            <td>{not_in_service}</td>
                        </tr>


                '''
        html_fmt_2 = html_fmt_2.format(
            dt=ds,
            date=date,
            in_work=in_work,
            in_lock=in_lock,
            has_send=has_send,
            not_in_service=not_in_service
        )

        html += html_fmt_2
        i += 1

    html += html_fmt_2_tail

    html_fmt_3_head = '''
        <table width="95%" class="table">
                                <caption>
                                    <h2></h2>
                                </caption>
                                <thead>
                                    <tr>
                                        <th colspan="6" style="text-align: center;">司机指标</th>
                                    </tr>
                                    <tr>
                                        <th>日期</th>
                                        <th>骑手平均被推送次数</th>
                                        <th>骑手平均被推送订单</th>
                                        <th>订单平均推送骑手数</th>
                                        <th>骑手平均应答次数</th>
                                        <th>服从率</th>
                                    </tr>
                                </thead>

    '''

    html_fmt_3_tail = '</table>'
    html += html_fmt_3_head

    i = 0
    while i < len(res):
        list_temp = list(res[i])

        date = list_temp[0]
        driver_pushed_times = list_temp[10]
        driver_pushed_order = list_temp[11]
        order_push_driver_times = list_temp[12]
        driver_reply_num = list_temp[13]
        obey_rate = list_temp[14]

        html_fmt_3 = '''

                                <tr>
                                    <td>{date}</td>
                                    <td>{driver_pushed_times}</td>
                                    <td>{driver_pushed_order}</td>
                                    <td>{order_push_driver_times}</td>
                                    <td>{driver_reply_num}</td>
                                    <td>{obey_rate}</td>
                                </tr>


                        '''
        html_fmt_3 = html_fmt_3.format(
            dt=ds,
            date=date,
            driver_pushed_times=driver_pushed_times,
            driver_pushed_order=driver_pushed_order,
            order_push_driver_times=order_push_driver_times,
            driver_reply_num=driver_reply_num,
            obey_rate=obey_rate
        )

        html += html_fmt_3
        i += 1

    html += html_fmt_3_tail

    sql = '''
        select
        from_unixtime(create_time,'yyyy-MM-dd'),
        count(id),
        count(if(driver_id <> 0,id,null)),
        concat(cast(round(count(if(driver_id <> 0,id,null)) * 100/count(id),2) as string),'%'),
        count(if(status = 5 or status = 4,id,null)),
        concat(cast(round(count(if(status = 5 or status = 4,id,null)) * 100/count(id),2) as string),'%'),
        count(distinct(if(status = 5 or status = 4,driver_id,null))),
        round(count(if(status = 5 or status = 4,id,null))/count(distinct(if(status = 5 or status = 4,driver_id,null))),1),
        round((sum(if(pickup_time <> 0, pickup_time - take_time,0)/60)/count(if(status = 5 or status = 4,id,null))),1),
        round((sum(if(take_time <> 0,take_time - create_time,0))/count(if(driver_id <> 0,id,null)))/60,1),

        concat(cast(round(count(if(status = 6 and (cancel_role = 3 or cancel_role = 4),id,null)) * 100/count(id),2) as string),'%'),
        concat(cast(round(count(if(status = 6 and driver_id = 0  and cancel_role = 1,id,null)) * 100/count(id),2) as string),'%'),
        concat(cast(round(count(if(status = 6 and driver_id <> 0  and cancel_role = 1,id,null)) * 100/count(id),2) as string),'%')
    from
        oride_db.data_order where dt= '{ds}' and from_unixtime(create_time,'yyyy-MM-dd') between '{start_date}' and '{ds}'
    group by from_unixtime(create_time,'yyyy-MM-dd')

    '''.format(ds=ds, start_date=airflow.macros.ds_add(ds, -5))

    cursor.execute(sql)
    res = cursor.fetchall()

    html_fmt_4_head = '''
        <table width="95%" class="table">
                                        <caption>
                                            <h2></h2>
                                        </caption>
                                        <thead>
                                            <tr>
                                                <th colspan="10" style="text-align: center;">宏观指标</th>
                                            </tr>
                                            <tr>
                                                <th>日期</th>
                                                <th>下单量</th>
                                                <th>接单量</th>
                                                <th>接单率</th>
                                                <th>完单量</th>
                                                <th>完单率</th>
                                                <th>完单骑手数</th>
                                                <th>人均完单量</th>
                                                <th>单均接驾时长（分钟）</th>
                                                <th>单均应答时长（分钟）</th>
                                            </tr>
                                        </thead>

    '''

    html_fmt_4_tail = '</table>'
    html += html_fmt_4_head

    i = 0
    while i < len(res):
        [date, ride_num, request_num, request_rate, on_ride_num, on_ride_rate, onride_driver_num,
         onride_driver_order_avg,
         pick_up_passager_time_avg, reply_time_avg
         ] = list(
            res[i][:10])
        html_fmt_4 = '''

                                        <tr>
                                            <td>{date}</td>
                                            <td>{ride_num}</td>
                                            <td>{request_num}</td>
                                            <td>{request_rate}</td>
                                            <td>{on_ride_num}</td>
                                            <td>{on_ride_rate}</td>
                                            <td>{onride_driver_num}</td>
                                            <td>{onride_driver_order_avg}</td>
                                            <td>{pick_up_passager_time_avg}</td>
                                            <td>{reply_time_avg}</td>
                                        </tr>


                                '''
        html_fmt_4 = html_fmt_4.format(
            dt=ds,
            date=date,
            ride_num=ride_num,
            request_num=request_num,
            request_rate=request_rate,
            on_ride_num=on_ride_num,
            on_ride_rate=on_ride_rate,
            onride_driver_num=onride_driver_num,
            onride_driver_order_avg=onride_driver_order_avg,
            pick_up_passager_time_avg=pick_up_passager_time_avg,
            reply_time_avg=reply_time_avg

        )

        html += html_fmt_4
        i += 1

    html += html_fmt_4_tail
    html += html_tail

    html_fmt_5_head = '''
            <table width="95%" class="table">
                                            <caption>
                                                <h2></h2>
                                            </caption>
                                            <thead>
                                                <tr>
                                                    <th colspan="10" style="text-align: center;">乘客指标</th>
                                                </tr>
                                                <tr>
                                                    <th>日期</th>
                                                    <th>系统取消率</th>
                                                    <th>乘客应答前取消率</th>
                                                    <th>乘客应答后取消率</th>
                                                </tr>
                                            </thead>

        '''

    html_fmt_5_tail = '</table>'
    html += html_fmt_5_head

    i = 0
    while i < len(res):
        list_temp = list(res[i])
        date = list_temp[0]
        admin_cancel_rate = list_temp[10]
        passager_cancel_before_rate = list_temp[11]
        passager_cancel_after_rate = list_temp[12]

        html_fmt_5 = '''

                        <tr>
                            <td>{date}</td>
                            <td>{admin_cancel_rate}</td>
                            <td>{passager_cancel_before_rate}</td>
                            <td>{passager_cancel_after_rate}</td>
                        </tr>
                        '''
        html_fmt_5 = html_fmt_5.format(
            dt=ds,
            date=date,
            admin_cancel_rate=admin_cancel_rate,
            passager_cancel_before_rate=passager_cancel_before_rate,
            passager_cancel_after_rate=passager_cancel_after_rate)

        html += html_fmt_5
        i += 1

    html += html_fmt_5_tail

    html += '<p>策略文档地址：https://docs.qq.com/sheet/DV21ZdlJUUENyYXBn?preview_token=&tab=BB08J2&coord=B8%24B8%240%240%240%240</p>'

    html += html_tail

    logging.info(html)

    # send mail
    email_subject = 'oride汇总指标统计_{}'.format(ds)
    send_email(['nan.li@opay-inc.com', 'song.zhang@opay-inc.com', 'mingze.yang@opay-inc.com',
                ], email_subject, html, mime_charset='utf-8')
    cursor.close()
    return


# insert_report_data = PythonOperator(
#     task_id='insert_data',
#     python_callable=insert_data,
#     provide_context=True,
#     dag=dag
# )

send_report = PythonOperator(
    task_id='send_report',
    python_callable=send_report_email,
    provide_context=True,
    dag=dag
)

dispatch_table >> filter_table >> assign_table >> push_table >> send_report
