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
            # Look for recent female officials
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
            # Look for recent male officials
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
        
        # If asking about time/term without a name, use recent person
        if any(phrase in query_lower for phrase in ["how long", "when did", "since when", "term"]) and not any(word in query_lower for word in ["who", "what", "michelle", "elizabeth"]):
            recent_people = []
            for exchange in session["history"][-2:]:
                recent_people.extend(exchange.get("entities", {}).get("people", []))
            if recent_people:
                enhanced_query = f"{recent_people[-1]} {enhanced_query}"
        
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
                            row['name'], row['office'], row['district_type'], 
                            row['district_number'], row['district_area'], row['email'], row['phone'], 
                            row['website'], row['x_account'], row['facebook_page'], row['level'],
                            row['party'], row['term_start_date'], row['next_election_date'], 
                            int(row['annual_salary']) if row['annual_salary'] and row['annual_salary'].strip() else None,
                            # NEW enhanced columns (populated with rich data)
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

# SEARCH TERM EXTRACTION
def extract_search_terms(query: str) -> str:
    """Extract the actual search terms from natural language queries."""
    query_lower = query.lower().strip()
    original_query = query.strip()
    
    # First, try to extract names from the ORIGINAL query (preserves capitalization)
    name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
    names = re.findall(name_pattern, original_query)
    if names:
        return names[0]
    
    # Look for names in different question formats
    # Handle "Did [Name] [verb]" patterns
    did_pattern = r'\bdid\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+'
    did_match = re.search(did_pattern, query_lower)
    if did_match:
        return ' '.join(word.capitalize() for word in did_match.group(1).split())
    
    # Handle "Where did [Name] [verb]" patterns  
    where_did_pattern = r'\bwhere did\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+'
    where_did_match = re.search(where_did_pattern, query_lower)
    if where_did_match:
        return ' '.join(word.capitalize() for word in where_did_match.group(1).split())
    
    # Handle "What did [Name] [verb]" patterns
    what_did_pattern = r'\bwhat did\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+'
    what_did_match = re.search(what_did_pattern, query_lower)
    if what_did_match:
        return ' '.join(word.capitalize() for word in what_did_match.group(1).split())
    
    # Handle "What does [Name] [verb]" patterns
    what_does_pattern = r'\bwhat does\s+([a-z]+ [a-z]+(?:\s[a-z]+)*)\s+'
    what_does_match = re.search(what_does_pattern, query_lower)
    if what_does_match:
        return ' '.join(word.capitalize() for word in what_does_match.group(1).split())
    
    # Look for names in possessive format (handles "michelle wu's")
    possessive_pattern = r'\b([a-z]+ [a-z]+)\'s\b'
    possessive_names = re.findall(possessive_pattern, query_lower)
    if possessive_names:
        # Convert to Title Case
        return ' '.join(word.capitalize() for word in possessive_names[0].split())
    
    # Handle specific office patterns
    if 'mayor' in query_lower:
        return 'mayor'
    elif 'governor' in query_lower:
        return 'governor'
    elif 'senator' in query_lower:
        return 'senator'
    elif 'representative' in query_lower:
        return 'representative'
    elif 'councilor' in query_lower or 'councillor' in query_lower:
        return 'councilor'
    
    # Extract districts
    district_match = re.search(r'district\s+(\d+)', query_lower)
    if district_match:
        return f"district {district_match.group(1)}"
    
    # Remove common question words and phrases for general search
    query_cleaned = re.sub(r'\b(who is|what is|tell me about|show me|find|search for|about|the|of|boston|educational|background|policy|focus|career|did|does|where|what)\b', '', query_lower).strip()
    
    # Final fallback - return cleaned query or original
    return query_cleaned if query_cleaned else query

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
        if any(phrase in query_lower for phrase in ['what is', 'tell me about', 'about', 'details']):
            intent_analysis["detail_level"] = "detailed"
        elif any(phrase in query_lower for phrase in ['who is', 'who']):
            intent_analysis["detail_level"] = "basic"
        
        # Determine target information
        if any(word in query_lower for word in ['salary', 'pay', 'money', 'earn', 'make', 'income']):
            intent_analysis["target_info"].append("salary")
        
        if any(phrase in query_lower for phrase in ['how long', 'when did', 'since when', 'term', 'time in office']):
            intent_analysis["target_info"].append("time_in_office")
        
        if any(word in query_lower for word in ['contact', 'email', 'phone', 'reach']):
            intent_analysis["target_info"].append("contact")
        
        if any(word in query_lower for word in ['party', 'democrat', 'republican', 'affiliation']):
            intent_analysis["target_info"].append("party")
        
        # Extract search entities
        # Names
        name_pattern = r'\b([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b'
        names = re.findall(name_pattern, query)
        intent_analysis["search_entities"].extend(names)
        
        # Offices
        offices = ["mayor", "governor", "senator", "representative", "councilor"]
        for office in offices:
            if office in query_lower:
                intent_analysis["search_entities"].append(office)
        
        # Districts
        district_matches = re.findall(r'district\s+(\d+)', query_lower)
        for district in district_matches:
            intent_analysis["search_entities"].append(f"district {district}")
        
        return intent_analysis

# KEEPING ALL OUR PROVEN SEARCH CODE
def fuzzy_match(text1, text2, threshold=0.6):
    """Check if two strings are similar enough (handles typos)"""
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

async def search_officials(query: str) -> List[Dict]:
    """PROVEN search logic that actually works."""
    async with aiosqlite.connect(DATABASE_URL) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.cursor()
        
        query_lower = query.lower().strip()
        print(f"Searching for: '{query}'")
        
        # PARTY-BASED SEARCHES
        if any(word in query_lower for word in ['democrat', 'democratic', 'dem', 'blue']):
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(party) LIKE '%democrat%'
                ORDER BY office, name
            """
            await cursor.execute(sql_query)
            results = await cursor.fetchall()
            return [dict(row) for row in results]
        
        if any(word in query_lower for word in ['republican', 'gop', 'red']):
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(party) LIKE '%republican%' OR LOWER(party) LIKE '%gop%'
            """
            await cursor.execute(sql_query)
            republicans = await cursor.fetchall()
            
            if not republicans:
                return [{"special_message": "no_republicans"}]
            else:
                return [dict(row) for row in republicans]
        
        if any(word in query_lower for word in ['nonpartisan', 'non-partisan', 'independent']):
            sql_query = """
                SELECT * FROM officials 
                WHERE LOWER(party) LIKE '%nonpartisan%' OR LOWER(party) LIKE '%independent%'
                ORDER BY office, name
            """
            await cursor.execute(sql_query)
            results = await cursor.fetchall()
            return [dict(row) for row in results]
        
        # DISTRICT SEARCHES FIRST
        district_match = re.search(r'district\s+(\d+)', query_lower)
        if district_match:
            district_num = district_match.group(1)
            sql_query = """
                SELECT * FROM officials 
                WHERE district_type = 'District' AND district_number = ?
            """
            await cursor.execute(sql_query, (district_num,))
            results = await cursor.fetchall()
            return [dict(row) for row in results]
        
        # OFFICE SEARCHES (FIXED - this was broken)
        normalized_query = normalize_search_term(query)
        search_pattern = f"%{normalized_query}%"
        
        # Try office search FIRST for queries like "mayor"
        sql_query = """
            SELECT * FROM officials 
            WHERE LOWER(office) LIKE LOWER(?)
        """
        await cursor.execute(sql_query, (search_pattern,))
        results = await cursor.fetchall()
        
        if results:
            return [dict(row) for row in results]
        
        # NAME-BASED SEARCHES
        sql_query = """
            SELECT * FROM officials 
            WHERE LOWER(name) LIKE LOWER(?)
        """
        await cursor.execute(sql_query, (search_pattern,))
        results = await cursor.fetchall()
        
        if results:
            return [dict(row) for row in results]
        
        # GENERAL SEARCH (fallback)
        sql_query = """
            SELECT * FROM officials 
            WHERE LOWER(name) LIKE LOWER(?) 
            OR LOWER(office) LIKE LOWER(?)
            OR LOWER(level) LIKE LOWER(?)
        """
        await cursor.execute(sql_query, (search_pattern, search_pattern, search_pattern))
        results = await cursor.fetchall()
        
        return [dict(row) for row in results]

# ENHANCED RESPONSE GENERATOR WITH BIOGRAPHICAL DATA
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
            
            # EDUCATION-FOCUSED RESPONSES (More flexible detection)
            if any(word in original_query.lower() for word in ['education', 'educational', 'school', 'college', 'university', 'degree', 'studied', 'graduate', 'graduated', 'attend', 'attended', 'alma mater', 'where did', 'went to school', 'go to school', 'go to college']):
                if official.get('education') and official['education'].strip():
                    return f"**{official['name']}** graduated from **{official['education']}**."
                else:
                    return f"I don't have educational background information for **{official['name']}**."
            
            # CAREER/BACKGROUND-FOCUSED RESPONSES (More flexible detection)
            if any(phrase in original_query.lower() for phrase in ['career', 'background', 'before office', 'work', 'job', 'experience', 'worked', 'did before', 'previous job', 'used to do', 'profession', 'occupation']):
                if official.get('career_before_office') and official['career_before_office'].strip():
                    return f"**Before entering office, {official['name']}** worked as: {official['career_before_office']}."
                else:
                    return f"I don't have career background information for **{official['name']}**."
            
            # POLICY/FOCUS-FOCUSED RESPONSES (Much more flexible detection)
            if any(word in original_query.lower() for word in ['policy', 'policies', 'focus', 'focuses', 'issues', 'priorities', 'works on', 'champions', 'believe', 'believes', 'stands for', 'fights for', 'supports', 'cares about', 'passionate about', 'agenda', 'platform', 'positions', 'views', 'stance', 'advocates', 'committed to']):
                if official.get('key_policy_areas') and official['key_policy_areas'].strip():
                    return f"**{official['name']}** focuses on: **{official['key_policy_areas']}**."
                else:
                    return f"I don't have policy focus information for **{official['name']}**."
            
            # SALARY-FOCUSED RESPONSES
            if "salary" in intent_analysis["target_info"]:
                if official['annual_salary']:
                    return f"**{official['name']}** earns **${official['annual_salary']:,} per year** as {official['office']}."
                else:
                    return f"I don't have salary information for **{official['name']}**."
            
            # TIME-IN-OFFICE RESPONSES
            if "time_in_office" in intent_analysis["target_info"]:
                if official['term_start_date']:
                    duration = ResponseGenerator.calculate_time_in_office(official['term_start_date'])
                    return f"**{official['name']}** has been {official['office']} since **{official['term_start_date']}** ({duration})."
                else:
                    return f"I don't have the start date information for **{official['name']}**."
            
            # CONTACT-FOCUSED RESPONSES
            if "contact" in intent_analysis["target_info"]:
                result = f"**Contact {official['name']}:**\n"
                if official['email']:
                    result += f"📧 {official['email']}\n"
                if official['phone']:
                    result += f"📞 {official['phone']}\n"
                if official['website']:
                    result += f"🌐 {official['website']}\n"
                return result
            
            # DETAILED INFO RESPONSES (Enhanced with biographical data)
            if intent_analysis["detail_level"] == "detailed":
                result_text = f"**{official['name']}** - {official['office']}"
                if official['district_type'] and official['district_number']:
                    result_text += f" ({official['district_type']} {official['district_number']})"
                
                result_text += "\n"
                
                # Add biographical summary if available
                if official.get('bio_summary') and official['bio_summary'].strip():
                    result_text += f"📋 **Background:** {official['bio_summary']}\n"
                
                # Add education if available
                if official.get('education') and official['education'].strip():
                    result_text += f"🎓 **Education:** {official['education']}\n"
                
                # Add career background if available
                if official.get('career_before_office') and official['career_before_office'].strip():
                    result_text += f"💼 **Career Before Office:** {official['career_before_office']}\n"
                
                # Add policy focus if available
                if official.get('key_policy_areas') and official['key_policy_areas'].strip():
                    result_text += f"🎯 **Policy Focus:** {official['key_policy_areas']}\n"
                
                if official['party']:
                    party_emoji = "🔵" if "Democrat" in official['party'] else "🔴" if "Republican" in official['party'] else "⚫"
                    result_text += f"{party_emoji} **Party:** {official['party']}\n"
                if official['annual_salary']:
                    result_text += f"💰 **Annual Salary:** ${official['annual_salary']:,}\n"
                if official['term_start_date']:
                    duration = ResponseGenerator.calculate_time_in_office(official['term_start_date'])
                    result_text += f"📅 **In Office Since:** {official['term_start_date']} ({duration})\n"
                if official['next_election_date']:
                    result_text += f"🗳️ **Next Election:** {official['next_election_date']}\n"
                
                result_text += "\n**Contact:**\n"
                if official['email']:
                    result_text += f"📧 {official['email']}\n"
                if official['phone']:
                    result_text += f"📞 {official['phone']}\n"
                if official['website']:
                    result_text += f"🌐 {official['website']}\n"
                
                return result_text
            
            # BASIC RESPONSES (Enhanced with bio summary)
            else:
                basic_response = f"**{official['name']}**"
                
                # Add compelling bio summary if available
                if official.get('bio_summary') and official['bio_summary'].strip():
                    basic_response += f" - {official['bio_summary']}"
                
                return basic_response
        
        # Multiple officials
        else:
            result = f"Found {len(officials)} officials:\n\n"
            for i, official in enumerate(officials[:8], 1):
                result += f"**{i}. {official['name']}** - {official['office']}"
                if official['party']:
                    party_emoji = "🔵" if "Democrat" in official['party'] else "🔴" if "Republican" in official['party'] else "⚫"
                    result += f" ({party_emoji} {official['party']})"
                
                # Add bio summary for multiple results if available
                if official.get('bio_summary') and official['bio_summary'].strip():
                    result += f"\n   📋 {official['bio_summary']}"
                
                result += f"\n📧 {official['email']}\n\n"
            
            return result

# MAIN CONVERSATION PROCESSOR
async def process_conversation(query: str, session_id: str = "default") -> str:
    """Main conversation processing pipeline."""
    
    # 1. Get conversation session
    session = conversation_engine.get_session(session_id)
    
    # 2. Enhance query with conversation context
    enhanced_query = conversation_engine.enhance_query_with_context(query, session)
    
    # 2.5. EXTRACT KEY SEARCH TERMS (fix for "Who is the mayor?" type queries)
    search_query = extract_search_terms(enhanced_query)
    
    # 3. Analyze query intent
    analyzer = QueryAnalyzer()
    intent_analysis = analyzer.analyze_query_intent(enhanced_query)
    
    # 4. Search officials database
    officials = await search_officials(search_query)
    
    # 5. Generate intelligent response
    generator = ResponseGenerator()
    response = generator.generate_response(officials, intent_analysis, query)
    
    # 6. Add to conversation history
    conversation_engine.add_exchange(session_id, query, response)
    
    return response

# API ENDPOINTS
class QueryModel(BaseModel):
    query: str
    session_id: str = "default"

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
async def ask_civic_ai(query_model: QueryModel):
    """Custom civic AI conversation endpoint."""
    print(f"Received query: {query_model.query} (Session: {query_model.session_id})")
    
    try:
        # Process through custom conversation engine
        response = await process_conversation(query_model.query, query_model.session_id)
        print(f"AI response: {response}")
        return {"response": response}
    
    except Exception as e:
        print(f"Error during conversation processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/debug/conversation/{session_id}")
async def debug_conversation(session_id: str):
    """Debug endpoint to view conversation state."""
    session = conversation_engine.get_session(session_id)
    return {
        "session_id": session_id,
        "history_count": len(session["history"]),
        "current_entities": session["current_entities"],
        "recent_exchanges": session["history"][-3:] if session["history"] else []
    }