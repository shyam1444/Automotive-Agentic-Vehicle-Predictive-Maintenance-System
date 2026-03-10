import os
from datetime import datetime
from loguru import logger
import httpx
import json

class RAGEngine:
    def __init__(self):
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = "gemma:2b"
        self.clickhouse_host = os.getenv("CLICKHOUSE_HOST", "localhost")
        self.clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", "9000"))
        self.clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
        self.clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse_pass")
        self.clickhouse_db = os.getenv("CLICKHOUSE_DATABASE", "telemetry_db")

    def _get_clickhouse_client(self):
        try:
            from clickhouse_driver import Client
            return Client(
                host=self.clickhouse_host,
                port=self.clickhouse_port,
                user=self.clickhouse_user,
                password=self.clickhouse_password,
                database=self.clickhouse_db
            )
        except ImportError:
            logger.error("clickhouse_driver not installed")
            return None

    def _retrieve_telemetry_context(self, vehicle_id: str):
        """Retrieve recent telemetry for a specific vehicle."""
        client = self._get_clickhouse_client()
        if not client:
            return "Database client unavailable."

        query = f"""
        SELECT 
            timestamp, engine_temp, vibration, battery_voltage, engine_rpm, speed, fuel_level
        FROM telemetry
        WHERE vehicle_id = %(vehicle_id)s
        ORDER BY timestamp DESC
        LIMIT 5
        """
        try:
            result = client.execute(query, {"vehicle_id": vehicle_id})
            if not result:
                return f"No telemetry data found for vehicle {vehicle_id}."

            context_lines = []
            for row in result:
                timestamp = row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0])
                context_lines.append(
                    f"- {vehicle_id} [{timestamp}]: Temp {row[1]:.1f}°C, Vib {row[2]:.2f} mm/s, "
                    f"Battery {row[3]:.1f}V, RPM {row[4]}, Speed {row[5]} km/h, Fuel {row[6]}%"
                )
            return "\n".join(context_lines)
        except Exception as e:
            logger.error(f"Error querying telemetry for RAG: {e}")
            return f"Error accessing database: {e}"

    def _retrieve_fleet_context(self):
        """Retrieve the latest status for all vehicles to answer general fleet queries."""
        client = self._get_clickhouse_client()
        if not client:
            return "Database client unavailable."

        query = """
        SELECT 
            vehicle_id,
            argMax(engine_temp, timestamp) as engine_temp,
            argMax(vibration, timestamp) as vibration,
            argMax(battery_voltage, timestamp) as battery_voltage
        FROM telemetry
        WHERE timestamp >= now() - INTERVAL 24 HOUR
        GROUP BY vehicle_id
        """
        try:
            result = client.execute(query)
            if not result:
                return "No fleet telemetry data found."
            
            critical = []
            warning = []
            healthy = []
            for row in result:
                vid, temp, vib, batt = row[0], row[1], row[2], row[3]
                status_str = f"{vid} (Temp: {temp:.1f}°C, Vib: {vib:.1f}mm/s, Batt: {batt:.1f}V)"
                if temp > 110 or vib > 8 or batt < 11:
                    critical.append(status_str)
                elif temp > 100 or vib > 6 or batt < 11.5:
                    warning.append(status_str)
                else:
                    healthy.append(vid)
            
            ctx = f"Fleet Status Overview ({len(result)} total vehicles monitored in last 24h):\n"
            if critical:
                ctx += "CRITICAL Vehicles:\n- " + "\n- ".join(critical[:10]) + ("\n...and more" if len(critical)>10 else "\n")
            else:
                ctx += "CRITICAL Vehicles: None\n"
                
            if warning:
                ctx += "WARNING Vehicles:\n- " + "\n- ".join(warning[:10]) + ("\n...and more" if len(warning)>10 else "\n")
            else:
                ctx += "WARNING Vehicles: None\n"
                
            if healthy:
                ctx += "HEALTHY (Not Critical/Warning) Vehicles:\n- " + "\n- ".join(healthy[:15]) + ("\n...and more" if len(healthy)>15 else "\n")
            else:
                ctx += "HEALTHY Vehicles: None\n"
            return ctx
        except Exception as e:
            logger.error(f"Error querying fleet context: {e}")
            return "Error retrieving fleet context."

    async def _query_ollama(self, prompt: str):
        """Send the augmented prompt to the local Ollama instance."""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                }
                response = await client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("response", "No response generated.")
        except httpx.ConnectError:
            logger.error("Ollama connection error. Is it running?")
            return "Error: Ollama service is not reachable. Ensure it is running locally."
        except httpx.TimeoutException:
            logger.error("Ollama query timed out.")
            return "Error: The model took too long to respond."
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return f"An unexpected error occurred: {e}"

    def _get_new_query(self, query: str) -> str:
        """Extract the actual latest query from history."""
        if "New query:" in query:
            return query.split("New query:")[-1].strip()
        return query

    def _extract_vehicle_id(self, query: str) -> str:
        """Attempt to extract a vehicle ID from the user's latest query."""
        import re
        new_query = self._get_new_query(query)
        matches = re.findall(r'VEHICLE_\d+', new_query, re.IGNORECASE)
        if matches:
            return matches[-1].upper()
        return None

    def _is_fleet_query(self, query: str) -> bool:
        """Check if the user is asking a general fleet question."""
        import re
        query_lower = self._get_new_query(query).lower()
        fleet_keywords = [
            "all vehicles", "which vehicles", "what vehicles", 
            "how many vehicles", "fleet", "critical vehicles", 
            "warning vehicles", "any vehicle", "other vehicles",
            "list vehicles", "healthy vehicles", "status of vehicles"
        ]
        return any(kw in query_lower for kw in fleet_keywords)

    async def retrieve_and_generate(self, user_query: str):
        """Main RAG pipeline: retrieves context, composes prompt, and gets response."""
        vehicle_id = self._extract_vehicle_id(user_query)
        is_fleet = self._is_fleet_query(user_query)
        
        context = ""
        system_rules = (
            "System Rules for Status:\n"
            "- CRITICAL: Engine Temp > 110°C, or Vibration > 8 mm/s, or Battery Voltage < 11.0V\n"
            "- WARNING: Engine Temp > 100°C, or Vibration > 6 mm/s, or Battery Voltage < 11.5V\n\n"
        )

        if not vehicle_id and is_fleet:
            logger.info("RAG triggered for Fleet Overview")
            context = self._retrieve_fleet_context()
            system_prompt = (
                "You are an AI Automotive Engineer assistant monitoring a fleet of vehicles.\n"
                "Use the following fleet telemetry data to answer questions about the fleet. "
                "The context below contains exact lists of vehicles and their statuses.\n"
                "Note: 'HEALTHY' and 'WARNING' vehicles are considered 'not critical'. If the user asks for 'not critical' vehicles, list both HEALTHY and WARNING.\n\n"
                f"{system_rules}"
                f"Fleet Context:\n{context}\n\n"
                f"User Question: {user_query}\n\n"
                "Answer the user's question by extracting the appropriate vehicle IDs from the context above:"
            )
        elif vehicle_id:
            logger.info(f"RAG triggered for {vehicle_id}")
            context = self._retrieve_telemetry_context(vehicle_id)
            system_prompt = (
                f"You are an AI Automotive Engineer assistant answering about '{vehicle_id}'.\n"
                f"Even if the user types '{vehicle_id.lower()}', they mean '{vehicle_id}'.\n"
                f"Use the following telemetry data to answer their question. "
                "Do not say the context has no information, because the context IS the information.\n\n"
                f"{system_rules}"
                f"Telemetry Context:\n{context}\n\n"
                f"User Question: {user_query}\n\n"
                "Answer concisely based strictly on the rules and context:"
            )
        else:
            logger.info(f"RAG triggered for general query")
            system_prompt = (
                "You are an AI Automotive Engineer assistant.\n"
                "Answer the user's question safely, or ask them to clarify what vehicle they are asking about.\n\n"
                f"User Question: {user_query}\n\n"
                "Answer concisely:"
            )

        logger.debug(f"Generated prompt for Ollama: {system_prompt}")
        response = await self._query_ollama(system_prompt)
        return response

rag_engine = RAGEngine()
