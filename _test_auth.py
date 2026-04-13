import sys, os, json, requests
sys.path.insert(0, os.path.join('.kiro','skills','oms-query','scripts'))
from oms_query_engine.config import EngineConfig

config = EngineConfig()
url = f"{config.base_url}/api/linker-oms/opc/iam/token"
payload = {
    "grantType": "password",
    "username": config.username,
    "password": config.password,
}

# Try auth 3 times
for i in range(3):
    resp = requests.post(url, json=payload, timeout=30)
    body = resp.json()
    data = body.get("data")
    print(f"Attempt {i+1}: status={resp.status_code}, data is None={data is None}")
    if data:
        print(f"  access_token present: {'access_token' in data}")
    else:
        print(f"  full response: {json.dumps(body, ensure_ascii=False)[:300]}")
