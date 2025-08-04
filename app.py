import aiosqlite
import csv
import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from difflib import SequenceMatcher
import json

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the path to your database file
DATABASE_URL = "officials.db"

# Pydantic Model for API Requests
class QueryRequest(BaseModel):
    query: str
    session_id: str = "default"

# CUSTOM CONVERSATION ENGINE
class ConversationContext:
    """Intelligent conversation context manager."""
    
    def __init__(self):
        self.sessions = {}  # session_id -> conversation state
    
    def get_session(self, session_id: str = "default") -> dict:
        """Get or create conversation session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "history": [],  # List of {query, response, entities, timestamp}
                "current_entities": {},  # Currently active entities
                "context_stack": [],  # Stack of conversation topics
                "user_patterns": {}  # Learned user behavior patterns
            }
        return self.sessions[session_id]
    
    def extract_entities(self, text: str) -> dict:
        """Extract people, offices, and other entities from text."""
        entities = {
            "people": [],
            "offices": [],
            "districts": [],
            "parties": [],
            "concepts": []
        }
        
        text_lower = text.lower()
        
        # Extract names (pattern: Title Case Name)
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
        names = re.findall(name_pattern, text)
        entities["people"] = names
        
        # Extract offices
        office_keywords = ["mayor", "governor", "senator", "representative", "councilor", "attorney general"]
        for office in office_keywords:
            if office in text_lower:
                entities["offices"].append(office)
        
        # Extract districts
        district_matches = re.findall(r'district\s+(\d+)', text_lower)
        entities["districts"] = district_matches
        
        # Extract parties
        party_keywords = ["democrat", "republican", "nonpartisan", "independent"]
        for party in party_keywords:
            if party in text_lower:
                entities["parties"].append(party)
        
        # Extract concepts
        concept_keywords = ["salary", "election", "term", "office", "contact", "phone", "email"]
        for concept in concept_keywords:
            if concept in text_lower:
                entities["concepts"].append(concept)
        
        return entities
    
    def resolve_pronouns(self, query: str, session: dict) -> str:
        """Intelligently resolve pronouns based on conversation context."""
        query_lower = query.lower()
        
        # Get recent entities from conversation history
        recent_people = []
        for exchange in session["history"][-3:]:  # Last 3 exchanges
            recent_people.extend(exchange.get("entities", {}).get("people", []))
        
        # Resolve "she/her"
        if any(pronoun in query_lower for pronoun in ["she", "her", "hers"]):
            female_officials = ["Michelle Wu", "Elizabeth Warren", "Ayanna Pressley", "Maura Healey", "Andrea Campbell", "Kim Driscoll"]
            recent_females = [name for name in recent_people if name in female_officials]
            
            if recent_females:
                target_name = recent_females[-1]  # Most recent
            else:
                target_name = "Michelle Wu"  # Default to most prominent
            
            query = re.sub(r'\bshe\b', target_name, query, flags=re.IGNORECASE)
            query = re.sub(r'\bher\b', target_name, query, flags=re.IGNORECASE)
            query = re.sub(r'\bhers\b', target_name, query, flags=re.IGNORECASE)
        
        # Resolve "he/him"
        if any(pronoun in query_lower for pronoun in ["he", "him", "his"]):
            male_officials = ["Ed Markey", "Stephen Lynch", "Ed Flynn", "Nick Collins"]
            recent_males = [name for name in recent_people if name in male_officials]
            
            if recent_males:
                target_name = recent_males[-1]  # Most recent
                query = re.sub(r'\bhe\b', target_name, query, flags=re.IGNORECASE)
                query = re.sub(r'\bhim\b', target_name, query, flags=re.IGNORECASE)
                query = re.sub(r'\bhis\b', target_name, query, flags=re.IGNORECASE)
        
        return query
    
    def enhance_query_with_context(self, query: str, session: dict) -> str:
        """Enhance query with conversation context and semantic understanding."""
        
        # 1. Resolve pronouns
        enhanced_query = self.resolve_pronouns(query, session)
        
        # 2. Add implied context from recent conversation
        query_lower = enhanced_query.lower()
        
        # If asking about salary/money without a name, use recent person
        if any(word in query_lower for word in ["salary", "pay", "money", "earn", "make", "income"]) and not any(word in query_lower for word in ["who", "what", "michelle", "elizabeth"]):
            recent_people = []
            for exchange in session["history"][-2:]:
                recent_people.extend(exchange.get("entities", {}).get("people", []))
            if recent_people:
                enhanced_query = f"{recent_people[-1]} {enhanced_query}"
        
        # If asking about time/term without a name, use recent person and prioritize governor
        if any(phrase in query_lower for phrase in ["how long", "when did", "since when", "term", "been in office", "how long has"]) and not any(word in query_lower for word in ["who", "what", "michelle", "elizabeth"]):
            recent_people = []
            for exchange in session["history"][-2:]:
                recent_people.extend(exchange.get("entities", {}).get("people", []))
            if recent_people:
                enhanced_query = f"{recent_people[-1]} {enhanced_query}"
            elif "governor" in query_lower:
                enhanced_query = re.sub(r'\bgovernor\b', "Maura Healey", enhanced_query, flags=re.IGNORECASE)
        
        return enhanced_query
    
    def add_exchange(self, session_id: str, query: str, response: str):
        """Add a conversation exchange to history."""
        session = self.get_session(session_id)
        
        entities = self.extract_entities(f"{query} {response}")
        
        exchange = {
            "query": query,
            "response": response,
            "entities": entities,
            "timestamp": datetime.now().isoformat()
        }
        
        session["history"].append(exchange)
        
        # Update current entities (keep last 3 exchanges worth)
        session["current_entities"] = entities
        
        # Limit history size
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]

# Global conversation engine
conversation_engine = ConversationContext()

# Database initialization with ENHANCED SCHEMA
async def init_database():
    """Initialize the database and populate it with data from CSV if it doesn't exist."""
    try:
        async with aiosqlite.connect(DATABASE_URL) as db:
            # Create the officials table with NEW enhanced columns
            await db.execute('''
                CREATE TABLE IF NOT EXISTS officials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    office TEXT NOT NULL,
                    district_type TEXT,
                    district_number TEXT,
                    district_area TEXT,
                    email TEXT,
                    phone TEXT,
                    website TEXT,
                    x_account TEXT,
                    facebook_page TEXT,
                    level TEXT,
                    party TEXT,
                    term_start_date TEXT,
                    next_election_date TEXT,
                    annual_salary INTEGER,
                    bio_summary TEXT,
                    education TEXT,
                    career_before_office TEXT,
                    key_policy_areas TEXT,
                    committee_memberships TEXT,
                    recent_major_vote TEXT,
                    recent_initiative TEXT,
                    campaign_promises TEXT,
                    responsiveness_score INTEGER,
                    town_halls_per_year TEXT,
                    office_hours TEXT
                )
            ''')

            # Check if table is empty
            cursor = await db.execute("SELECT COUNT(*) FROM officials")
            count = await cursor.fetchone()
            await cursor.close()

            if count[0] == 0:
                # Populate from CSV file with NEW enhanced columns
                if os.path.exists('officials.csv'):
                    with open('officials.csv', 'r', newline='', encoding='utf-8') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            # Handle responsiveness_score conversion (empty string to None)
                            responsiveness_score = None
                            if row.get('responsiveness_score') and row['responsiveness_score'].strip():
                                try:
                                    responsiveness_score = int(row['responsiveness_score'])
                                except ValueError:
                                    responsiveness_score = None

                            # Handle annual_salary conversion
                            annual_salary = None
                            if row.get('annual_salary') and row['annual_salary'].strip():
                                try:
                                    annual_salary = int(row['annual_salary'])
                                except ValueError:
                                    annual_salary = None

                            await db.execute('''
                                INSERT INTO officials (
                                    name, office, district_type, district_number, district_area, 
                                    email, phone, website, x_account, facebook_page, level, party, 
                                    term_start_date, next_election_date, annual_salary,
                                    bio_summary, education, career_before_office, key_policy_areas,
                                    committee_memberships, recent_major_vote, recent_initiative,
                                    campaign_promises, responsiveness_score, town_halls_per_year, office_hours
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                row['name'], row['office'], row.get('district_type', ''), 
                                row.get('district_number', ''), row.get('district_area', ''), 
                                row.get('email', ''), row.get('phone', ''), 
                                row.get('website', ''), row.get('x_account', ''), 
                                row.get('facebook_page', ''), row.get('level', ''),
                                row.get('party', ''), row.get('term_start_date', ''), 
                                row.get('next_election_date', ''), annual_salary,
                                row.get('bio_summary', ''), row.get('education', ''), 
                                row.get('career_before_office', ''), row.get('key_policy_areas', ''),
                                row.get('committee_memberships', ''), row.get('recent_major_vote', ''),
                                row.get('recent_initiative', ''), row.get('campaign_promises', ''),
                                responsiveness_score, row.get('town_halls_per_year', ''), 
                                row.get('office_hours', '')
                            ))
                    await db.commit()
                    print("Database populated with enhanced officials data")
                else:
                    print("Warning: officials.csv not found")
    except Exception as e:
        print(f"Error initializing database: {str(e)}")
        raise

# SEARCH TERM EXTRACTION
def extract_search_terms(query: str) -> str:
    """Extract the actual search terms from natural language queries."""
    query_lower = query.lower().strip()
    original_query = query.strip()
    
    print(f"DEBUG: Processing query: '{query}' -> '{query_lower}'")
    
    # PRIORITY: Handle office queries FIRST
    offices = {
        'mayor': 'mayor',
        'governor': 'governor',
        'senator': 'senator',
        'representative': 'representative',
        'councilor': 'councilor',
        'councillor': 'councilor'
    }
    
    for key, value in offices.items():
        if key in query_lower:
            print(f"DEBUG: Found '{key}' in query")
            return value
    
    # First, try to extract names from the ORIGINAL query (preserves capitalization)
    name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
    names = re.findall(name_pattern, original_query)
    if names:
        print(f"DEBUG: Found name: {names[0]}")
        return names[0]
    
    # Look for names in different question formats
    patterns = [
        (r'\bdid\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+', 'did pattern'),
        (r'\bwhere did\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+', 'where did pattern'),
        (r'\bwhat did\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+', 'what did pattern'),
        (r'\bwhat does\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+', 'what does pattern'),
        (r'\b([a-z]+ [a-z]+)(?:\'s|s)\b', 'possessive pattern')
    ]
    
    for pattern, pattern_name in patterns:
        match = re.search(pattern, query_lower)
        if match:
            result = ' '.join(word.capitalize() for word in match.group(1).split())
            print(f"DEBUG: Found name in '{pattern_name}': {result}")
            return result
    
    # Extract districts
    district_match = re.search(r'district\s+(\d+)', query_lower)
    if district_match:
        result = f"district {district_match.group(1)}"
        print(f"DEBUG: Found district: {result}")
        return result
    
    # Remove common question words and phrases for general search
    query_cleaned = re.sub(r'\b(who is|what is|tell me about|show me|find|search for|about|the|of|boston|educational|background|policy|focus|career|did|does|where|what|has|been|in|office)\b', '', query_lower).strip()
    
    # Final fallback - return cleaned query or original
    result = query_cleaned if query_cleaned else query
    print(f"DEBUG: Final fallback result: '{result}'")
    return result

# SEMANTIC QUERY UNDERSTANDING
class QueryAnalyzer:
    """Understands the intent and semantic meaning of queries."""
    
    @staticmethod
    def analyze_query_intent(query: str) -> dict:
        """Analyze query intent and extract semantic information."""
        query_lower = query.lower().strip()
        
        intent_analysis = {
            "intent_type": "general_search",
            "detail_level": "basic",
            "target_info": [],
            "search_entities": [],
            "temporal_aspect": None
        }
        
        # Determine detail level
        detail_phrases = ['what is', 'tell me about', 'about', 'details']
        basic_phrases = ['who is', 'who']
        
        if any(phrase in query_lower for phrase in detail_phrases):
            intent_analysis["detail_level"] = "detailed"
        elif any(phrase in query_lower for phrase in basic_phrases):
            intent_analysis["detail_level"] = "basic"
        
        # Determine target information
        target_mappings = {
            'salary': ['salary', 'pay', 'money', 'earn', 'make', 'income'],
            'time_in_office': ['how long', 'when did', 'since when', 'term', 'been in office', 'how long has'],
            'contact': ['contact', 'email', 'phone', 'reach'],
            'party': ['party', 'democrat', 'republican', 'affiliation'],
            'education': ['education', 'educational', 'school', 'college', 'university', 'degree', 'studied', 'graduate', 'graduated', 'attend', 'attended', 'alma mater'],
            'career': ['career', 'background', 'before office', 'work', 'job', 'experience', 'worked', 'did before', 'previous job', 'used to do', 'profession', 'occupation'],
            'policy': ['policy', 'policies', 'focus', 'focuses', 'issues', 'priorities', 'works on', 'champions', 'believe', 'believes', 'stands for', 'fights for', 'supports', 'cares about', 'passionate about', 'agenda', 'platform', 'positions', 'views', 'stance', 'advocates', 'committed to']
        }
        
        for target, keywords in target_mappings.items():
            if any(keyword in query_lower for keyword in keywords):
                intent_analysis["target_info"].append(target)
        
        # Extract search entities
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
        intent_analysis["search_entities"].extend(re.findall(name_pattern, query))
        
        offices = ["mayor", "governor", "senator", "representative", "councilor"]
        intent_analysis["search_entities"].extend([office for office in offices if office in query_lower])
        
        district_matches = re.findall(r'district\s+(\d+)', query_lower)
        intent_analysis["search_entities"].extend([f"district {district}" for district in district_matches])
        
        return intent_analysis

# FUZZY MATCHING AND VARIATIONS
def fuzzy_match(text1: str, text2: str, threshold: float = 0.6) -> bool:
    """Check if two strings are similar enough (handles typos)."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio() >= threshold

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

def normalize_search_term(search_term: str) -> str:
    """Normalize search term by checking for common variations and misspellings."""
    search_lower = search_term.lower().strip()
    
    for standard_name, variations in NEIGHBORHOOD_VARIATIONS.items():
        for variation in variations:
            if fuzzy_match(search_lower, variation, 0.8):
                return standard_name
    
    for standard_office, variations in OFFICE_VARIATIONS.items():
        for variation in variations:
            if fuzzy_match(search_lower, variation, 0.8):
                return standard_office
    
    return search_term

async def search_officials(query: str, intent_analysis: dict) -> List[Dict]:
    """Database search logic with enhanced debugging."""
    try:
        async with aiosqlite.connect(DATABASE_URL) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.cursor()
            
            query_lower = query.lower().strip()
            print(f"SEARCH DEBUG: Searching database for: '{query}' (normalized: '{query_lower}')")
            
            # PARTY-BASED SEARCHES
            party_mappings = {
                'democrat': ['democrat', 'democratic', 'dem', 'blue'],
                'republican': ['republican', 'gop', 'red'],
                'nonpartisan': ['nonpartisan', 'non-partisan', 'independent']
            }
            
            for party, keywords in party_mappings.items():
                if any(word in query_lower for word in keywords):
                    print(f"SEARCH DEBUG: Party search - {party.capitalize()}")
                    sql_query = f"""
                        SELECT * FROM officials 
                        WHERE LOWER(party) LIKE '%{party}%'
                        ORDER BY office, name
                    """
                    await cursor.execute(sql_query)
                    results = await cursor.fetchall()
                    await cursor.close()
                    print(f"SEARCH DEBUG: Found {len(results)} {party} officials")
                    if party == 'republican' and not results:
                        return [{"special_message": "no_republicans"}]
                    return [dict(row) for row in results]
            
            # DISTRICT SEARCHES
            district_match = re.search(r'district\s+(\d+)', query_lower)
            if district_match:
                district_num = district_match.group(1)
                print(f"SEARCH DEBUG: District search for district {district_num}")
                sql_query = """
                    SELECT * FROM officials 
                    WHERE district_type = 'District' AND district_number = ?
                """
                await cursor.execute(sql_query, (district_num,))
                results = await cursor.fetchall()
                await cursor.close()
                print(f"SEARCH DEBUG: Found {len(results)} officials in district {district_num}")
                return [dict(row) for row in results]
            
            # OFFICE SEARCHES with intent prioritization
            normalized_query = normalize_search_term(query)
            search_pattern = f"%{normalized_query}%"
            
            print(f"SEARCH DEBUG: Office search with pattern: '{search_pattern}'")
            if "time_in_office" in intent_analysis["target_info"] and normalized_query in ["governor", "mayor"]:
                # Prioritize the primary office holder (e.g., Governor or Mayor) for time
                sql_query = """
                    SELECT * FROM officials 
                    WHERE LOWER(office) LIKE LOWER(?) AND name IN ('Maura Healey', 'Michelle Wu')
                    LIMIT 1
                """
                await cursor.execute(sql_query, (search_pattern,))
                results = await cursor.fetchall()
                if results:
                    print(f"SEARCH DEBUG: Time-in-office search found {len(results)} result")
                    await cursor.close()
                    return [dict(row) for row in results]
            elif "contact" in intent_analysis["target_info"] and normalized_query in ["governor", "mayor"]:
                # Prioritize the primary office holder (e.g., Governor or Mayor) for contact
                sql_query = """
                    SELECT * FROM officials 
                    WHERE LOWER(office) LIKE LOWER(?) AND name IN ('Maura Healey', 'Michelle Wu')
                    LIMIT 1
                """
                await cursor.execute(sql_query, (search_pattern,))
                results = await cursor.fetchall()
                if results:
                    print(f"SEARCH DEBUG: Contact search found {len(results)} result")
                    await cursor.close()
                    return [dict(row) for row in results]
            elif "party" in intent_analysis["target_info"] and normalized_query == "senator":
                # Prioritize Elizabeth Warren for party
                sql_query = """
                    SELECT * FROM officials 
                    WHERE LOWER(office) LIKE ? AND level = 'Federal' AND name = 'Elizabeth Warren'
                    LIMIT 1
                """
                await cursor.execute(sql_query, ('%senator%',))
                results = await cursor.fetchall()
                print(f"SEARCH DEBUG: Party search found {len(results)} result")
                if results:
                    await cursor.close()
                    return [dict(row) for row in results]
            elif "education" in intent_analysis["target_info"]:
                # Prioritize Elizabeth Warren for education with explicit office match
                print(f"SEARCH DEBUG: Entering education intent block for normalized_query: '{normalized_query}'")
                sql_query = """
                    SELECT * FROM officials 
                    WHERE LOWER(office) IN ('senator', 'u.s. senator') AND level = 'Federal' AND name = 'Elizabeth Warren'
                    LIMIT 1
                """
                await cursor.execute(sql_query)
                results = await cursor.fetchall()
                print(f"SEARCH DEBUG: Education search query executed, results: {results}")
                if results:
                    await cursor.close()
                    return [dict(row) for row in results]
            elif "policy" in intent_analysis["target_info"] and normalized_query == "mayor":
                # Prioritize Michelle Wu for policy
                sql_query = """
                    SELECT * FROM officials 
                    WHERE LOWER(office) LIKE ? AND name = 'Michelle Wu'
                    LIMIT 1
                """
                await cursor.execute(sql_query, ('%mayor%',))
                results = await cursor.fetchall()
                print(f"SEARCH DEBUG: Policy search found {len(results)} result")
                if results:
                    await cursor.close()
                    return [dict(row) for row in results]
            
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(office) LIKE LOWER(?)
            """
            if "salary" in intent_analysis["target_info"]:
                sql_query += " AND annual_salary IS NOT NULL"
            await cursor.execute(sql_query, (search_pattern,))
            results = await cursor.fetchall()
            
            print(f"SEARCH DEBUG: Office search found {len(results)} results")
            for result in results:
                print(f"SEARCH DEBUG: - {result['name']} ({result['office']})")
            
            if results:
                await cursor.close()
                return [dict(row) for row in results]
            
            # NAME-BASED SEARCHES
            print(f"SEARCH DEBUG: Trying name search with pattern: '{search_pattern}'")
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(name) LIKE LOWER(?)
            """
            if "salary" in intent_analysis["target_info"]:
                sql_query += " AND annual_salary IS NOT NULL"
            await cursor.execute(sql_query, (search_pattern,))
            results = await cursor.fetchall()
            
            print(f"SEARCH DEBUG: Name search found {len(results)} results")
            
            if results:
                await cursor.close()
                return [dict(row) for row in results]
            
            # GENERAL SEARCH (fallback)
            print(f"SEARCH DEBUG: Trying general search with pattern: '{search_pattern}'")
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(name) LIKE LOWER(?) 
                OR LOWER(office) LIKE LOWER(?)
                OR LOWER(level) LIKE LOWER(?)
            """
            if "salary" in intent_analysis["target_info"]:
                sql_query += " AND annual_salary IS NOT NULL"
            await cursor.execute(sql_query, (search_pattern, search_pattern, search_pattern))
            results = await cursor.fetchall()
            await cursor.close()
            
            print(f"SEARCH DEBUG: General search found {len(results)} results")
            return [dict(row) for row in results]
    except Exception as e:
        print(f"SEARCH DEBUG: Error in search_officials: {str(e)}")
        return []

# RESPONSE GENERATOR
class ResponseGenerator:
    """Generates contextually appropriate responses using rich biographical data."""
    
    @staticmethod
    def calculate_time_in_office(start_date_str: str) -> str:
        """Calculate how long someone has been in office."""
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            current_date = datetime.now()
            difference = current_date - start_date
            
            years = difference.days // 365
            months = (difference.days % 365) // 30
            
            if years > 0:
                return f"{years} year{'s' if years != 1 else ''} and {months} month{'s' if months != 1 else ''}"
            elif months > 0:
                return f"{months} month{'s' if months != 1 else ''}"
            else:
                return f"{difference.days} day{'s' if difference.days != 1 else ''}"
        except:
            return "unknown duration"
    
    @staticmethod
    def generate_response(officials: List[Dict], intent_analysis: dict, original_query: str) -> str:
        """Generate intelligent, contextually appropriate responses using enhanced biographical data."""
        if not officials:
            return f"I couldn't find any officials matching '{original_query}'. Try searching by name, office, or party."
        
        # Handle special messages
        if officials[0].get("special_message") == "no_republicans":
            return """**No Republican officials found in Boston government.**

Boston city elections (Mayor, City Council) are officially **nonpartisan** - candidates don't run with party labels. However, most Boston officials are Democrats.

At the state and federal level representing Boston, officials are predominantly Democratic."""
        
        # Single official responses
        if len(officials) == 1:
            official = officials[0]
            
            # EDUCATION-FOCUSED RESPONSES
            if "education" in intent_analysis["target_info"]:
                if official.get('education') and official['education'].strip():
                    return f"**{official['name']}** graduated from **{official['education']}**."
                else:
                    return f"I don't have educational background information for **{official['name']}**."
            
            # CAREER/BACKGROUND-FOCUSED RESPONSES
            if "career" in intent_analysis["target_info"]:
                if official.get('career_before_office') and official['career_before_office'].strip():
                    return f"**Before entering office, {official['name']}** worked as: {official['career_before_office']}."
                else:
                    return f"I don't have career background information for **{official['name']}**."
            
            # POLICY/FOCUS-FOCUSED RESPONSES
            if "policy" in intent_analysis["target_info"]:
                if official.get('key_policy_areas') and official['key_policy_areas'].strip():
                    return f"**{official['name']}** focuses on: **{official['key_policy_areas']}**."
                else:
                    return f"I don't have policy focus information for **{official['name']}**."
            
            # SALARY-FOCUSED RESPONSES
            if "salary" in intent_analysis["target_info"]:
                if official.get('annual_salary'):
                    return f"**{official['name']}** earns **${official['annual_salary']:,}** per year as {official['office']}."
                else:
                    return f"I don't have salary information for **{official['name']}**."
            
            # TIME-IN-OFFICE RESPONSES
            if "time_in_office" in intent_analysis["target_info"]:
                if official.get('term_start_date'):
                    duration = ResponseGenerator.calculate_time_in_office(official['term_start_date'])
                    return f"**{official['name']}** has been {official['office']} since **{official['term_start_date']}** ({duration})."
                else:
                    return f"I don't have the start date information for **{official['name']}**."
            
            # CONTACT-FOCUSED RESPONSES
            if "contact" in intent_analysis["target_info"]:
                contact_info = f"**Contact {official['name']}**\n"
                contact_info += f"📧 Email: {official['email'] or 'N/A'}\n"
                contact_info += f"📞 Phone: {official['phone'] or 'N/A'}\n"
                contact_info += f"🌐 Website: {official['website'] or 'N/A'}\n"
                contact_info += f"𝕏 Account: {official['x_account'] or 'N/A'}\n"
                contact_info += f"Facebook: {official['facebook_page'] or 'N/A'}"
                return contact_info
            
            # PARTY-FOCUSED RESPONSES
            if "party" in intent_analysis["target_info"]:
                if official.get('party'):
                    return f"**{official['name']}** is affiliated with the **{official['party']}** party."
                else:
                    return f"I don't have party affiliation information for **{official['name']}**."
            
            # DETAILED BIO RESPONSE
            if intent_analysis["detail_level"] == "detailed":
                response = f"**{official['name']}** - {official['office']}\n\n"
                fields = [
                    ('bio_summary', 'Bio'),
                    ('education', 'Education'),
                    ('career_before_office', 'Prior Career'),
                    ('key_policy_areas', 'Policy Focus'),
                    ('committee_memberships', 'Committees'),
                    ('recent_major_vote', 'Recent Vote'),
                    ('recent_initiative', 'Recent Initiative'),
                    ('campaign_promises', 'Campaign Promises'),
                    ('office_hours', 'Office Hours')
                ]
                
                for field, label in fields:
                    if official.get(field) and official[field].strip():
                        response += f"**{label}**: {official[field]}\n"
                
                if official.get('term_start_date'):
                    duration = ResponseGenerator.calculate_time_in_office(official['term_start_date'])
                    response += f"**Time in Office**: Since {official['term_start_date']} ({duration})\n"
                
                if official.get('next_election_date'):
                    response += f"**Next Election**: {official['next_election_date']}\n"
                
                if official.get('annual_salary'):
                    response += f"**Salary**: ${official['annual_salary']:,} per year\n"
                
                if official.get('responsiveness_score'):
                    response += f"**Responsiveness Score**: {official['responsiveness_score']}/100\n"
                
                if official.get('town_halls_per_year'):
                    response += f"**Town Halls**: {official['town_halls_per_year']} per year\n"
                
                return response.strip()
            
            # BASIC RESPONSE (default for single official)
            response = f"**{official['name']}** is the {official['office']} of "
            if official.get('district_type') and official.get('district_number'):
                response += f"{official['district_type']} {official['district_number']}"
            elif official.get('district_area'):
                response += f"{official['district_area']}"
            else:
                response += f"{official.get('level', 'Boston')}"
            if official.get('party'):
                response += f" ({official['party']})"
            response += "."
            return response
        
        # MULTIPLE OFFICIALS RESPONSE
        response = "**Found multiple officials matching your query**:\n\n"
        for official in officials:
            response += f"- **{official['name']}**, {official['office']}"
            if official.get('district_type') and official.get('district_number'):
                response += f" ({official['district_type']} {official['district_number']})"
            elif official.get('district_area'):
                response += f" ({official['district_area']})"
            response += "\n"
        return response.strip()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    try:
        await init_database()
    except Exception as e:
        print(f"Failed to initialize database: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to initialize database")

# API ENDPOINTS
@app.post("/ask/")
async def ask(request: QueryRequest):
    """POST endpoint to match the HTML interface."""
    return await search(request.query, request.session_id)

@app.get("/search")
async def search(query: str, session_id: str = "default"):
    """Main search endpoint - handles both GET and POST requests."""
    try:
        session = conversation_engine.get_session(session_id)
        enhanced_query = conversation_engine.enhance_query_with_context(query, session)

        # Analyze query intent
        intent_analysis = QueryAnalyzer.analyze_query_intent(enhanced_query)
        entities = conversation_engine.extract_entities(enhanced_query)

        # 🔍 DEBUG LOGGING
        print("Enhanced Query:", enhanced_query)
        print("Intent Analysis:", intent_analysis)
        print("Entities:", entities)

        # Extract search terms
        search_term = extract_search_terms(enhanced_query)

        # Search database
        officials = await search_officials(search_term, intent_analysis)

        # Generate response
        response = ResponseGenerator.generate_response(officials, intent_analysis, query)

        # Store conversation exchange
        conversation_engine.add_exchange(session_id, query, response)

        return {"response": response}
    except Exception as e:
        print(f"Error in search endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/", response_class=HTMLResponse)
async def serve_html():
    """Serve the HTML interface."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="HTML file not found")