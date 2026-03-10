import requests
import json
import time

url = "http://localhost:8000/api/chat"
headers = {"Content-Type": "application/json"}

print("Test 1: Global fleet query")
res1 = requests.post(url, json={"message": "can you tell what all VEHICLES are not critical"}, headers=headers)
print("Response 1:", res1.json().get('response', res1.text))
sess = res1.json().get('session_id')
time.sleep(2)

print("\nTest 2: Specific vehicle query (follow up)")
res2 = requests.post(url, json={"message": "tell about vehicle_005", "session_id": sess}, headers=headers)
print("Response 2:", res2.json().get('response', res2.text))
