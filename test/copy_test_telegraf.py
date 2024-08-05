import warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os
import json
import pytest
import time
import memorystats
import subprocess
import common as common_m
import yaml

api_host_name = os.environ.get('API_HOST') or 'localhost'
port_number = 8000
RETRY_COUNT = 6
telegraf_config_file = '/etc/telegraf/telegraf.conf'
access_token = '33Tt32v0DsJ6Rph013baoStUFgeWouJGN3GIQny5evhlWXiRf8GcvT3uGWEKEPKP'
NOS_OPEN_API_PATH = "nos-openapi.yaml"

def apply_subscription(subscription):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/configuration', data=json.dumps(subscription), verify=False)
        assert r.status_code == 200, f"PUT /api/telemetry/v0/subscription/configuration returned {r.status_code}, expected 200"

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_enable_subscription():
    subscription = {
        'enableStats': True,
        'enableEvents': True,
        'accessToken': access_token
    }
    apply_subscription(subscription)

def get_telegraf_cfg():
    lines = []
    with open(telegraf_config_file, 'r') as cfg:
        for line in cfg:
            lines.append(line.strip())
    return lines

def apply_subscription_stats_interface(subscription):
    apply_subscription_stats('interface', subscription)

def clear_subscription_stats_interface():
    subscription = {
        'stats': [
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_stats('interface', subscription)

def apply_subscription_stats_platform(subscription):
    apply_subscription_stats('platform', subscription)

def clear_subscription_stats_platform():
    subscription = {
        'stats': [
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_stats('platform', subscription)

def apply_subscription_stats(module, subscription):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/stats/{module}', data=json.dumps(subscription), verify=False)
        assert r.status_code == 200, f"PUT /api/telemetry/v0/subscription/stats/{module} returned {r.status_code}, expected 200"

        r = requests.request(method='GET', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/stats/{module}', verify=False)
        assert r.status_code == 200, f"GET /api/telemetry/v0/subscription/stats/{module} returned {r.status_code}, expected 200"
        body = r.json()
        assert body == subscription, f"Response doesn't match request: '{body}' != {subscription}"

def check_telegraf_config_file(required, not_required):
    time.sleep(5) # Should be enough for telegraf service to update config asynchronously
    lines = get_telegraf_cfg()
    for line in lines:
        assert line not in not_required, f"Unexpected line in config file: {line}"
        if line in required:
            required.remove(line)
    assert len(required) == 0, f"Config file missing lines: {required}"

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_memory_usage():
    line_protocol = 'MemoryStats,serialnumber=TC012322E-V7U0R '
    sample_count = 3
    m = memorystats.MemoryStats(sample_count, 0)
    metric = m.get_line_metric()
    assert metric is not None, "Empty line protocol when metrics available"
    assert metric[:len(line_protocol)] == line_protocol, "Wrong metric prefix"
    values = metric[len(line_protocol):].split(',')
    params = set()
    for value in values:
        params.add(value.split('=')[0])
    assert len(params) == 3, f"Expected 3 params (usage_min, usage_max, usage_avg), got {params}"
    assert "usage_min" in params, "usage_min not foind in the telegraf line protocol"
    assert "usage_max" in params, "usage_max not foind in the telegraf line protocol"
    assert "usage_avg" in params, "usage_avg not foind in the telegraf line protocol"

    usage_min, usage_max, usage_avg = m.get_metrics()
    assert usage_min == usage_max, "Different usage min and max for single collection"
    assert usage_min == usage_avg, "Different usage min and avg for single collection"
    assert usage_min < 100 and usage_min > 0, f"Usage min isout of reasonable range: {usage_min}, expect between 0 and 100 (non-inclusive)"
    assert len(m.usage) == 1, "Single collection must provide single entry"
    for _ in range(sample_count + 2):
        m.collect()
    assert len(m.usage) == sample_count, f"Number of entries {len(m.usage)} is not equal to sample_count {sample_count}"
    
# curl -X PUT -d '{"enableStats": true, "accessToken": "abc123"}' http://localhost:8000/api/telemetry/v0/subscription/configuration
# curl -X PUT -d '{"stats": [{"type": "EthernetInterfaceStats"}], "sampleCount": 3, "samplePeriod": 5, "callbackUrl": "http://192.168.8.6:8000/v1/stats", "flushInterval": 10}' http://localhost:8000/api/telemetry/v0/subscription/stats/interface

def test_cpu_stats_send():
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("CpuStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'CpuStatsCallbackElement'"

    p = subprocess.Popen(["/vagrant/test/telegraf_test_server.py", "_cpu"])

    subscription = {
        'enableStats': True,
        'enableEvents': False,
        'accessToken': access_token
    }
    apply_subscription(subscription)

    management_config = {
        "mode": "Cloud"
    }
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/v1/config/management',
                             data=json.dumps(management_config), verify=False)
    assert r.status_code == 200, f"PUT /v1/config/management returned {r.status_code}, expected 200"

    subscription = {
        'stats': [
            {
                'type': 'CpuStats',
                'sampleCount': 3,
                'samplePeriod': 1
            }
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_stats_platform(subscription)

    found_stats = False
    for _ in range(20):
        try:
            with open('/tmp/telegraf_records_cpu') as f:
                found_records = f.readlines()
                for record in found_records:
                    if "CpuStats" in record:
                        obj = json.loads(record)
                        validation = common_m.validate_object_spec(stats_element_spec, obj["cpuStats"][0], "CpuStatsCallbackElement", schemas_spec)
                        assert validation is None, f"{validation}, record={record}"
                        found_stats = True
                        break
            if found_stats:
                break
            time.sleep(1)
        except FileNotFoundError:
            time.sleep(1)

    p.terminate()

    assert found_stats, f"Found no CpuStats records written by telegraf, expected at least one"
    clear_subscription_stats_platform()

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_memory_stats_send():
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("MemoryStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'MemoryStatsCallbackElement'"

    p = subprocess.Popen(["/vagrant/test/telegraf_test_server.py", "_memory"])

    subscription = {
        'enableStats': True,
        'enableEvents': False,
        'accessToken': access_token
    }
    apply_subscription(subscription)

    management_config = {
        "mode": "Cloud"
    }
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/v1/config/management',
                             data=json.dumps(management_config), verify=False)
    assert r.status_code == 200, f"PUT /v1/config/management returned {r.status_code}, expected 200"

    subscription = {
        'stats': [
            {
                'type': 'MemoryStats',
                'sampleCount': 3,
                'samplePeriod': 1
            }
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_stats_platform(subscription)

    found_stats = False
    for _ in range(40):
        try:
            with open('/tmp/telegraf_records_memory') as f:
                found_records = f.readlines()
                for record in found_records:
                    if "MemoryStats" in record:
                        obj = json.loads(record)
                        validation = common_m.validate_object_spec(stats_element_spec, obj["memoryStats"][0], "MemoryStatsCallbackElement", schemas_spec)
                        assert validation is None, f"{validation}, record={record}"
                        found_stats = True
                        break
            if found_stats:
                break
            time.sleep(1)
        except FileNotFoundError:
            time.sleep(1)

    p.terminate()

    assert found_stats, f"Found no MemoryStats records written by telegraf, expected at least one"
    clear_subscription_stats_platform()

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_ethernet_interface_stats_send():
    with open(NOS_OPEN_API_PATH, "r") as stream:
        openapi_spec = yaml.safe_load(stream)
        schemas_spec = openapi_spec.get("components", {}).get("schemas", {})
        assert schemas_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'components/schemas'"
        stats_element_spec = schemas_spec.get("EthernetInterfaceStatsCallbackElement", {})
        assert stats_element_spec != {}, f"Cannot load OpenAPI spec for validating requests. Loaded spec missing 'MemoryStatsCallbackElement'"

    p = subprocess.Popen(["/vagrant/test/telegraf_test_server.py", "_ethernet"])

    subscription = {
        'enableStats': True,
        'enableEvents': False,
        'accessToken': access_token
    }
    apply_subscription(subscription)

    management_config = {
        "mode": "Cloud"
    }
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/v1/config/management',
                             data=json.dumps(management_config), verify=False)
    assert r.status_code == 200, f"PUT /v1/config/management returned {r.status_code}, expected 200"

    subscription = {
        'stats': [
            {
                'type': 'EthernetInterfaceStats',
                'sampleCount': 3,
                'samplePeriod': 1
            }
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_stats_interface(subscription)

    found_stats = False
    for _ in range(40):
        try:
            with open('/tmp/telegraf_records_ethernet') as f:
                found_records = f.readlines()
                for record in found_records:
                    if "EthernetInterfaceStats" in record:
                        obj = json.loads(record)
                        validation = common_m.validate_object_spec(stats_element_spec, obj["ethernetInterfaceStats"][0], "EthernetInterfaceStatsCallbackElement", schemas_spec)
                        assert validation is None, f"{validation}, record={record}"
                        found_stats = True
                        break
            if found_stats:
                break
            time.sleep(1)
        except FileNotFoundError:
            time.sleep(1)

    p.terminate()

    assert found_stats, f"Found no EthernetInterfaceStats records written by telegraf, expected at least one"
    clear_subscription_stats_interface()
