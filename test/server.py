import asyncio
from aiohttp import web
import json
import paramiko
import traceback

records_file = "telegraf_stats_cpu"
number = 1

routes = web.RouteTableDef()

@routes.post('/v1')
async def post_stats(request):
    global number
    data = await request.json()
    print(data)
    with open(records_file + str(number) + '.json', 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print("\n\n")
    number += 1
    if(number>=10): number = 1
    return web.Response(text=f"new stats {number-1} was added")

'''
@routes.post('/v1')
async def post_stats(request):
    data = await request.json()
    print(data)
    with open(records_file, 'w') as json_file:
        json.dump(data, json_file, indent=4)
    print("\n\n")
    return web.Response(text=f"new stats was added")

@routes.post('/stats')
async def add_stats(request: web.Request) -> web.Response:
    data = await request.json()
    print(data)
    return web.Response(text=f"new stats was added")

async def init_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app
'''
def init_app():
    app = web.Application()
    app.add_routes(routes)
    return app

def open_ap_ssh_connection(apIp, user, password, timeout=60):
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
              'telegraf platform stats cpu flush-interval 10'
              'telegraf platform stats cpu sample-count 2',
              'telegraf platform stats cpu sample-interval 5',
             ]

show_cmd = "_show report snapshot system"

def run_remote_command(ssh, cmd, timeout, waitForResult=True):
    flag = 0

    try:
        transport = ssh.get_transport()
        channel = transport.open_session()
        stdin, stdout, stderr = ssh.exec_command(cmd , timeout=timeout)
        if waitForResult:
            out = stdout.read().decode().strip()
            print("out", out)
            error = stderr.read().decode().strip()
            print("error", error)
            stdout.flush()
            if error:
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

def get_ap_cpu():
    print("===========Get AP CPU Show Results==============")

    ssh1 = open_ap_ssh_connection(apIp, user, pwd)
    if ssh1 != None:
        flag, result = run_remote_command(ssh1, show_cmd, 30)
        print(" 1---", result)
        ssh1.close()
        filename = apIp + "_ap_cpu_show.txt"
        with open (filename, "w") as f:
            f.write (result)    
    else:
        print("ssh failed")


web.run_app(init_app(), host='134.141.244.62', port=9000)