import requests

try:
    resp = requests.post(
        "http://localhost:8000/api/chat",
        json={"message": "Why is VEHICLE_007 marked as critical?"},
        timeout=30
    )
    print(resp.status_code, resp.json())
except Exception as e:
    print(e)
