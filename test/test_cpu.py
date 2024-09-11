import time
import pytest
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import json
import subprocess
import os, glob
import paramiko
import common as common_m
import yaml
import traceback

records_file = "telegraf_stats_cpu1.json"
NOS_OPEN_API_PATH = "nos-openapi.yaml"

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

apIp = '10.234.102.78'
user = 'admin'
pwd = 'Aerohive123'
config_cmd = ['telegraf platform stats cpu enable',
              'telegraf platform stats url http://134.141.244.62:9000/v1',
              'telegraf platform stats flush-interval 10',
              'telegraf platform stats cpu sample-count 3',
              'telegraf platform stats cpu sample-interval 5',
          ]

show_cmd = ['_show report snapshot system',]

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

class ShellConnect:
    def __init__(self, hostname, port, username, password, ):
        self.__ssh = None
        self.__received = ('', '', '')  # stdin, stdout, stderr
        self.__output = ''
        try:
            self.__ssh = paramiko.SSHClient()
            self.__ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.__ssh.connect(hostname=hostname, port=port, username=username, password=password)
            print('Connected to {}'.format(hostname))
        except paramiko.AuthenticationException:
            print('Failed to connect to {} due to wrong username/password'.format(hostname))
        except:
            print('Failed to connect to {}'.format(hostname))

    def __del__(self):
        self.__ssh.close()

    @property
    def getRcv(self):
        return self.__output

    async def execute(self, command_list):
        ch = self.__ssh.invoke_shell(term='vt100', width=80, height=24, width_pixels=0, height_pixels=0,
                                     environment=None)

        out = ""
        for command in command_list:
            cmd = command.strip('\n')
            print(cmd)
            ch.send(cmd + '\n')
            while not ch.recv_ready():
                await asyncio.sleep(3)
            out += ch.recv(1024).decode()
        return out

async def configure_ap_telegraf():
    print("=========== Configure Telegraf==============")
    ssh_server = ShellConnect(apIp, 22, user, pwd)

    result = await ssh_server.execute(config_cmd)
    print("result", result)
    time.sleep(0.2)
    ssh_server.__del__()


async def get_ap_cpu():
    print("===========Get AP CPU Show Results==============")
    ssh_server = ShellConnect(apIp, 22, user, pwd)
    output = await ssh_server.execute(show_cmd)
    print("&&&&&&&&&&&&&&&&&")
    print(output)
    time.sleep(0.2)
    ssh_server.__del__()
    filename = apIp + "_ap_cpu_show.txt"
    with open (filename, "w") as f:
        # Write some text to the file
        f.write (output)       
    
'''
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
'''

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
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("CpuStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'CpuStatsCallbackElement'"

    await configure_ap_telegraf()
    
    process = subprocess.Popen(['python','server.py'], start_new_session=True)
    await asyncio.sleep(20)
    
    process.terminate()
    #await get_ap_cpu()

    found_stats = False
    with open(records_file) as f:
        obj = json.load(f)
        validation = common_m.validate_object_spec(stats_element_spec, obj["cpuStats"][0], "CpuStatsCallbackElement", schemas_spec)
        assert validation is None, f"{validation}"
        found_stats = True

    #Need to compare telegraf server's results with AP CPU readings
    #telegraf server saved received cpu stats in telegraf_stats_cpu*.json,
    #and AP CPU reading was saved in <apIp>_ap_cpu_show.txt.
    #assert "CPU usage in telegraf server" == "CPU usage in AP CPU reading"   
       
    assert found_stats

