from app import extract_search_terms, QueryAnalyzer

query = "how much does the mayor make"

search_term = extract_search_terms(query)
intent_analysis = QueryAnalyzer.analyze_query_intent(query)

print("Search term:", search_term)
print("Intent analysis:", intent_analysis)
