import asyncio
from nlp.rag_engine import rag_engine

async def main():
    ctx = rag_engine._retrieve_telemetry_context("VEHICLE_007")
    print("Context retrieved:")
    print(ctx)
    print("Vehicle ID extracted:")
    print(rag_engine._extract_vehicle_id("Why is VEHICLE_007 marked as critical?"))

asyncio.run(main())
