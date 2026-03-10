import requests

try:
    resp = requests.post(
        "http://localhost:8000/api/chat",
        json={"message": "tell me about VEHICLE_007"},
        timeout=30
    )
    print("1:", resp.json())
    sess = resp.json()["session_id"]
    
    resp2 = requests.post(
        "http://localhost:8000/api/chat",
        json={"message": "ok, now tell me about VEHICLE_008", "session_id": sess},
        timeout=30
    )
    print("2:", resp2.json())
except Exception as e:
    print(e)
