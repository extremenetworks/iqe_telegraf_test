import warnings
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import os
import json
import pytest

api_host_name = os.environ.get('API_HOST') or 'localhost'
port_number = 8000
RETRY_COUNT = 6

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_state_system():
    with warnings.catch_warnings(record=True):
        r = requests.request(method='GET', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/state/system', verify=False)
        assert r.status_code == 200, f"GET /api/telemetry/v0/state/system returned {r.status_code}, expected 200"
        body = r.json()
        assert not body['isDigitalTwin']
        assert 'sysDescription' in body
        assert 'sysName' in body

@pytest.mark.dependency(depends=['test_0license.py::test_upload_license_file'], scope='session')
def test_state_system_components():
    with warnings.catch_warnings(record=True):
        r = requests.request(method='GET', url=f'http://{api_host_name}:{port_number}/api/telemetry/v0/state/system/components', verify=False)
        assert r.status_code == 200, f"GET /api/telemetry/v0/state/system/components returned {r.status_code}, expected 200"
        body = r.json()
        assert 'urls' in body
        for url in body['urls']:
            assert len(url['url']) > 0, "URL is empty"
            assert len(url['supportedOps']) > 0, "Supported operatins are empty"
