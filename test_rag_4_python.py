import asyncio
from nlp.rag_engine import rag_engine

async def main():
    ctx = rag_engine._retrieve_telemetry_context("VEHICLE_005")
    print("VEHICLE_005 logic:\n", ctx)
    is_fleet = rag_engine._is_fleet_query("tell me what all vehicles are not critical")
    print("Is fleet:", is_fleet)
    fleet_ctx = rag_engine._retrieve_fleet_context()
    print("Fleet logic:\n", fleet_ctx[:200])

asyncio.run(main())
