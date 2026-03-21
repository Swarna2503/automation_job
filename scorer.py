import os
import json
import time
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# ⚙️ INITIALIZATION
# ==========================================
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ==========================================
# ⚙️ USER CONFIGURATION
# ==========================================
TEST_URLS = [
    # The heavy JavaScript site (Gem.com)
    "https://jobs.apple.com/en-ca/details/200652249-3956/software-engineer-agentic-ai-ai-data-platforms",
    # The Location test (Ukraine)
    "https://www.globallogic.com/uki/careers/trainee-associate-ml-developer-irc291744/",
    # The Apple test (Heavy ATS)
    "https://jobs.insightpartners.com/companies/marigold-2/jobs/71243277-associate-software-engineer"
]

MY_SKILLS = [
    "Python", "SQL", "R", "C/C++", "Java", "ADK", "LLMs", "RAG", "Clustering", 
    "Segmentation", "Recommendation Systems", "NLP", "Feature Engineering",  
    "Scikit-Learn", "PyTorch", "TensorFlow", "Autoencoders", "Hive", "AWS", 
    "Apache Spark", "PySpark", "Hadoop", "MongoDB", "Git"
]

MAX_EXPERIENCE = 3
# ==========================================

def scrape_webpage(url):
    """Opens a headless browser, waits for the DOM, and pauses for JS text rendering."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # Disguise the headless browser as a standard Windows Chrome browser
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # wait_until="domcontentloaded" is much safer than "networkidle"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Hard pause for 5 seconds to guarantee React/Angular JavaScript text loads
            page.wait_for_timeout(5000) 
            
            # Extract all visible text from the body
            text = page.inner_text("body")
            browser.close()
            
            # Cap at 10,000 characters to save AI tokens
            return text[:10000] 
            
    except Exception as e:
        print(f"   ⚠️ Playwright failed to read page: {e}")
        return None

def evaluate_job(text, skills, max_exp):
    """Passes the text to Gemini with strict Knockout Rules and a Math Formula."""
    prompt = f"""
    You are an expert technical recruiter evaluating a job description. 
    Candidate's Max Experience: {max_exp} years
    Candidate's Skills: {', '.join(skills)}
    
    Read the following job description text carefully.

    KNOCKOUT RULES (If ANY of these are true, the score MUST be 0):
    1. Experience: The job explicitly requires MORE than {max_exp} years of minimum experience for the core role.
    2. Location: The job is explicitly located OUTSIDE of the United States (e.g., UK, India, Ukraine, Canada), even if it says "Remote".
    3. Sponsorship/Citizenship: The job explicitly states "no sponsorship available", "will not sponsor", "US Citizens only", "Green Card only", or requires an active US security clearance.
    
    If it passes ALL knockout rules, calculate a match score (0-100) using this EXACT formula:
    1. Identify the total number of distinct technical skills requested in the job description.
    2. Count how many of the Candidate's Skills match those requested skills.
    3. Score = (Matching Skills / Total Requested Skills) * 100.
    (Example: If the job asks for 3 skills and the candidate matches 2, the score is 66).

    Respond ONLY with a valid JSON object in this exact format:
    {{
        "years_required": (integer or null),
        "location_flagged": (true or false - true if outside US),
        "sponsorship_flagged": (true or false - true if they refuse sponsorship or require citizenship),
        "score": (integer 0-100),
        "reason": "Short explanation of the score, mentioning the exact math used (e.g., matched 2 out of 3 skills)."
    }}
    
    Job Description Text:
    {text}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ AI Evaluation Failed: {e}")
        return {"years_required": 99, "score": 0, "reason": "AI Error"}
    """Passes the text to Gemini with strict Knockout Rules."""
    prompt = f"""
    You are an expert technical recruiter evaluating a job description. 
    Candidate's Max Experience: {max_exp} years
    Candidate's Skills: {', '.join(skills)}
    
    Read the following job description text carefully.

    KNOCKOUT RULES (If ANY of these are true, the score MUST be 0):
    1. Experience: The job explicitly requires MORE than {max_exp} years of minimum experience for the core role.
    2. Location: The job is explicitly located OUTSIDE of the United States (e.g., UK, India, Ukraine, Canada), even if it says "Remote".
    3. Sponsorship/Citizenship: The job explicitly states "no sponsorship available", "will not sponsor", "US Citizens only", "Green Card only", or requires an active US security clearance.
    
    If it passes ALL knockout rules, calculate a match score (1-100) based on how many of the candidate's skills overlap.

    Respond ONLY with a valid JSON object in this exact format:
    {{
        "years_required": (integer or null),
        "location_flagged": (true or false - true if outside US),
        "sponsorship_flagged": (true or false - true if they refuse sponsorship or require citizenship),
        "score": (integer 0-100),
        "reason": "Short explanation of the score or the exact knockout reason."
    }}
    
    Job Description Text:
    {text}
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ AI Evaluation Failed: {e}")
        return {"years_required": 99, "score": 0, "reason": "AI Error"}

def run_scorer():
    print(f"🧠 Waking up the AI Brain. Evaluating {len(TEST_URLS)} jobs...\n")
    print("-" * 50)
    
    results = []
    
    for url in TEST_URLS:
        print(f"🕷️ Scraping (with Playwright): {url[:60]}...")
        job_text = scrape_webpage(url)
        
        if not job_text:
            print("❌ Could not read webpage.\n")
            continue
            
        print("🤖 AI is checking rules and scoring...")
        evaluation = evaluate_job(job_text, MY_SKILLS, MAX_EXPERIENCE)
        
        score = evaluation.get("score", 0)
        years = evaluation.get("years_required", "Unknown")
        loc_flag = evaluation.get("location_flagged", False)
        spon_flag = evaluation.get("sponsorship_flagged", False)
        reason = evaluation.get("reason", "")
        
        # Build a nice output string showing what got flagged
        flags = []
        if loc_flag: flags.append("📍 Bad Location")
        if spon_flag: flags.append("🛂 Visa/Clearance Issue")
        if str(years).isdigit() and int(years) > MAX_EXPERIENCE: flags.append("⏱️ Exp Too High")
        
        flag_str = f" | Flags: {', '.join(flags)}" if flags else " | Flags: Clean ✅"
        
        results.append({
            "url": url,
            "score": score,
            "years": years,
            "reason": reason,
            "flags": flag_str
        })
        
        print(f"✅ Score: {score}/100 | Exp Required: {years} yrs{flag_str}")
        print(f"📝 Reason: {reason}\n")
        print("-" * 50)

    results.sort(key=lambda x: x["score"], reverse=True)
    
    print("\n🏆 RESULTS RANKING:")
    for rank, res in enumerate(results, 1):
        if res['score'] > 0:
            print(f"{rank}. [Score: {res['score']}] - {res['url']}")
        else:
            print(f"   [REJECTED: 0] - {res['url']}")

if __name__ == "__main__":
    run_scorer()