import os
import json
import time
import csv
from serpapi import GoogleSearch
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# ⚙️ INITIALIZATION
# ==========================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PREFS = {
    # Added a space between parentheses and focused on US/Remote
    "job_keywords": 'Python (Developer OR Engineer OR "Machine Learning" OR "Data Scientist") ("United States" OR "US" OR USA) ("Remote" OR "Work from home")',
    
    # Keeping search skills broad to increase the "Net" size
    "search_skills": ["LLMs", "PyTorch", "NLP", "RAG"], 
    
    "blocked_sites": [
        "indeed.com", "linkedin.com", "ziprecruiter.com", "reddit.com", 
        "stackoverflow.com", "github.com", "onlinejobs.ph", "naukri.com", 
        "builtin.com", "simplyhired.com", "dice.com", "glassdoor.com"
    ],
    
    "max_experience_years": 3,
    "my_skills": [
        "Python", "SQL", "R", "C/C++", "Java", "ADK", "LLMs", "RAG", "Clustering", 
        "Segmentation", "Recommendation Systems", "NLP", "Feature Engineering",  
        "Scikit-Learn", "PyTorch", "TensorFlow", "Autoencoders", "Hive", "AWS", 
        "Apache Spark", "PySpark", "Hadoop", "MongoDB", "Git"
    ]
}

# ==========================================
# 🔍 PHASE 1: THE FILTERED SCOUT
# ==========================================
def find_jobs(prefs, target_count=100):
    all_urls = []
    
    # Build Query: Logic uses OR for skills to expand results
    query = f'{prefs["job_keywords"]}'
    if prefs.get("search_skills"):
        skills_str = " OR ".join([f'"{s}"' for s in prefs["search_skills"]])
        query += f" ({skills_str})"
    
    # Google Dorking for ATS sites (Greenhouse, Lever, etc.)
    query += ' (site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR "Apply")'
    query += " -Senior -Lead -Principal -Manager -Director -Staff"
    
    if prefs.get("blocked_sites"):
        block_str = " ".join([f"-site:{site}" for site in prefs["blocked_sites"]])
        query += f" {block_str}"

    print(f"🔍 SCOUTING: Target {target_count} roles (last 24 hours)...")
    
    for start in range(0, target_count, 10):
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY,
            "start": start,
            "tbs": "qdr:d", # Last 24 Hours
            "gl": "us", 
            "hl": "en",
            "cr": "countryUS" # Restrict results to US
        }
        
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        if not results: break
            
        for res in results:
            link = res.get("link")
            if link:
                all_urls.append(link)
        
        print(f"   Page {start//10 + 1}: Captured {len(all_urls)} potential links...")
        if len(all_urls) >= target_count: break
        time.sleep(1) 

    return list(set(all_urls))

# ==========================================
# 🕷️ PHASE 2A: THE SCRAPER
# ==========================================
def scrape_webpage(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(2000)
            text = page.inner_text("body")
            browser.close()
            return text
    except:
        return None

# ==========================================
# 🧠 PHASE 2B: THE AI BRAIN
# ==========================================
def evaluate_job(text, skills, max_exp):
    prompt = f"""
    Evaluate this job for a candidate with max {max_exp} years experience.
    Candidate Skills: {', '.join(skills)}
    
    RULES:
    1. If req exp > {max_exp}, score = 0.
    2. If location is NOT US or Remote-US, score = 0.
    3. Score 0-100 based on matches.
    
    Return ONLY JSON:
    {{"years": int, "score": int, "reason": "str"}}
    
    Text: {text[:7000]}
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return {"score": 0, "reason": "AI Error"}

# ==========================================
# 🚀 EXECUTION
# ==========================================
if __name__ == "__main__":
    job_links = find_jobs(PREFS, target_count=100)
    
    if not job_links:
        print("❌ No links found. Try removing some 'blocked_sites' or broadening keywords.")
        exit()

    print(f"\n--- 🔗 RAW LINKS FOUND ({len(job_links)}) ---")
    for i, url in enumerate(job_links, 1):
        print(f"{i}. {url}")
    print("-------------------------------------------\n")

    scored_jobs = []
    
    for i, url in enumerate(job_links, 1):
        print(f"[{i}/{len(job_links)}] Analyzing: {url[:60]}...")
        content = scrape_webpage(url)
        
        # Diagnostic: Skip reason
        if not content:
            print("   ⚠️ SKIP: Scraper failed/Blocked.")
            continue
        if len(content) < 500:
            print(f"   ⚠️ SKIP: Content too short ({len(content)} chars).")
            continue
            
        eval_data = evaluate_job(content, PREFS["my_skills"], PREFS["max_experience_years"])
        
        # Save results regardless of score for manual debugging
        scored_jobs.append({
            "score": eval_data.get("score", 0),
            "years": eval_data.get("years", "N/A"),
            "reason": eval_data.get("reason", "N/A"),
            "url": url
        })
        print(f"   ✅ Processed. AI Score: {eval_data.get('score')}")
        time.sleep(2)

    scored_jobs.sort(key=lambda x: x['score'], reverse=True)
    
    with open("diagnostic_results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["score", "years", "reason", "url"])
        writer.writeheader()
        writer.writerows(scored_jobs)
        
    print(f"\n🎉 DONE! Saved {len(scored_jobs)} analyzed links to diagnostic_results.csv")