import ast
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
import os
import json
from common import apIp, user, pwd, api_host_name, port_number

NOS_OPEN_API_PATH = "nos-openapi.yaml"

found_stats = False

routes = web.RouteTableDef()

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

config_cmd = ['telegraf ethernet stats vlan-counter enable',
              f'telegraf ethernet stats vlan-counter url http://{api_host_name}:{port_number}/v1',
              'telegraf ethernet stats vlan-counter flush-interval 10',
              'telegraf ethernet stats vlan-counter sample-interval 5',
        ]

show_cmd = ['show interface vlan counters',]

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


async def get_ap_vlan():
    print("===========Get AP Vlan Show Results==============")
    ssh_server = ShellConnect(apIp, 22, user, pwd)
    output = await ssh_server.execute(show_cmd)
    print("&&&&&&&&&&&&&&&&&")
    print(output)
    time.sleep(0.2)
    ssh_server.__del__()
    filename = apIp + "_ap_vlan_show.txt"
    with open (filename, "w") as f:
        # Write some text to the file
        f.write (output)       

def convert_value(value):
    try:
        return int(value)
    except ValueError:
        return value.strip()

def convert_cli_data(cli_data):
    for entry in cli_data:
        for key, value in entry.items():
            entry[key] = convert_value(value)
    return cli_data  

def are_almost_similar(value1, value2, tolerance=0.05):
    """
    Check if two values are almost similar within a given tolerance.
    """
    return abs(value1 - value2) <= tolerance * max(abs(value1), abs(value2))

def compare_cli_json(vlan_stats, vlan_data, tolerance=0.05):
    mismatches = []
    compared_keys = set()

    # Print vlan_stats from telegraf server output
    print("vlan_stats:", vlan_stats)

    # Print vlan_data from show command command
    print("vlan_data:", vlan_data)

    # Compare keys
    for key, json_value in vlan_stats['keys'].items():
        if key in vlan_data[0]:
            cli_value = vlan_data[0][key]
            compared_keys.add(key)
            if isinstance(json_value, int) and isinstance(cli_value, int):
                if not are_almost_similar(json_value, cli_value, tolerance):
                    mismatches.append((key, json_value, cli_value))
            elif json_value != cli_value:
                mismatches.append((key, json_value, cli_value))
        else:
            print(f"Key {key} not found in vlan_data")

    # Compare stats
    for key, json_value in vlan_stats['stats'].items():
        if isinstance(json_value, dict):  # Handle nested dictionaries
            for sub_key, sub_value in json_value.items():
                if sub_key in vlan_data[0]:
                    cli_value = vlan_data[0][sub_key]
                    compared_keys.add(sub_key)
                    if isinstance(sub_value, int) and isinstance(cli_value, int):
                        if not are_almost_similar(sub_value, cli_value, tolerance):
                            mismatches.append((sub_key, sub_value, cli_value))
                    elif sub_value != cli_value:
                        mismatches.append((sub_key, sub_value, cli_value))
                else:
                    print(f"Sub-key {sub_key} not found in vlan_data")
        else:
            if key in vlan_data[0]:
                cli_value = vlan_data[0][key]
                compared_keys.add(key)
                if isinstance(json_value, int) and isinstance(cli_value, int):
                    if not are_almost_similar(json_value, cli_value, tolerance):
                        mismatches.append((key, json_value, cli_value))
                elif json_value != cli_value:
                    mismatches.append((key, json_value, cli_value))

    # Compare errors
    if 'errors' in vlan_stats['stats']:
        for error_key, error_value in vlan_stats['stats']['errors'].items():
            if error_key in vlan_data[0]:
                cli_value = vlan_data[0][error_key]
                compared_keys.add(error_key)
                if isinstance(error_value, int) and isinstance(cli_value, int):
                    if not are_almost_similar(error_value, cli_value, tolerance):
                        mismatches.append((error_key, error_value, cli_value))
                elif error_value != cli_value:
                    mismatches.append((error_key, error_value, cli_value))
            else:
                print(f"Error key {error_key} not found in vlan_data")

    return mismatches, list(compared_keys)

def read_tgraf_server(records_file):
    try:
         # Read vlan stats Telegraf server's JSON file
         with open(records_file, 'r') as f:
             telegraf_data = json.load(f)
             vlan_stats = telegraf_data["ethernetInterfaceVlanStats"][0]["items"][0]
             return vlan_stats

    except Exception as e:
         print(f"Error reading Telegraf vlan stats from {records_file}: {e}")
         return None

async def compare_vlan_stats(records_file):
    global found_stats
    """
    Function to compare the vlan stats between the Telegraf server and AP vlan stats readings.
    """
    # Call read_tgraf_server to get vlan_stats
    vlan_stats = read_tgraf_server(records_file)
    if vlan_stats is None:
        return None
    
    try:
        # Read vlan stats cli file
        filename = f"{apIp}_ap_vlan_show.txt"
        with open(filename, 'r') as f:
            ap_data = f.readlines()
            header_index = 0
            for i, line in enumerate(ap_data):
                if line.startswith("ifIndex"):
                    header_index = i
                    break
            keys = ap_data[header_index].strip().split()
    
            # Extract the data lines
            data_lines = ap_data[header_index + 4:header_index + 5]  # Adjust the range as needed
            
            # Parse the data lines into a list of dictionaries
            vlan_data = []
            for line in data_lines:
                values = line.strip().split()
                vlan_data.append(dict(zip(keys, values)))
    
        vlan_data = convert_cli_data(vlan_data)
        if vlan_data == [{}]:
            assert found_stats, "No data from show command" 

        # Compare key-value pairs
        mismatches, compared_keys = compare_cli_json(vlan_stats, vlan_data, tolerance=0.05)

        # Print compared keys
        print("\nKeys that have been compared:")
        print(compared_keys)
        
        # Print mismatches
        if mismatches:
            print("Mismatches found:")
            for mismatch in mismatches:
                print(f"Key: {mismatch[0]}, JSON value: {mismatch[1]}, CLI value: {mismatch[2]}")
            assert found_stats, "Mismatch found in cli and json values."    

        else:
            print("All key-value pairs match within the tolerance.")
            found_stats = True
    except Exception as e:
        # print(f"Error reading AP vlan show results: {e}")
        assert found_stats, f"Error : {e}"
        return None
    
async def test_post():

    remove_old_files()
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("EthernetInterfaceStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'EthernetInterfaceStatsCallbackElement'"

    await configure_ap_telegraf()
    
    process = subprocess.Popen(['python','server.py'], start_new_session=True)
    await asyncio.sleep(20)
    
    process.terminate()

    await get_ap_vlan()

    global found_stats  
    found_stats = False

    last_json_with_tag = common_m.find_last_json_with_tag("ethernetInterfaceVlanStats")
    if last_json_with_tag:
        print("Found the last JSON with ethernetInterfaceVlanStats tag in:", last_json_with_tag)
        with open(last_json_with_tag) as f:
            obj = json.load(f)
            validation = common_m.validate_object_spec(stats_element_spec, obj["ethernetInterfaceVlanStats"][0], "EthernetInterfaceStatsCallbackElement", schemas_spec)
            assert validation is None, f"{validation}"
            await compare_vlan_stats(last_json_with_tag)
            
    else:
        # print("No JSON file contains the specified tag.") 
        assert found_stats, "No JSON file contains the specified tag."