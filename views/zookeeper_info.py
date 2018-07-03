#-*- coding: utf-8 -*-
from flask import Blueprint,render_template,g,request,flash
from Modules import produce,check,loging,main_info
from kazoo.client import KazooClient
import __init__
app = __init__.app
logging = loging.Error()
page_zk_info=Blueprint('zookeeper_info',__name__)
host = app.config.get('ZOOKEEPER_HOST')
port = app.config.get('ZOOKEEPER_PORT')
zk = KazooClient('%s:%s' %(host,port))
@page_zk_info.route('/zk')
@page_zk_info.route( '/zk/info')
@main_info.main_info
def Zookeeper_Info():
    def Get_arg(arg):
        #解析请求参数
        if arg in request.args:
            return  request.args[arg]
        else:
            return None
    try:
        URL = None
        if 'info' in request.path:
            URL = Get_arg('path')
        zk.start()
        if URL:
            #匹配多级访问
            if '_' in URL:
                PATH = URL.replace(':','/')
                URLS = PATH.split('/')
            else:
                #匹配一级访问
                URLS = (URL,)
                PATH = URL
        #匹配根访问
        else:
            URLS = ()
            PATH = ''
        DATAS = zk.get_children('/%s'%PATH)
        INFOS = None
        if not DATAS:
            INFOS = zk.get('/%s'%PATH)
        return render_template('zk_show.html',Main_Infos=g.main_infos,DATAS = DATAS,URLS=URLS,URL=URL,INFOS=INFOS)
    except Exception as e:
        logging.error(e)
        flash(str(e))
        return  render_template('Message_static.html',Main_Infos=g.main_infos)

@page_zk_info.before_request
@check.login_required(grade=10)
def check_login(error=None):
    produce.Async_log(g.user, request.url)

@page_zk_info.teardown_request
def zk_remove(error=None):
    zk.stop()
    zk.close()


