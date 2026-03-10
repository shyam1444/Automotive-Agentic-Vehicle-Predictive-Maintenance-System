from clickhouse_driver import Client
import os
client = Client(host=os.getenv("CLICKHOUSE_HOST", "localhost"), port=int(os.getenv("CLICKHOUSE_PORT", "9000")), user=os.getenv("CLICKHOUSE_USER", "default"), password=os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass"), database=os.getenv("CLICKHOUSE_DATABASE", "telemetry_db"))
res = client.execute("SELECT DISTINCT vehicle_id FROM telemetry LIMIT 20")
print("Available vehicles:", res)
