import pytest
import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

s = requests.Session()
retries = Retry(total=3,
                backoff_factor=0.1,
                status_forcelist=[ 500, 502, 503, 504 ])
s.mount('http://', HTTPAdapter(max_retries=retries))


def test_timeout_with_retry():
    
    with pytest.raises(requests.exceptions.ConnectionError):
        s.get('http://httpbin.org/delay/5', timeout=3)

def test_timeout_without_retry():

    with pytest.raises(requests.exceptions.Timeout):
        requests.get('http://httpbin.org/delay/5', timeout=3)