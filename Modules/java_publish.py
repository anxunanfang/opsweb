#-*- coding: utf-8 -*-
import paramiko
from scp import SCPClient
import sys
import os
import time
from rediscluster import RedisCluster
import Mysql,loging
import __init__
app = __init__.app
import shutil
nodes = app.config.get('NODES_PRODUCE')
Redis = RedisCluster(startup_nodes=nodes,decode_responses=True)
mysql_user = app.config.get('MYSQL_USER')
mysql_password = app.config.get('MYSQL_PASSWORD')
mysql_host = app.config.get('MYSQL_HOST')
mysql_port = app.config.get('MYSQL_PORT')
mysql_db = 'op'
MYSQL = Mysql.MYSQL(mysql_user,mysql_password,mysql_host,mysql_port,mysql_db)
svnUrl = app.config.get('SVN_URL')
svnUser = app.config.get('SVN_USER')
svnPassword = app.config.get('SVN_PASSWORD')
svnDir = app.config.get('SVN_FILE_DIR')
gitUrl = app.config.get('GIT_URL')
gitUser = app.config.get('GIT_USER')
gitPassword = app.config.get('GIT_PASSWORD')
gitDir = app.config.get('GIT_FILE_DIR')
def java_publish(publish_key,Message_key):
    # 从svn获取war包
    def svn_up(warZipName):
        Redis.lpush(Message_key, '%s svn export start......' % warZipName)
        os.system('export LC_CTYPE="zh_CN.UTF-8"')
        os.system('/bin/mkdir -p %s' % svnDir)
        war_path = '%s%s' % (svnDir, warZipName)
        warTagName = warZipName.split('.zip')[0]
        if os.path.exists(war_path):
            os.remove(war_path)
        svnCoCmd = '/usr/bin/svn export --no-auth-cache --non-interactive --username %s --password %s  %s/svn/publish/produce/%s  %s' % (
        svnUser, svnPassword,svnUrl,warZipName, war_path)
        os.system(svnCoCmd)
        if os.path.exists(war_path):
            os.system('cd %s  &&  /usr/bin/unzip -qo %s' % (svnDir, warZipName))
            if os.path.exists("{0}{1}".format(svnDir, warTagName)):
                shutil.rmtree("{0}{1}".format(svnDir, warTagName))
            else:
                Redis.lpush(Message_key, '%s name error!' % warTagName)
                sys.exit()
            Redis.lpush(Message_key, '%s svn export success!' % warZipName)
            Redis.lpush(Message_key, '*' * 60)
        else:
            Redis.lpush(Message_key, '*' * 60)
            Redis.lpush(Message_key, '%s svn export fail !' % warZipName)
            Redis.lpush(Message_key, '*' * 60)
            sys.exit()
        return svnDir

    # 从git获取war包
    def git_up(project):
        warname = project.split('/')[-1]
        war_path = '%s%s' % (gitDir, warname)
        if not os.path.isdir(gitDir):
            os.system('mkdir -p %s' % gitDir)
        if os.path.exists(war_path):
            os.remove(war_path)
        gitCoCmd = 'cd {0} && /usr/bin/git clone http://{1}:{2}@{3}/{4}' % (
        gitDir, gitUser, gitPassword,gitUrl,project)
        os.system(gitCoCmd)
        if os.path.exists(war_path):
            Redis.lpush(Message_key, '%s git clone success!' % warZipName)
            Redis.lpush(Message_key, '*' * 60)
        else:
            Redis.lpush(Message_key, '*' * 60)
            Redis.lpush(Message_key, '%s git clone fail !' % warZipName)
            Redis.lpush(Message_key, '*' * 60)
            sys.exit()
        return war_path

    # 构造ssh连接
    def _init_ssh(ip, username):
        keyFile = '/home/' + username + '/.ssh/id_rsa'
        ssh = paramiko.SSHClient()
        key = paramiko.RSAKey.from_private_key_file(keyFile)
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(ip, 22, username, pkey=key, timeout=15)
        except Exception as e:
            Redis.lpush(Message_key, '*' * 60)
            Redis.lpush(Message_key, '%s %s login fail !' % (ip, username))
            Redis.lpush(Message_key, '*' * 60)
            sys.exit()
        return ssh

    def check_path(ssh, ip, username):
        # 获取jboss目录并备份旧war包
        cmd = 'cd /home/' + username + ' && ls |grep jboss-'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        jbossName = stdout.read()
        count = len(jbossName.strip().splitlines())
        if count == 1:
            basePath = '/home/%s/%s/server/default/deploy/' % (username, jbossName.strip())
            Redis.lpush(Message_key, 'check %s %s env ---> Pass' % (ip, username))
        else:
            Redis.lpush(Message_key, '*' * 60)
            Redis.lpush(Message_key, '%s -->jboss Directory just one!' % ip)
            Redis.lpush(Message_key, '*' * 60)
            sys.exit()
        return basePath

    def Restart_java(ssh, warZipName):
        cmd = '/usr/bin/pkill -9 java'
        try:
            for i in range(3):
                time.sleep(1)
                ssh.exec_command(cmd)
            ssh.close()
        except Exception as e:
            Redis.lpush(Message_key, 'Restart_java:{0}'.format(e))
            Redis.lpush(Message_key, '      %s --->restart fail ' % warZipName)
        else:
            Redis.lpush(Message_key, '      %s --->restart Success' % warZipName)
        Redis.lpush(Message_key, '*' * 60)

    def publish(warZipName, basePath, file_Dir, ssh):
        try:
            warTagName = warZipName.split('.zip')[0]
            scp = SCPClient(ssh.get_transport())
            Redis.lpush(Message_key, '      {0} --->publish start ......'.format(warZipName))
            Redis.lpush(Message_key, 'backup {0}{1}'.format(basePath, warName))
            cmds = ['/bin/mkdir -p {0}'.format(bakPath),
                    '/usr/bin/rsync -av --delete %s%s/ %s%s/' % (basePath, warName, bakPath, warName)]
            for cmd in cmds:
                try:
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    if stderr.read():
                        Redis.lpush(Message_key, cmd)
                        Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                except Exception as e:
                    Redis.lpush(Message_key, str(e))
                    sys.exit()
            try:
                Redis.lpush(Message_key, '      %s --->backup Success' % warName)
                Redis.lpush(Message_key, "copy {0} to {1}:{2}".format(warZipName, ip, username))
                scp.put('%s%s' % (file_Dir, warZipName), '%s%s' % (basePath, warZipName))
                Redis.lpush(Message_key, '      %s --->copy Success' % warZipName)
                Redis.lpush(Message_key, "unzip {0} ......".format(warZipName))
                cmd = "cd %s  &&  /usr/bin/unzip -qo %s" % (basePath, warZipName)
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if stderr.read():
                    Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                cmd = "[ -d {0}{1} ]  && echo True ".format(basePath, warTagName)
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if stderr.read():
                    Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                Msg_zip = stdout.read().strip()
                if Msg_zip == 'True':
                    Redis.lpush(Message_key, '      %s --->unzip Success' % warZipName)
                    Redis.lpush(Message_key, "rsync  {0} to {1}".format(warTagName, warName))
                    cmds = ["/bin/rm -rf {0}{1}".format(basePath, warName),
                            "/usr/bin/rsync -av  --delete {0}{1}/  {0}{2}/".format(basePath, warTagName, warName),
                            "/bin/rm -rf %s%s" % (basePath, warZipName), "/bin/rm -rf %s%s" % (basePath, warTagName)]
                    for cmd in cmds:
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                        if stderr.read():
                            Redis.lpush(Message_key, cmd)
                            Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                    cmd = "[ -d {0}{1} ]  && echo True ".format(basePath, warName)
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    if stderr.read():
                        Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                    Msg_sync = stdout.read().strip()
                    if Msg_sync == 'True':
                        Redis.lpush(Message_key, '      %s --->Publish Success' % warZipName)
                        Restart_java(ssh, warZipName)
                    else:
                        Redis.lpush(Message_key, '      %s --->rsync fail' % warName)
                        cmd = '/usr/bin/rsync -av --delete %s%s/ %s%s/' % (bakPath, warName, basePath, warName)
                        stdin, stdout, stderr = ssh.exec_command(cmd)
                        if stderr.read():
                            Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                        Redis.lpush(Message_key, '      %s --->Publish fail' % warZipName)
                        Redis.lpush(Message_key, '*' * 60)
                else:
                    Redis.lpush(Message_key, '      %s --->unzip fail' % warZipName)
            except Exception as e:
                cmd = '/usr/bin/rsync -av --delete %s%s/ %s%s/' % (bakPath, warName, basePath, warName)
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if stderr.read():
                    Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
                Redis.lpush(Message_key, '*' * 60)
                Redis.lpush(Message_key, str(e))
                Redis.lpush(Message_key, '*' * 60)
        except Exception as e:
            Redis.lpush(Message_key, 'publish:{0}'.format(e))
            sys.exit()

    def rollback(ssh, basePath, warName, warZipName):
        cmd = '/usr/bin/rsync -av --delete %s%s/ %s%s/' % (bakPath, warName, basePath, warName)
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            if stderr.read():
                Redis.lpush(Message_key, 'fail :{0}'.format(stderr.read()))
        except Exception as e:
            Redis.lpush(Message_key, str(e))
            Redis.lpush(Message_key, '         %s  --->rollback fail !' % warZipName)
        else:
            Redis.lpush(Message_key, '         %s --->rollback success!' % warZipName)
            Restart_java(ssh, warZipName)

    try:
        if Redis.exists(publish_key):
            INFO = Redis.rpop(publish_key)
            Redis.delete(publish_key)
            if INFO:
                INFO = eval(INFO)
                warZipName = INFO['warTagName']
                warName = INFO['warname']
                Action = INFO['Action']
                ServerList = INFO['ServerList']
                Gray = INFO['Gray']
                Way = INFO['Way']
                if Action == 'publish':
                    if Way == 'SVN':
                        file_Dir = svn_up(warZipName)
                    if Way == 'GIT':
                        file_Dir = git_up(warZipName)
                for ip,username in ServerList:
                    bakPath = '/home/%s/bak/'%username
                    ssh  = _init_ssh(ip,username)
                    basePath = check_path(ssh,ip,username)
                    time.sleep(3)
                    if Action == 'restart':
                        Restart_java(ssh,warZipName)
                    if Action == 'publish':
                        publish(warZipName,basePath,file_Dir,ssh)
                    if Action == 'rollback':
                        rollback(ssh,basePath,warName,warZipName)
                if Gray and Action == 'publish':
                    Redis.lpush(Message_key, '灰度发布信息:{0}   {1}'.format(ip, username))
                else:
                    cmd = "update java_list set Gray = '0' where project = '%s';" % warName
                    MYSQL.Run(cmd)
                    MYSQL.Close()
            else:
                Redis.lpush(Message_key, '没有获取到上线相关信息,请重试!')
    except Exception as e:
        Redis.lpush(Message_key,'main:{0}'.format(e))
    finally:
        Redis.lpush(Message_key,'_End_')
        Redis.expire(Message_key, 3600)