import asyncio
from nlp.rag_engine import rag_engine

async def main():
    q = "Previous messages:\nuser: Why is VEHICLE_007 marked as critical?\nassistant: The engine temperature is above 110°C.\n\nNew query: tell me about VEHICLE_008"
    print("Vehicle extracted from memory-augmented query:")
    print(rag_engine._extract_vehicle_id(q))
    
    ctx = rag_engine._retrieve_telemetry_context("VEHICLE_008")
    print("\nContext for VEHICLE_008:")
    print(ctx)

asyncio.run(main())
