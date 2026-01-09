"""
ClickHouse Initialization Script
=================================
Initializes ClickHouse database schema and tables for the automotive predictive maintenance system.

This script can be used to:
1. Initialize ClickHouse database if not using Docker auto-init
2. Verify ClickHouse setup
3. Recreate tables if needed
"""

import os
import sys
from pathlib import Path
from clickhouse_driver import Client
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")

# Path to SQL initialization file
INIT_SQL_PATH = Path(__file__).parent / "docker" / "clickhouse" / "init.sql"


def connect_clickhouse():
    """Connect to ClickHouse and return client"""
    try:
        client = Client(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            user=CLICKHOUSE_USER,
            password=CLICKHOUSE_PASSWORD,
            settings={'use_numpy': False}
        )
        # Test connection
        client.execute('SELECT 1')
        logger.info(f"✅ Connected to ClickHouse at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
        return client
    except Exception as e:
        logger.error(f"❌ Failed to connect to ClickHouse: {e}")
        logger.error(f"   Make sure ClickHouse is running and accessible at {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
        return None


def read_sql_file(file_path: Path) -> str:
    """Read SQL file and return content"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"❌ SQL file not found: {file_path}")
        return None
    except Exception as e:
        logger.error(f"❌ Error reading SQL file: {e}")
        return None


def execute_sql_statements(client: Client, sql_content: str):
    """Execute SQL statements from content"""
    # Split by semicolon and filter out comments and empty statements
    statements = []
    current_statement = []
    
    for line in sql_content.split('\n'):
        # Remove single-line comments
        if '--' in line:
            line = line[:line.index('--')]
        
        line = line.strip()
        if line:
            current_statement.append(line)
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                if statement.strip() and not statement.strip().startswith('--'):
                    statements.append(statement)
                current_statement = []
    
    # Execute each statement
    executed = 0
    failed = 0
    
    for statement in statements:
        try:
            client.execute(statement)
            executed += 1
            logger.debug(f"✅ Executed: {statement[:50]}...")
        except Exception as e:
            # Some statements might fail if objects already exist (IF NOT EXISTS)
            if "already exists" in str(e).lower() or "exists" in str(e).lower():
                logger.debug(f"⚠️  Skipped (already exists): {statement[:50]}...")
            else:
                logger.warning(f"⚠️  Failed: {statement[:50]}... Error: {e}")
                failed += 1
    
    return executed, failed


def verify_setup(client: Client):
    """Verify that tables were created successfully"""
    logger.info("\n🔍 Verifying ClickHouse setup...")
    
    try:
        # Check if database exists
        databases = client.execute("SHOW DATABASES")
        db_names = [db[0] for db in databases]
        
        if CLICKHOUSE_DATABASE not in db_names:
            logger.error(f"❌ Database '{CLICKHOUSE_DATABASE}' not found!")
            return False
        
        logger.info(f"✅ Database '{CLICKHOUSE_DATABASE}' exists")
        
        # Use the database
        client.execute(f"USE {CLICKHOUSE_DATABASE}")
        
        # Check for key tables
        tables = client.execute("SHOW TABLES")
        table_names = [table[0] for table in tables]
        
        expected_tables = [
            'telemetry',
            'telemetry_kafka',
            'telemetry_mv',
            'anomalies',
            'vehicle_predictions',
            'vehicle_alerts'
        ]
        
        logger.info(f"\n📊 Found {len(table_names)} tables:")
        for table in table_names:
            logger.info(f"   - {table}")
        
        missing_tables = [t for t in expected_tables if t not in table_names]
        if missing_tables:
            logger.warning(f"\n⚠️  Missing tables: {', '.join(missing_tables)}")
            return False
        
        logger.info(f"\n✅ All expected tables exist!")
        
        # Check row counts
        try:
            telemetry_count = client.execute(f"SELECT count() FROM {CLICKHOUSE_DATABASE}.telemetry")[0][0]
            logger.info(f"📈 Telemetry records: {telemetry_count}")
        except:
            logger.info("📈 Telemetry table is empty (expected for new setup)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verifying setup: {e}")
        return False


def main():
    """Main initialization function"""
    print("=" * 80)
    print("🚀 ClickHouse Initialization")
    print("=" * 80)
    print(f"Host: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")
    print(f"Database: {CLICKHOUSE_DATABASE}")
    print("=" * 80)
    
    # Connect to ClickHouse
    client = connect_clickhouse()
    if not client:
        logger.error("❌ Cannot proceed without ClickHouse connection")
        sys.exit(1)
    
    # Read SQL file
    logger.info(f"\n📖 Reading SQL initialization file: {INIT_SQL_PATH}")
    sql_content = read_sql_file(INIT_SQL_PATH)
    
    if not sql_content:
        logger.error("❌ Cannot proceed without SQL file")
        sys.exit(1)
    
    # Execute SQL statements
    logger.info("\n⚙️  Executing SQL statements...")
    executed, failed = execute_sql_statements(client, sql_content)
    
    logger.info(f"\n📊 Execution Summary:")
    logger.info(f"   ✅ Executed: {executed} statements")
    if failed > 0:
        logger.info(f"   ⚠️  Failed: {failed} statements")
    
    # Verify setup
    if verify_setup(client):
        logger.info("\n" + "=" * 80)
        logger.info("✅ ClickHouse initialization completed successfully!")
        logger.info("=" * 80)
    else:
        logger.warning("\n" + "=" * 80)
        logger.warning("⚠️  ClickHouse initialization completed with warnings")
        logger.warning("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

