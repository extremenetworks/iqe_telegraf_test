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

NOS_OPEN_API_PATH = "nos-openapi.yaml"
apIp = '10.234.102.78'
user = 'admin'
pwd = 'Aerohive123'

config_cmd = ['telegraf platform stats memory enable',
              'telegraf platform stats url http://134.141.203.60:9000/v1',
              'telegraf platform stats flush-interval 10',
              'telegraf platform stats memory sample-count 3',
              'telegraf platform stats memory sample-interval 5',
              ]

show_cmd = ['_show telegraf platform stats memory', ]

show_stats_file = apIp + "_ap_memory_show.txt"

def get_latest_stats_file():
    cwd = os.getcwd()
    files = os.listdir(cwd)
    stats_file = [f for f in files if os.path.isfile(f) and f.startswith('telegraf_stats_mem')]
    stats_file.sort()
    print(f'The latest memory stats file is: {stats_file[-1]}')
    return stats_file[-1]


def remove_old_files():
    fileList = glob.glob('*.json', recursive=True)

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


def run_remote_command(ssh, cmd, timeout, waitForResult=True):
    flag = 0

    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        if waitForResult:
            out = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
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
            await asyncio.sleep(1)
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
    await asyncio.sleep(2)
    output = await ssh_server.execute(show_cmd)
    print("&&&&&&&&&&&&&&&&&")
    print(output)
    time.sleep(0.2)
    await ssh_server.execute(['no telegraf platform stats memory enable'])
    ssh_server.__del__()
    with open(show_stats_file, "w") as f:
        f.write(output)

async def test_post():

    remove_old_files()
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("MemoryStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'MemoryStatsCallbackElement'"

    await configure_ap_telegraf()

    process = subprocess.Popen(['python', 'server.py'], start_new_session=True)
    await asyncio.sleep(60)
    process.terminate()
    await get_ap_cpu()

    found_stats = False
    records_file = get_latest_stats_file()
    with open(records_file) as f:
        obj = json.load(f)
        validation = common_m.validate_object_spec(stats_element_spec, obj["memoryStats"][0], "MemoryStatsCallbackElement",
                                                   schemas_spec)
        assert validation is None, f"{validation}"
        found_stats = True

    with open(show_stats_file, 'r') as f:
        mem_stats_shown = f.read().split('\n')[14].split('\t')
        print(mem_stats_shown)
        mem_stats_telegraf = [obj['memoryStats'][-1]['items'][0]['usage']['min'],
                              obj['memoryStats'][-1]['items'][0]['usage']['max'],
                              obj['memoryStats'][-1]['items'][0]['usage']['avg']]
        print(mem_stats_telegraf)

    assert found_stats