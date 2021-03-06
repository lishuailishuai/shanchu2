
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
import json
import logging
from airflow.models import Variable
import requests
import os
from airflow.sensors import OssSensor

args = {
        'owner': 'yangmingze',
        'start_date': datetime(2019, 11, 9),
        'depends_on_past': False,
        'retries': 3,
        'retry_delay': timedelta(minutes=2),
        'email': ['bigdata_dw@opay-inc.com'],
        'email_on_failure': True,
        'email_on_retry': False,
} 

dag = airflow.DAG( 'dwd_oride_rider_signups_df', 
    schedule_interval="10 00 * * *",
    default_args=args,
    )

##----------------------------------------- 变量 ---------------------------------------##

db_name="oride_dw"
table_name="dwd_oride_rider_signups_df"


##----------------------------------------- 依赖 ---------------------------------------## 
# 获取变量
code_map=eval(Variable.get("sys_flag"))

# 判断ufile(cdh环境)
if code_map["id"].lower()=="ufile":

    ods_sqoop_mass_rider_signups_df_tesk = UFileSensor(
        task_id='ods_sqoop_mass_rider_signups_df_tesk',
        filepath="{hdfs_path_str}/dt={pt}/_SUCCESS".format(
            hdfs_path_str="oride_dw_sqoop/opay_spread/rider_signups",
            pt="{{ds}}"
        ),
        bucket_name='opay-datalake',
        poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
        dag=dag
    )
    # 路径
    hdfs_path = "ufile://opay-datalake/oride/oride_dw/dwd_oride_rider_signups_df"
else:
    ods_sqoop_mass_rider_signups_df_tesk = OssSensor(
        task_id='ods_sqoop_mass_rider_signups_df_tesk',
        bucket_key="{hdfs_path_str}/dt={pt}/_SUCCESS".format(
            hdfs_path_str="oride_dw_sqoop/opay_spread/rider_signups",
            pt="{{ds}}"
        ),
        bucket_name='opay-datalake',
        poke_interval=60,  # 依赖不满足时，一分钟检查一次依赖状态
        dag=dag
    )
    # 路径
    hdfs_path = "oss://opay-datalake/oride/oride_dw/dwd_oride_rider_signups_df"



##----------------------------------------- 任务超时监控 ---------------------------------------## 

def fun_task_timeout_monitor(ds,dag,**op_kwargs):

    dag_ids=dag.dag_id

    msg = [
        {"dag":dag,"db": "oride_dw", "table":"{dag_name}".format(dag_name=dag_ids), "partition": "country_code=nal/dt={pt}".format(pt=ds), "timeout": "800"}
    ]

    TaskTimeoutMonitor().set_task_monitor(msg)

task_timeout_monitor= PythonOperator(
    task_id='task_timeout_monitor',
    python_callable=fun_task_timeout_monitor,
    provide_context=True,
    dag=dag
)

##----------------------------------------- 脚本 ---------------------------------------## 

def dwd_oride_rider_signups_df_sql_task(ds):

    HQL='''

    
    set hive.exec.parallel=true;
    set hive.exec.dynamic.partition.mode=nonstrict;

    INSERT overwrite TABLE oride_dw.dwd_oride_rider_signups_df partition(country_code,dt)

    SELECT id,
       --未知

       name,
       --司机姓名

       mobile,
       --电话号码

       gender,
       --1男，2女

       birthday,
       --生日

       country,
       --国家

       STATE,
       --州

       city,
       --城市

       address,
       --详细地址

       address_photo,
       --地址验证图片.

       address_status,
       --地址验证状态: 0:Pending 1:Passed 9:Failed

       address_status_note,
       --地址验证未通过原因

       adress_status_time,
       --地址审核时间

       address_status_admin_id,
       --地址审核管理员id

       address_collecting_time,
       --address veri time.

       avator,
       --头像

       dirver_experience,
       --是否有驾驶经验：0没有，1有

       license_number,
       --驾照号

       holding_license_time,
       --驾照持有时间:1:less than 1 year2: 2~3 years3: More than 3 years

       gmail_account,
       --未知

       opay_account,
       --未知

       drivers_test,
       --驾驶能力测试：0:Pending 1:Passed 9:Failed

       drivers_test_note,
       --测试结果备注或说明.

       drivers_test_time,
       --驾驶能力测试时间

       drivers_test_admin_id,
       --驾驶能力测试管理员id

       way_know,
       --single selection 1. OPAY AGENT2. ADVERTISEMENT3. THROUGH A FRIEND 10 预注册

       base_finished_time,
       --基础信息完成时间:几乎等同于注册时间

       bvn_number,
       --BVN码

       bnv_status,
       --bvn码状态: 0:Pending 1:Passed 9:Failed

       bvn_status_note,
       --bvn验证未通过原因

       bvn_time,
       --bvn审核时间

       bvn_admin_id,
       --bvn审核管理员id

       veri_time,
       --骑手审核时间

       status,
       --骑手状态:0待审核,1正在审核,2通过审核,9审核失败,拒绝该账号

       note,
       --最终验证失败后的理由.

       admin_id,
       --最终验证人ID.

       reg_code,
       --注册码

       create_time,
       --未知

       update_time,
       --未知

       rider_experience,
       --Do you have any rider experience as a job before? 1:XGo 2:Gokada 3: Other company 4: self business 5: Not at all 6: EasyM 7: MaxGo 8: JumiaFood 9: FedEx 10: DHL

       exp_cert_images,
       --竞对证据图片

       exp_plate_number,
       --竞对证据车牌号

       know_orider,
       --How did you find out about ORide? 1:OPay Agent 2:Advertisment 3:Through friend 4:field sales 5:telesales 6:self visit 7:through riders 8:HR Agent 9:Road show 10:ORide app 11:Association introduction

       know_orider_extend,
       --对应know_orider的号码

       agent_opay_account,
       --Agent opay account

       field_sales_number,
       --field sales number

       telesales_number,
       --telesales number

       riders_number,
       --through riders; rider number

       road_show_number,
       --路演工作人员手机号

       hr_agent_company,
       --agent id

       emergencies_name,
       --In Case Of Emergencies who do we contact? Name

       emergencies_mobile,
       --In Case Of Emergencies who do we contact? Mobile

       traing_test,
       --管理后台增加审核项——是否参加培训并通过测试:  1:passed、0:pengding 两种状态

       is_reward_amount,
       --是否领取新骑手奖励金额，1:passed 0:pengding

       reward_amount,
       --新骑手领取奖励金额

       marital_status,
       --1:marriged 2:unmarried 3:divorced

       religion,
       --1:Christians 2:Muslims 3:none 4:others

       religion_other,
       --religion other

       id_number,
       --Identify number

       online_test,
       --笔试测试：0:Pending 1:Passed 9:Failed

       online_test_note,
       --笔试未通过原因

       online_test_time,
       --笔试测试时间

       online_test_admin_id,
       --笔试审核管理员id

       driver_type,
       --骑手类型：1 ORide-Green, 2 ORide-Street, 3 OTrike

       own_vehicle_brand,
       --第三方骑手车辆品牌

       own_vehicle_brand_other,
       --第三方骑手车辆其它品牌

       own_vehicle_model,
       --第三方骑手车辆型号

       own_plate_number,
       --第三方骑手车牌号

       own_chassis_number,
       --第三方骑手车架号

       own_engine_number,
       --第三方骑手发动机号

       own_engine_capacity,
       --第三方骑手发动机排量

       own_bike_photos,
       --第三方骑手车辆图片

       local_government,
       --第三方骑手地理围栏json

       vehicle_status,
       --车辆状况：0:Pending 1:Passed 9:Failed

       vehicle_status_note,
       --第三方骑手车辆验证未通过原因

       vehicle_status_time,
       --车辆状况检查时间

       vehicle_status_admin_id,
       --车况检查管理员id

       record_by,
       --填写人

       form_pics,
       --报名表照片等

       association_id,
       --骑手所属协会id

       team_id,
       --骑手所属协会team id

       driver_id,
       --在oride后台的ID

       job_type,
       --keke司机工作类型: 1 all day 2 day shift 3 night shift 4 Part time

       is_vehicle_owner,
       --是否是keke车主: 0 不是 1 是

       ofood_driver,
       --是否同时为ofood骑手: 0 否 1 是

       region_id,
       --地区

       use_own_phone,
       --是否使用自已的手机 0否 1是

       own_phone_status,
       --自带手机检验状态 0:Pending 1:Passed 9:Failed

       own_phone_status_note,
       --自带手机检验未通过原因

       own_phone_status_time,
       --自带手机检验时间

       own_phone_status_admin_id,
       --自带手机检验管理员id

       nationality,
       --国籍

       license_expire_date,
       --驾驶证有效期

       license_photo,
       --驾驶证照片

       vehicle_license_number,
       --车辆行驶证

       vehicle_license_expire_date,
       --车辆行驶证有效期

       vehicle_license_photo,
       --车辆行驶证照片

       mobile_money_operator,
       --Mobile Money运营商

       mobile_money_account,--骑手Mobile Money账号

       'nal' as country_code,
        '{pt}' as dt

FROM oride_dw_ods.ods_sqoop_mass_rider_signups_df
WHERE dt='{pt}'
    
    
    '''.format(
        pt=ds,
        table=table_name,
        db=db_name
        )
    return HQL


#熔断数据，如果数据重复，报错
# def check_key_data_task(ds):

#     cursor = get_hive_cursor()

#     #主键重复校验
#     check_sql='''
#     SELECT count(1)-count(distinct city_id) as cnt
#       FROM {db}.{table}
#       WHERE dt='{pt}'
#       and country_code in ('NG')
#     '''.format(
#         pt=ds,
#         now_day=airflow.macros.ds_add(ds, +1),
#         table=table_name,
#         db=db_name
#         )

#     logging.info('Executing 主键重复校验: %s', check_sql)

#     cursor.execute(check_sql)

#     res = cursor.fetchone()
 
#     if res[0] >1:
#         flag=1
#         raise Exception ("Error The primary key repeat !", res)
#         sys.exit(1)
#     else:
#         flag=0
#         print("-----> Notice Data Export Success ......")

#     return flag



#主流程
def execution_data_task_id(ds,**kargs):

    hive_hook = HiveCliHook()

    #读取sql
    _sql=dwd_oride_rider_signups_df_sql_task(ds)

    logging.info('Executing: %s', _sql)

    #执行Hive
    hive_hook.run_cli(_sql)

    #熔断数据
    #check_key_data_task(ds)

    #生成_SUCCESS
    """
    第一个参数true: 数据目录是有country_code分区。false 没有
    第二个参数true: 数据有才生成_SUCCESS false 数据没有也生成_SUCCESS 

    """
    TaskTouchzSuccess().countries_touchz_success(ds,db_name,table_name,hdfs_path,"true","true")
    
dwd_oride_rider_signups_df_task= PythonOperator(
    task_id='dwd_oride_rider_signups_df_task',
    python_callable=execution_data_task_id,
    provide_context=True,
    dag=dag
)


ods_sqoop_mass_rider_signups_df_tesk>>dwd_oride_rider_signups_df_task