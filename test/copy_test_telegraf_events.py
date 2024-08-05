import pytest
import common as common_m
import bootchecks
import productenv
import time
import os
import warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import subprocess
import json

api_host_name = os.environ.get('API_HOST') or 'localhost'
port_number = 8000
access_token = '33Tt32v0DsJ6Rph013baoStUFgeWouJGN3GIQny5evhlWXiRf8GcvT3uGWEKEPKP'

empty_subscription = {
        'stats': [
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }

def apply_subscription(subscription):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/configuration', data=json.dumps(subscription), verify=False)
        assert r.status_code == 200, f"PUT /api/telemetry/v0/subscription/configuration returned {r.status_code}, expected 200"

def apply_subscription_events(subscription):
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/events/platform', data=json.dumps(subscription), verify=False)
        assert r.status_code == 200, f"PUT /api/telemetry/v0/subscription/events/platform returned {r.status_code}, expected 200"

        r = requests.request(method='GET', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/subscription/events/platform', verify=False)
        assert r.status_code == 200, f"GET /api/telemetry/v0/subscription/events/platform returned {r.status_code}, expected 200"
        body = r.json()
        assert body == subscription, f"Response doesn't match request: '{body}' != {subscription}"

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_bootchecks_fresh_install():
    r = common_m.get_redis_conn()
    pubsub = r.pubsub()
    pubsub.subscribe(
        [
            "telegraf:reboot",
            "telegraf:upgrade",
        ]
    )

    r.delete(bootchecks.redis_version_key)

    bootchecks.check_version()

    for i in range(10):
        message = pubsub.get_message(ignore_subscribe_messages=True)
        assert message is None
        time.sleep(1)

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_bootchecks_upgrade():
    r = common_m.get_redis_conn()
    pubsub1 = r.pubsub()
    pubsub1.subscribe(
        [
            "telegraf:upgrade",
        ]
    )
    pubsub2 = r.pubsub()
    pubsub2.subscribe(
        [
            "telegraf:reboot",
        ]
    )
    r.set(bootchecks.redis_version_key, "0.0.0.0")

    bootchecks.check_version()

    found = False
    for i in range(10):
        message = pubsub1.get_message(ignore_subscribe_messages=True)
        if message is not None:
            assert "0.0.0.0" in message["data"].decode("utf-8")
            found = True
        time.sleep(1)
    assert found

    found = False
    for i in range(10):
        message = pubsub2.get_message(ignore_subscribe_messages=True)
        if message is not None:
            assert "Upgrade" in message["data"].decode("utf-8")
            found = True
        time.sleep(1)
    assert found

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_bootchecks_reboot():
    r = common_m.get_redis_conn()
    pubsub1 = r.pubsub()
    pubsub1.subscribe(
        [
            "telegraf:upgrade",
        ]
    )
    pubsub2 = r.pubsub()
    pubsub2.subscribe(
        [
            "telegraf:reboot",
        ]
    )
    pe = productenv.read_product_env()
    version = pe.get("productVersion", "latest")
    r.set(bootchecks.redis_version_key, version)

    bootchecks.check_version()

    for i in range(10):
        message = pubsub1.get_message(ignore_subscribe_messages=True)
        assert message is None
        time.sleep(1)

    found = False
    for i in range(10):
        message = pubsub2.get_message(ignore_subscribe_messages=True)
        if message is not None:
            assert "Unknown" in message["data"].decode("utf-8")
            found = True
        time.sleep(1)
    assert found

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_successful_login_no_event():
    login = {
        "id": "admin",
        "password": "abc123",
    }

    r = common_m.get_redis_conn()
    pubsub1 = r.pubsub()
    pubsub1.subscribe(
        [
            "telegraf:login",
        ]
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='POST', url=f'https://{api_host_name}:5825/v1/login/local', params=login, json=login, verify=False)
    assert r.status_code == 200, f"PUT /v1/login/ returned {r.status_code}, expected 200 when passing correct login info."

    found = False
    for i in range(10):
        message = pubsub1.get_message(ignore_subscribe_messages=True)
        if message is not None:
            assert "Login failed due to invalid password" in message["data"].decode("utf-8")
            found = True
        time.sleep(1)
    assert not found

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_failed_login_event():
    login = {
        "id": "admin",
        "password": "incorrect",
    }

    r = common_m.get_redis_conn()
    pubsub1 = r.pubsub()
    pubsub1.subscribe(
        [
            "telegraf:login",
        ]
    )

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='POST', url=f'https://{api_host_name}:5825/v1/login/local', params=login, json=login, verify=False)
    assert r.status_code == 401, f"PUT /v1/login/ returned {r.status_code}, expected 401 when passing incorrect login info."

    found = False
    for i in range(10):
        message = pubsub1.get_message(ignore_subscribe_messages=True)
        if message is not None:
            assert "Login failed due to invalid password" in message["data"].decode("utf-8")
            found = True
        time.sleep(1)
    assert found

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_upgrade_event_send():
    subscription = {
        'enableStats': False,
        'enableEvents': True,
        'accessToken': access_token
    }
    apply_subscription(subscription)

    p = subprocess.Popen(["/vagrant/test/telegraf_test_server.py", "_events_upgrade"])

    management_config = {
        "mode": "Cloud"
    }
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/v1/config/management',
                             data=json.dumps(management_config), verify=False)
    assert r.status_code == 200, f"PUT /v1/config/management returned {r.status_code}, expected 200"

    subscription = {
        'events': [
            {
                'type': 'UpgradeEvent',
                'sampleCount': 3,
                'samplePeriod': 1
            }
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_events(subscription)

    r = common_m.get_redis_conn()
    r.set(bootchecks.redis_version_key, "0.0.0.0")

    bootchecks.check_version()

    found_stats = False
    for _ in range(40):
        try:
            r.set(bootchecks.redis_version_key, "0.0.0.0")
            bootchecks.check_version()

            with open('/tmp/telegraf_records_events_upgrade') as f:
                found_records = f.readlines()
                for record in found_records:
                    if "UpgradeEvent" in record:
                        found_stats = True
                        break
            if found_stats:
                break
            time.sleep(1)
        except FileNotFoundError:
            time.sleep(1)

    p.terminate()

    assert found_stats, f"Found no UpgradeEvent records written by telegraf, expected at least one"

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_reboot_event_send():
    subscription = {
        'enableStats': False,
        'enableEvents': True,
        'accessToken': access_token
    }
    apply_subscription(subscription)

    p = subprocess.Popen(["/vagrant/test/telegraf_test_server.py", "_events_reboot"])

    management_config = {
        "mode": "Cloud"
    }
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", category=InsecureRequestWarning)
        r = requests.request(method='PUT', url=f'http://{api_host_name}:{port_number}/v1/config/management',
                             data=json.dumps(management_config), verify=False)
    assert r.status_code == 200, f"PUT /v1/config/management returned {r.status_code}, expected 200"

    subscription = {
        'events': [
            {
                'type': 'RebootEvent',
                'sampleCount': 3,
                'samplePeriod': 1
            }
        ],
        'callbackUrl': 'http://127.0.0.1:8081/platform',
        'flushInterval': 1
    }
    apply_subscription_events(subscription)

    r = common_m.get_redis_conn()
    pe = productenv.read_product_env()
    version = pe.get("productVersion", "latest")
    r.set(bootchecks.redis_version_key, version)

    bootchecks.check_version()

    found_stats = False
    for _ in range(40):
        try:
            bootchecks.check_version()

            with open('/tmp/telegraf_records_events_reboot') as f:
                found_records = f.readlines()
                for record in found_records:
                    if "RebootEvent" in record:
                        found_stats = True
                        break
            if found_stats:
                break
            time.sleep(1)
        except FileNotFoundError:
            time.sleep(1)

    p.terminate()

    assert found_stats, f"Found no RebootEvent records written by telegraf, expected at least one"
