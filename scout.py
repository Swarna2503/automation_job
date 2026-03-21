import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ==========================================
# ⚙️ USER CONFIGURATION
# ==========================================
USER_PREFERENCES = {
    # Keep it simple: Title + Remote
    "job_keywords": '"Python" ("Developer" OR "Engineer") "Remote"',
    
    "search_skills": ["LLMs", "AWS", "PyTorch", "Spark"], 
    
    "max_experience_years": 3,
    
    "blocked_sites": ["indeed.com", "linkedin.com", "ziprecruiter.com", "glassdoor.com", "builtin.com", "simplyhired.com", "dice.com", "reddit.com"]
}
# ==========================================

def build_search_query(prefs):
    """Builds a lightweight, highly effective Google Dork."""
    query = f'{prefs["job_keywords"]}'
    
    # Add skills (Limit to 4 max)
    if prefs.get("search_skills"):
        skills_str = " OR ".join([f'"{skill}"' for skill in prefs["search_skills"]])
        query += f" ({skills_str})"
        
    # Filter Seniority
    if prefs.get("max_experience_years", 0) < 4:
        query += " -Senior -Lead -Principal -Manager -Director -Staff"
        
    # Block Aggregators (This naturally leaves company career pages)
    if prefs.get("blocked_sites"):
        block_str = " ".join([f"-site:{site}" for site in prefs["blocked_sites"]])
        query += f" {block_str}"
    
    return query

def find_jobs(query):
    """Searches Google using SerpApi for the last 24 hours."""
    params = {
      "engine": "google",
      "q": query,
      "api_key": SERPAPI_KEY,
      "num": 30,       
      "tbs": "qdr:d",  # Last 24 Hours
      "gl": "us",      # Tell Google to search strictly from the United States
      "hl": "en"       # English results only
    }

    print(f"🔍 Executing Streamlined 24-Hour Search:\n{query}\n")
    search = GoogleSearch(params)
    results = search.get_dict()

    organic_results = results.get("organic_results", [])
    job_urls = []

    for result in organic_results:
        link = result.get("link")
        title = result.get("title")
        print(f"✅ Found: {title}")
        print(f"🔗 URL: {link}\n")
        job_urls.append(link)

    return job_urls

if __name__ == "__main__":
    dynamic_query = build_search_query(USER_PREFERENCES)
    urls = find_jobs(dynamic_query)
    print(f"🎯 Total links scraped from the open web (Last 24 Hrs): {len(urls)}")