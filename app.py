import aiosqlite
import csv
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from langchain.agents import initialize_agent, AgentType, Tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List, Dict
from dotenv import load_dotenv
from difflib import SequenceMatcher

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

# Fuzzy matching helper function
def fuzzy_match(text1, text2, threshold=0.6):
    """Check if two strings are similar enough (handles typos)"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() >= threshold

# Common misspellings and variations
NEIGHBORHOOD_VARIATIONS = {
    'roslindale': ['roslindale', 'roslindal', 'roslindail'],
    'jamaica plain': ['jamaica plain', 'jamaca plain', 'jamaicaplain', 'jp'],
    'south end': ['south end', 'southend', 'south-end'],
    'back bay': ['back bay', 'backbay', 'back-bay'],
    'charlestown': ['charlestown', 'charleston', 'charestown'],
    'east boston': ['east boston', 'eastboston', 'east-boston', 'eastie'],
    'north end': ['north end', 'northend', 'north-end'],
    'allston': ['allston', 'alston', 'alliston'],
    'brighton': ['brighton', 'britton', 'bryton'],
    'roxbury': ['roxbury', 'roxbery', 'roxburry'],
    'dorchester': ['dorchester', 'dorchestor', 'dorchster', 'dot'],
    'west roxbury': ['west roxbury', 'westroxbury', 'west-roxbury'],
    'hyde park': ['hyde park', 'hydepark', 'hyde-park'],
    'mission hill': ['mission hill', 'missionhill', 'mission-hill']
}

OFFICE_VARIATIONS = {
    'mayor': ['mayor', 'mayer', 'major'],
    'city councilor': ['city councilor', 'city councilman', 'councilor', 'councilman', 'council member'],
    'state senator': ['state senator', 'senator', 'state senate'],
    'state representative': ['state representative', 'state rep', 'representative', 'rep']
}

def normalize_search_term(search_term):
    """Normalize search term by checking for common variations and misspellings"""
    search_lower = search_term.lower().strip()
    
    # Check neighborhood variations
    for standard_name, variations in NEIGHBORHOOD_VARIATIONS.items():
        for variation in variations:
            if fuzzy_match(search_lower, variation, 0.8):
                return standard_name
    
    # Check office variations
    for standard_office, variations in OFFICE_VARIATIONS.items():
        for variation in variations:
            if fuzzy_match(search_lower, variation, 0.8):
                return standard_office
    
    return search_term

# IMPROVED Database search function with fuzzy matching
async def get_officials_by_name(name: str) -> List[Dict]:
    """
    AI-powered search that handles misspellings and smart mapping.
    """
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        
        # Normalize the search term first
        normalized_name = normalize_search_term(name)
        print(f"Searching for: '{name}' (normalized: '{normalized_name}')")
        
        # Check if this is a district-specific search
        district_match = re.search(r'district\s+(\d+)', normalized_name.lower())
        
        if district_match:
            # This is a district search - be very specific
            district_num = district_match.group(1)
            query = """
                SELECT * FROM officials 
                WHERE district_type = 'District' AND district_number = ?
            """
            await cursor.execute(query, (district_num,))
        else:
            # Get all officials for fuzzy matching
            await cursor.execute("SELECT * FROM officials")
            all_officials = await cursor.fetchall()
            
            # First try exact/close matches
            search_term = f"%{normalized_name.lower()}%"
            
            # Try regular search first
            query = """
                SELECT * FROM officials 
                WHERE lower(name) LIKE ? 
                OR lower(office) LIKE ?
                OR lower(level) LIKE ?
            """
            await cursor.execute(query, (search_term, search_term, search_term))
            
            results = await cursor.fetchall()
            
            # If no results, try fuzzy matching on names AND offices
            if not results:
                fuzzy_matches = []
                for official in all_officials:
                    # Check name similarity
                    if fuzzy_match(normalized_name, official['name'], 0.6):
                        fuzzy_matches.append(dict(official))
                    # Check office similarity  
                    elif fuzzy_match(normalized_name, official['office'], 0.6):
                        fuzzy_matches.append(dict(official))
                    # Special check for mayor/mayer
                    elif ('mayor' in normalized_name.lower() or 'mayer' in normalized_name.lower()) and 'mayor' in official['office'].lower():
                        fuzzy_matches.append(dict(official))
                
                return fuzzy_matches
        
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
            # Try to suggest similar terms
            normalized = normalize_search_term(name)
            if normalized != name:
                return f"No officials found matching '{name}'. Did you mean '{normalized}'? Let me search for that."
            return f"No officials found matching '{name}'. Try searching for 'mayor', 'city councilor', or a specific name."
        
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

# Create the LangChain Agent with different agent type
llm = ChatOpenAI(
    temperature=0, 
    model="gpt-3.5-turbo", 
    api_key=os.environ.get("OPENAI_API_KEY")
)

# Define tools for the agent
tools = [
    Tool.from_function(
        func=sync_get_officials_by_name,
        name="BostonOfficials",
        description="Search for Boston elected officials by name, office, or neighborhood. Always use this tool for any question about Boston officials."
    )
]

# System message for the agent - CLEAR AND DIRECT
system_message_content = """You are an AI assistant that helps people find Boston elected officials.

CRITICAL: For ANY question about officials, you MUST use the BostonOfficials tool first. Never respond without using the tool.

When someone asks about officials:
1. Use the BostonOfficials tool with their exact query
2. Present the results in a helpful way
3. Be conversational and encouraging about civic engagement

Examples:
- "Who is the mayor?" → Use BostonOfficials("mayor")
- "Roslindale councilor" → Use BostonOfficials("roslindale") 
- "Michelle Wu" → Use BostonOfficials("Michelle Wu")

Always use the tool first, then respond based on the results."""

# Initialize the agent with ZERO_SHOT_REACT_DESCRIPTION (more reliable than OPENAI_FUNCTIONS)
agent = initialize_agent(
    tools, 
    llm, 
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
    agent_kwargs={
        "prefix": system_message_content,
        "format_instructions": "Use the following format:\n\nQuestion: the input question you must answer\nThought: you should always think about what to do\nAction: the action to take, should be one of [BostonOfficials]\nAction Input: the input to the action\nObservation: the result of the action\n... (this Thought/Action/Action Input/Observation can repeat N times)\nThought: I now know the final answer\nFinal Answer: the final answer to the original input question",
        "suffix": "Begin!\n\nQuestion: {input}\nThought:{agent_scratchpad}"
    }
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
    AI Agent endpoint with better agent type.
    """
    print(f"Received query: {query_model.query}")
    
    try:
        # Run the AI agent
        response = agent.run(query_model.query)
        print(f"Agent response: {response}")
        return {"response": response}
    
    except Exception as e:
        print(f"Error during agent execution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}