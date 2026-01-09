"""
Example Implementation: Natural Language Query Interface
========================================================
This is a simplified example showing how to implement NLP query capabilities.
"""

import os
from typing import Dict, Optional
from langchain.llms import OpenAI
from langchain.chains import SQLDatabaseChain
from langchain.sql_database import SQLDatabase
from loguru import logger

# Note: This requires OpenAI API key or local LLM setup
# For production, consider using open-source alternatives like:
# - Llama 2 (via HuggingFace)
# - Mistral AI
# - Local LLM servers (Ollama, LM Studio)


class NaturalLanguageQueryEngine:
    """
    Convert natural language queries to SQL and execute against ClickHouse.
    
    Example Usage:
        engine = NaturalLanguageQueryEngine(clickhouse_connection_string)
        result = await engine.query("Show me all vehicles with high engine temperature")
    """
    
    def __init__(self, db_connection_string: str, api_key: Optional[str] = None):
        """
        Initialize the query engine.
        
        Args:
            db_connection_string: Database connection string
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
        """
        self.db = SQLDatabase.from_uri(db_connection_string)
        
        # Initialize LLM
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI API key not found. Using mock responses.")
            self.llm = None
        else:
            self.llm = OpenAI(temperature=0, openai_api_key=api_key)
            self.chain = SQLDatabaseChain.from_llm(
                self.llm,
                self.db,
                verbose=True,
                return_intermediate_steps=True
            )
    
    async def query(self, user_query: str, vehicle_id: Optional[str] = None) -> Dict:
        """
        Process natural language query and return results.
        
        Args:
            user_query: Natural language query from user
            vehicle_id: Optional vehicle ID to filter results
            
        Returns:
            Dictionary with query results and metadata
        """
        try:
            # Add vehicle context if provided
            if vehicle_id:
                user_query = f"For vehicle {vehicle_id}: {user_query}"
            
            if not self.llm:
                # Mock response for development
                return {
                    "query": user_query,
                    "sql": "SELECT * FROM telemetry WHERE vehicle_id = ?",
                    "result": [],
                    "summary": "Mock response - configure OpenAI API key for full functionality",
                    "error": None
                }
            
            # Execute query through LangChain
            result = self.chain(user_query)
            
            # Extract SQL and results
            sql_query = result.get("intermediate_steps", [{}])[0].get("sql", "")
            query_result = result.get("result", [])
            
            # Generate natural language summary
            summary = self._generate_summary(user_query, query_result)
            
            return {
                "query": user_query,
                "sql": sql_query,
                "result": query_result,
                "summary": summary,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "query": user_query,
                "sql": None,
                "result": [],
                "summary": f"Error processing query: {str(e)}",
                "error": str(e)
            }
    
    def _generate_summary(self, query: str, results: list) -> str:
        """Generate a natural language summary of the results."""
        if not results:
            return "No results found for your query."
        
        result_count = len(results)
        return f"Found {result_count} result(s) matching your query: '{query}'"


# Example FastAPI endpoint integration
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class QueryRequest(BaseModel):
    query: str
    vehicle_id: Optional[str] = None

@app.post("/nlp/query")
async def natural_language_query(request: QueryRequest):
    '''
    Natural language query endpoint.
    
    Example queries:
    - "Show me all vehicles with high engine temperature"
    - "What's the average battery voltage for vehicle V001?"
    - "Which vehicles need urgent maintenance?"
    '''
    engine = NaturalLanguageQueryEngine(
        db_connection_string="clickhouse://localhost:9000/telemetry_db"
    )
    result = await engine.query(request.query, request.vehicle_id)
    return result
"""

