from nlp.rag_engine import rag_engine
import asyncio

async def test():
    ctx5 = rag_engine._retrieve_telemetry_context("VEHICLE_005")
    print("VEHICLE_005 ctx:", ctx5)
    
    ctx8 = rag_engine._retrieve_telemetry_context("VEHICLE_008")
    print("VEHICLE_008 ctx:", ctx8)

asyncio.run(test()) 
