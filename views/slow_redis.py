#-*- coding: utf-8 -*-
import redis
from flask import Blueprint,render_template,g,flash,request
from Modules import loging, check,produce,MyForm,main_info
import __init__
app = __init__.app
logging = loging.Error()
redis_ips = app.config.get('REDIS_IPS')
page_slow_redis=Blueprint('slow_redis',__name__)
@page_slow_redis.route('/slow_redis',methods = ['GET', 'POST'])
@main_info.main_info
def slow_redis():
    form = MyForm.myform()
    if form.submit_redis.data:
        for ip in redis_ips:
            Redis = redis.StrictRedis(host=ip, port=6379, db=0, socket_timeout=1)
            Redis.slowlog_reset()
            Redis.config_set("slowlog-max-len", 100)
            Redis.config_set("slowlog-log-slower-than", 200000)
    for ip in redis_ips:
        try:
            Redis = redis.StrictRedis(host=ip,port=6379,db=0,socket_timeout=1)
            results = Redis.slowlog_get(100)
        except:
            logging.error('%s Timeout reading from socket!' %ip)
            continue
        if results:
            flash("redis server:%s" %ip)
            flash("slow log len:%s" %Redis.slowlog_len())
            flash(results)
    return render_template('slow_redis_show.html',Main_Infos=g.main_infos,form = form)
@page_slow_redis.before_request
@check.login_required(grade=10)
def check_login(error=None):
    produce.Async_log(g.user, request.url)