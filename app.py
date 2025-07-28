import aiosqlite
import csv
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from langchain.agents import initialize_agent, AgentType, Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define the path to your database file
DATABASE_URL = "officials.db"

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database initialization
async def init_database():
    """Initialize the database and populate it with data from CSV if it doesn't exist."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        # Create the officials table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS officials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                office TEXT NOT NULL,
                district_type TEXT,
                district_number TEXT,
                email TEXT,
                phone TEXT,
                website TEXT,
                social_media TEXT,
                level TEXT
            )
        ''')
        
        # Check if table is empty
        cursor = await db.execute("SELECT COUNT(*) FROM officials")
        count = await cursor.fetchone()
        
        if count[0] == 0:
            # Populate from CSV file
            if os.path.exists('officials.csv'):
                with open('officials.csv', 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        await db.execute('''
                            INSERT INTO officials (name, office, district_type, district_number, email, phone, website, social_media, level)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            row['name'], row['office'], row['district_type'], 
                            row['district_number'], row['email'], row['phone'], 
                            row['website'], row['social_media'], row['level']
                        ))
                await db.commit()
                print("Database populated with officials data")
            else:
                print("Warning: officials.csv not found")

# Database search function
async def get_officials_by_name(name: str) -> List[Dict]:
    """
    Searches the database for an elected official by their name or office.
    """
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        
        # Search broadly across name and office
        query = """
            SELECT * FROM officials 
            WHERE lower(name) LIKE ? 
            OR lower(office) LIKE ? 
            OR lower(district_type) LIKE ?
            OR lower(level) LIKE ?
        """
        search_term = f"%{name.lower()}%"
        await cursor.execute(query, (search_term, search_term, search_term, search_term))
        
        results = await cursor.fetchall()
        return [dict(row) for row in results]

# Synchronous wrapper for the async function (needed for LangChain)
def sync_get_officials_by_name(name: str) -> str:
    """Synchronous wrapper for the async database function."""
    try:
        # Get the current event loop or create a new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run the async function
        if loop.is_running():
            # If we're already in an async context, we need to handle this differently
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, get_officials_by_name(name))
                results = future.result()
        else:
            results = loop.run_until_complete(get_officials_by_name(name))
        
        if not results:
            return f"No officials found matching '{name}'. Try searching for a different name or office."
        
        # Format the results nicely
        formatted_results = []
        for official in results:
            result_text = f"**{official['name']}** - {official['office']}"
            if official['district_type'] and official['district_number']:
                result_text += f" ({official['district_type']} {official['district_number']})"
            if official['email']:
                result_text += f"\n📧 Email: {official['email']}"
            if official['phone']:
                result_text += f"\n📞 Phone: {official['phone']}"
            if official['website']:
                result_text += f"\n🌐 Website: {official['website']}"
            formatted_results.append(result_text)
        
        return "\n\n".join(formatted_results)
    
    except Exception as e:
        return f"Error searching for officials: {str(e)}"

# Create the LangChain Agent
llm = ChatOpenAI(
    temperature=0, 
    model="gpt-3.5-turbo", 
    api_key=os.environ.get("OPENAI_API_KEY")
)  # Fixed: Added missing closing parenthesis

# Define tools for the agent
tools = [
    Tool.from_function(
        func=sync_get_officials_by_name,
        name="OfficialsDB",
        description="A tool that searches the Boston officials database. Use this for any question about elected officials, their names, offices, or contact information. Input should be the name of the official or the office they hold (e.g., 'mayor', 'city councilor', 'state senator')."
    )
]

# System message for the agent - UPDATED TO BE SMARTER
system_message_content = """You are a helpful assistant for finding information about elected officials in Boston. 

Always use the 'OfficialsDB' tool to search for information. When users ask about:
- A specific person's name (e.g., "Michelle Wu") - search for that name
- An office or position (e.g., "mayor", "city councilor") - search for that office
- A district (e.g., "district 1") - search for that district
- A neighborhood (e.g., "Roslindale", "Back Bay") - search for related districts or councilors

Be proactive and helpful:
- If someone asks about Roslindale, automatically search for "District 5" since Roslindale is in District 5
- If someone asks about Jamaica Plain, automatically search for "District 6" since Jamaica Plain is in District 6
- If someone asks about South End or Back Bay, automatically search for "District 2"
- If someone asks about Charlestown, automatically search for "District 1"
- If someone asks about a neighborhood, search for related council districts
- If your initial search doesn't find results, try alternative search terms automatically
- Don't just say you can't find something - try different searches to help the user
- If you find multiple results, present them clearly with contact information

Always format contact information clearly and encourage civic engagement."""

# Initialize the agent
agent = initialize_agent(
    tools, 
    llm, 
    agent=AgentType.OPENAI_FUNCTIONS, 
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={"system_message": system_message_content}
)

# Pydantic model for requests
class QueryModel(BaseModel):
    query: str

@app.on_event("startup")
async def startup_event():
    """Initialize the database when the app starts."""
    await init_database()

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML interface."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse("<h1>Error: index.html not found</h1>", status_code=404)

@app.post("/ask/")
async def ask_agent(query_model: QueryModel):
    """
    Endpoint to send natural language queries to the AI agent.
    """
    print(f"Received query: {query_model.query}")
    
    try:
        # Run the agent synchronously (LangChain agents are not natively async)
        response = agent.run(query_model.query)  # Changed from arun to run
        print(f"Agent response: {response}")
        return {"response": response}
    
    except Exception as e:
        print(f"Error during agent execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}