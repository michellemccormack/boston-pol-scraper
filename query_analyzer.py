import re

class QueryAnalyzer:
    @staticmethod
    def analyze_query_intent(query: str) -> dict:
        intent = {}
        query_lower = query.lower()
        if "salary" in query_lower:
            intent["target_info"] = "salary"
        elif "contact" in query_lower:
            intent["target_info"] = "contact"
        elif "education" in query_lower:
            intent["target_info"] = "education"
        elif "background" in query_lower or "career" in query_lower:
            intent["target_info"] = "career"
        else:
            intent["target_info"] = "general"
        return intent

    @staticmethod
    def extract_entities(query: str) -> list:
        return re.findall(r"[A-Z][a-z]+(?:\s[A-Z][a-z]+)*", query)
