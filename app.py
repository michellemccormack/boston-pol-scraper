import aiosqlite
from fastapi import FastAPI
from langchain.agents import initialize_agent, AgentType, Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import os
from fastapi.middleware.cors import CORSMiddleware # New Import

# Define the path to your database file
DATABASE_URL = "officials.db"

app = FastAPI()

# NEW: Add CORS middleware to allow cross-origin requests from your frontend
origins = [
    "http://localhost", # For local development
    "http://127.0.0.1", # For local development
    "file://", # For opening index.html directly in browser
    "null", # Some browsers (like Chrome) use 'null' origin for local files
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, you can restrict this later
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Your database search function is now a "tool" for the AI.
async def get_officials_by_name(name: str):
    """
    Searches the database for an elected official by their name.
    """
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row  # This makes rows act like dictionaries
        cursor = await db.cursor()
        
        # SQL query to find officials with a similar name
        # We will search broadly across name and office to catch more matches
        query = "SELECT * FROM officials WHERE lower(name) LIKE ? OR lower(Office) LIKE ?;"
        await cursor.execute(query, (f"%{name.lower()}%", f"%{name.lower()}%"))
        
        results = await cursor.fetchall()
        
        return [dict(row) for row in results]

# Create the LangChain Agent
# --- API KEY IS DIRECTLY INCLUDED IN THIS LINE ---
llm = ChatOpenAI(
    temperature=0, 
    model="gpt-3.5-turbo", 
    api_key=os.environ.get("OPENAI_API_KEY")

# The Tool definition now explicitly handles the async nature of get_officials_by_name
tools = [
    Tool.from_function(
        func=get_officials_by_name,
        name="OfficialsDB",
        description="A tool that searches the Boston officials database. Use this for any question that asks about an elected official's name, office, or contact information. The input should be the full or partial name of the official, or the office they hold (e.g., 'mayor').",
        coroutine=get_officials_by_name # Explicitly tell LangChain it's a coroutine
    )
]

# We will provide a specific system message to guide the AI's reasoning
# --- FIX: Passed as system_message within agent_kwargs ---
system_message_content = "You are a helpful assistant for finding information about elected officials in Boston. Always use the 'OfficialsDB' tool to search for information. If the user asks about an office (like 'mayor' or 'city councilor'), try searching for that office. If they ask about a name, search for that name. If you find multiple results, list them clearly."

agent = initialize_agent(
    tools, 
    llm, 
    agent=AgentType.OPENAI_FUNCTIONS, 
    verbose=True,
    handle_parsing_errors=True, # Added to catch potential parsing issues
    agent_kwargs={"system_message": system_message_content} # Pass the custom prompt
)

# Pydantic model for the POST request body
class QueryModel(BaseModel):
    query: str

@app.get("/")
async def read_root():
    """
    Root endpoint for the API. Returns a welcome message.
    """
    return {"message": "Welcome to the AI Political Scraper API!"}

@app.post("/ask/")
async def ask_agent(query_model: QueryModel):
    """
    Endpoint to send natural language queries to the AI agent.
    The agent uses its tools to find and return relevant information.
    """
    # Print the received query to the terminal for debugging.
    print(f"Received query: {query_model.query}")
    try:
        # --- CRUCIAL FIX: AWAITING THE ASYNCHRONOUS AGENT RUN ---
        response = await agent.arun(query_model.query) 
        # Print the agent's final response to the terminal.
        print(f"Agent response: {response}")
        return {"response": response}
    except Exception as e:
        # If an error occurs, print it to the terminal and return a 500 error.
        print(f"Error during agent execution: {e}")
        return {"error": str(e)}, 500

