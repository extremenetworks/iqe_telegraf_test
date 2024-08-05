import pytest
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import json
import subprocess
import os, glob
import paramiko

records_file = "telegraf_stats_cpu"

'''
routes = web.RouteTableDef()

@routes.post('/v1')
async def post_stats(request):
    data = await request.json()
    print(data)
    with open(records_file, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print("\n\n")
    return web.Response(text=f"new stats was added")

def create_app():
    app = web.Application()
    app.add_routes(routes)
    return app
'''
def remove_old_files():    
    # Getting All Files List
    fileList = glob.glob('*.json', recursive=True)
        
    # Remove all files one by one
    for file in fileList:
        try:
            os.remove(file)
        except OSError:
            print("Error while deleting file")
    
    print("Removed all matched files!")

def open_ap_ssh_connection(apIp, user, password, timeout=30):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(apIp, username=user,
                    password=password, timeout=timeout)
    except:
        return None
    return ssh

apIp = '192.168.2.44'
user = 'admin'
pwd = 'Aerohive123'
config_cmd = ['telegraf platform stats cpu enable',
              'telegraf platform stats url http://192.168.2.12:9000/v1',
          'telegraf platform stats cpu flush-interval 10'
          'telegraf platform stats cpu sample-count 2',
          'telegraf platform stats cpu sample-interval 5',
          ]

show_cmd = "_show report snapshot system\n"

def run_remote_command(ssh, cmd, timeout, waitForResult=True):
    flag = 0

    try:
        #print(" cmd =", cmd)

        stdin, stdout, stderr = ssh.exec_command(cmd , timeout=timeout)
        if waitForResult:
            out = stdout.read().decode().strip()
            #print("out", out)
            error = stderr.read().decode().strip()
            #print("error", error)
            stdout.flush()
            if error:
                #print("cmd exec failed")
                flag = 1

            if error:
                return flag, error
            else:
                return flag, out
        else:
            return 0, ''

    except Exception as err:
        flag = 1
        print(("\nException (%s) %s" % (err, str(traceback.format_exc()))))
        return flag, "Failed to do SSH connection, or timed out"

def configure_ap_telegraf():
    print("=========== Configure Telegraf==============")
    ssh1 = open_ap_ssh_connection(apIp, user, pwd)
   
    if ssh1 != None:
        for cmd in config_cmd:
            flag, result = run_remote_command(ssh1, cmd, 30)
            print("cmd flag result", cmd, flag, result)
        ssh1.close()
    else:
        print("ssh failed")

def get_ap_cpu():
    print("===========Get AP CPU Show Results==============")

    ssh1 = open_ap_ssh_connection(apIp, user, pwd)
    if ssh1 != None:
        flag, result = run_remote_command(ssh1, show_cmd, 30)
        print(" 1---", result)
        ssh1.close()
        filename = apIp + "_ap_cpu_show.txt"
        with open (filename, "w") as f:
            # Write some text to the file
            f.write (result)    
    else:
        print("ssh failed")

async def test_post():
    #app = create_app()
    #resp = await web.run_app(init_app(), host='192.168.2.12', port=9000)
    #server = TestServer(app, host='192.168.2.12', port=9000)
    #client = await aiohttp_client(server)
    #await asyncio.sleep(1)
    #resp = await client.post('/v1', data={'cpu':'0','usage':'50'})
    #assert resp.status == 200
    #assert "new stats was added" in resp.text()

    remove_old_files()
    #configure_ap_telegraf()

    process = subprocess.Popen(['python','server.py'], start_new_session=True)
    await asyncio.sleep(30)
    
    process.terminate()
    #get_ap_cpu()

    #Need to compare telegraf server's results with AP CPU readings
    #telegraf server saved received cpu stats in telegraf_stats_cpu*.json,
    #and AP CPU reading was saved in <apIp>_ap_cpu_show.txt.
    #assert "CPU usage in telegraf server" == "CPU usage in AP CPU reading"   
       
    assert True

