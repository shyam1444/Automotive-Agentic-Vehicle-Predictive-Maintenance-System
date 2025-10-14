"""
MongoDB Schema Definitions for Phase 4 - Multi-Agent Ecosystem
===============================================================
Defines collections, indexes, and validation schemas for agent data
"""

from datetime import datetime
from typing import Dict, Any

# ============================================================================
# COLLECTION SCHEMAS
# ============================================================================

# Agent Status Collection
AGENT_STATUS_SCHEMA = {
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["agent_id", "agent_type", "status", "last_heartbeat"],
            "properties": {
                "agent_id": {
                    "bsonType": "string",
                    "description": "Unique agent identifier"
                },
                "agent_type": {
                    "enum": ["master", "diagnostics", "customer", "scheduling", "manufacturing", "ueba"],
                    "description": "Type of agent"
                },
                "status": {
                    "enum": ["active", "idle", "error", "stopped"],
                    "description": "Current agent status"
                },
                "last_heartbeat": {
                    "bsonType": "date",
                    "description": "Last heartbeat timestamp"
                },
                "messages_processed": {
                    "bsonType": "int",
                    "description": "Total messages processed"
                },
                "errors_count": {
                    "bsonType": "int",
                    "description": "Error count since start"
                },
                "metadata": {
                    "bsonType": "object",
                    "description": "Additional agent-specific metadata"
                }
            }
        }
    }
}

# Customer Info Collection
CUSTOMER_INFO_SCHEMA = {
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["customer_id", "vehicle_id", "contact_info"],
            "properties": {
                "customer_id": {
                    "bsonType": "string",
                    "description": "Unique customer identifier"
                },
                "vehicle_id": {
                    "bsonType": "string",
                    "description": "Associated vehicle ID"
                },
                "contact_info": {
                    "bsonType": "object",
                    "required": ["phone"],
                    "properties": {
                        "phone": {"bsonType": "string"},
                        "email": {"bsonType": "string"},
                        "whatsapp": {"bsonType": "string"}
                    }
                },
                "customer_name": {
                    "bsonType": "string"
                },
                "preferred_contact_method": {
                    "enum": ["sms", "email", "whatsapp"],
                    "description": "Preferred notification method"
                },
                "notification_enabled": {
                    "bsonType": "bool",
                    "description": "Whether notifications are enabled"
                }
            }
        }
    }
}

# Service Schedule Collection
SERVICE_SCHEDULE_SCHEMA = {
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["booking_id", "vehicle_id", "scheduled_date", "severity", "status"],
            "properties": {
                "booking_id": {
                    "bsonType": "string",
                    "description": "Unique booking identifier"
                },
                "vehicle_id": {
                    "bsonType": "string"
                },
                "customer_id": {
                    "bsonType": "string"
                },
                "scheduled_date": {
                    "bsonType": "date",
                    "description": "Scheduled maintenance date"
                },
                "severity": {
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Alert severity level"
                },
                "status": {
                    "enum": ["pending", "confirmed", "in_progress", "completed", "cancelled"],
                    "description": "Booking status"
                },
                "service_type": {
                    "bsonType": "string",
                    "description": "Type of service required"
                },
                "diagnostic_result_id": {
                    "bsonType": "string",
                    "description": "Reference to diagnostic result"
                },
                "estimated_duration": {
                    "bsonType": "int",
                    "description": "Estimated duration in minutes"
                },
                "notes": {
                    "bsonType": "string"
                }
            }
        }
    }
}

# Manufacturing Reports Collection
MANUFACTURING_REPORTS_SCHEMA = {
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["report_id", "component", "failure_pattern", "timestamp"],
            "properties": {
                "report_id": {
                    "bsonType": "string",
                    "description": "Unique report identifier"
                },
                "component": {
                    "bsonType": "string",
                    "description": "Component with repeated failures"
                },
                "failure_pattern": {
                    "bsonType": "object",
                    "properties": {
                        "failure_type": {"bsonType": "string"},
                        "occurrence_count": {"bsonType": "int"},
                        "affected_vehicles": {"bsonType": "array"},
                        "common_conditions": {"bsonType": "object"}
                    }
                },
                "capa_suggestions": {
                    "bsonType": "array",
                    "description": "Corrective and Preventive Actions"
                },
                "severity_score": {
                    "bsonType": "double",
                    "description": "Aggregated severity (0-1)"
                },
                "timestamp": {
                    "bsonType": "date"
                }
            }
        }
    }
}

# Alerts History Collection
ALERTS_HISTORY_SCHEMA = {
    "validator": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["alert_id", "vehicle_id", "timestamp", "severity"],
            "properties": {
                "alert_id": {
                    "bsonType": "string",
                    "description": "Unique alert identifier"
                },
                "vehicle_id": {
                    "bsonType": "string"
                },
                "timestamp": {
                    "bsonType": "date"
                },
                "severity": {
                    "enum": ["warning", "critical"],
                    "description": "Alert severity"
                },
                "failure_probability": {
                    "bsonType": "double"
                },
                "diagnostic_result": {
                    "bsonType": "object",
                    "description": "Associated diagnostic result"
                },
                "customer_notified": {
                    "bsonType": "bool",
                    "description": "Whether customer was notified"
                },
                "service_scheduled": {
                    "bsonType": "bool",
                    "description": "Whether service was scheduled"
                },
                "resolution_status": {
                    "enum": ["pending", "acknowledged", "scheduled", "resolved"],
                    "description": "Current resolution status"
                },
                "agents_processed": {
                    "bsonType": "array",
                    "description": "List of agents that processed this alert"
                }
            }
        }
    }
}

# ============================================================================
# INDEX DEFINITIONS
# ============================================================================

INDEXES = {
    "agent_status": [
        {"keys": [("agent_id", 1)], "unique": True},
        {"keys": [("agent_type", 1), ("status", 1)]},
        {"keys": [("last_heartbeat", -1)]}
    ],
    "customer_info": [
        {"keys": [("customer_id", 1)], "unique": True},
        {"keys": [("vehicle_id", 1)]},
        {"keys": [("contact_info.phone", 1)]}
    ],
    "service_schedule": [
        {"keys": [("booking_id", 1)], "unique": True},
        {"keys": [("vehicle_id", 1), ("scheduled_date", -1)]},
        {"keys": [("status", 1), ("severity", -1)]},
        {"keys": [("scheduled_date", 1)]}
    ],
    "manufacturing_reports": [
        {"keys": [("report_id", 1)], "unique": True},
        {"keys": [("component", 1), ("timestamp", -1)]},
        {"keys": [("severity_score", -1)]}
    ],
    "alerts_history": [
        {"keys": [("alert_id", 1)], "unique": True},
        {"keys": [("vehicle_id", 1), ("timestamp", -1)]},
        {"keys": [("resolution_status", 1), ("severity", -1)]},
        {"keys": [("timestamp", -1)]}
    ]
}

# ============================================================================
# INITIALIZATION FUNCTION
# ============================================================================

async def initialize_mongodb(db):
    """
    Initialize MongoDB collections with schemas and indexes
    
    Args:
        db: MongoDB database instance
    """
    collections_config = {
        "agent_status": AGENT_STATUS_SCHEMA,
        "customer_info": CUSTOMER_INFO_SCHEMA,
        "service_schedule": SERVICE_SCHEDULE_SCHEMA,
        "manufacturing_reports": MANUFACTURING_REPORTS_SCHEMA,
        "alerts_history": ALERTS_HISTORY_SCHEMA
    }
    
    # Create collections with validation
    for collection_name, schema in collections_config.items():
        if collection_name not in await db.list_collection_names():
            await db.create_collection(collection_name, **schema)
            print(f"✅ Created collection: {collection_name}")
        else:
            # Update validation schema
            await db.command({
                "collMod": collection_name,
                "validator": schema["validator"]
            })
            print(f"🔄 Updated validation for: {collection_name}")
    
    # Create indexes
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]
        for index_spec in indexes:
            await collection.create_index(
                index_spec["keys"],
                unique=index_spec.get("unique", False)
            )
        print(f"📇 Created indexes for: {collection_name}")
    
    print("✅ MongoDB initialization complete!")

# ============================================================================
# SAMPLE DATA GENERATION
# ============================================================================

def generate_sample_customers():
    """Generate sample customer data for testing"""
    return [
        {
            "customer_id": "CUST_001",
            "vehicle_id": "VEHICLE_001",
            "customer_name": "John Smith",
            "contact_info": {
                "phone": "+1234567890",
                "email": "john.smith@example.com",
                "whatsapp": "+1234567890"
            },
            "preferred_contact_method": "email",
            "notification_enabled": True
        },
        {
            "customer_id": "CUST_002",
            "vehicle_id": "VEHICLE_002",
            "customer_name": "Jane Doe",
            "contact_info": {
                "phone": "+1234567891",
                "email": "jane.doe@example.com",
                "whatsapp": "+1234567891"
            },
            "preferred_contact_method": "sms",
            "notification_enabled": True
        },
        {
            "customer_id": "CUST_003",
            "vehicle_id": "VEHICLE_003",
            "customer_name": "Bob Johnson",
            "contact_info": {
                "phone": "+1234567892",
                "email": "bob.johnson@example.com",
                "whatsapp": "+1234567892"
            },
            "preferred_contact_method": "whatsapp",
            "notification_enabled": True
        }
    ]
