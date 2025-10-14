"""
Phase 4 Initialization Script
==============================
Initializes MongoDB with schemas and sample data
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mongodb_schemas import initialize_mongodb, generate_sample_customers

MONGODB_URI = 'mongodb://admin:mongodb_pass@localhost:27017/'
MONGODB_DATABASE = 'agents_db'

async def init_phase4():
    """Initialize Phase 4 MongoDB infrastructure"""
    print("=" * 80)
    print("🚀 Phase 4 Initialization")
    print("=" * 80)
    
    try:
        # Connect to MongoDB
        print("📡 Connecting to MongoDB...")
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[MONGODB_DATABASE]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Connected to MongoDB")
        
        # Initialize collections and schemas
        print("\n📋 Initializing collections and schemas...")
        await initialize_mongodb(db)
        
        # Insert sample customers
        print("\n👥 Creating sample customer data...")
        customers = generate_sample_customers()
        
        for customer in customers:
            await db.customer_info.update_one(
                {'customer_id': customer['customer_id']},
                {'$set': customer},
                upsert=True
            )
            print(f"   ✅ Created: {customer['customer_id']} ({customer['customer_name']})")
        
        # Verify collections
        print("\n📊 Verifying collections...")
        collections = await db.list_collection_names()
        expected_collections = [
            'agent_status',
            'customer_info',
            'service_schedule',
            'manufacturing_reports',
            'alerts_history'
        ]
        
        for coll in expected_collections:
            if coll in collections:
                count = await db[coll].count_documents({})
                print(f"   ✅ {coll}: {count} documents")
            else:
                print(f"   ❌ {coll}: NOT FOUND")
        
        # Show customer records
        print("\n👤 Sample Customers:")
        async for customer in db.customer_info.find().limit(10):
            print(f"   - {customer['customer_id']}: {customer['customer_name']}")
            print(f"     Vehicle: {customer['vehicle_id']}")
            print(f"     Contact: {customer['contact_info']['phone']} | {customer['contact_info']['email']}")
            print(f"     Method: {customer['preferred_contact_method']}")
            print()
        
        print("=" * 80)
        print("✅ Phase 4 Initialization Complete!")
        print("=" * 80)
        print("\nNext Steps:")
        print("1. Start Master Agent:      python3 agents/master_agent.py")
        print("2. Start Diagnostics Agent: python3 agents/diagnostics_agent.py")
        print("3. Start Customer Agent:    python3 agents/customer_agent.py")
        print()
        
        client.close()
        
    except Exception as e:
        print(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(init_phase4())
