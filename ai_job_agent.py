import os
import json
import time
import csv
import re
from serpapi import GoogleSearch
from google import genai
from google.genai import types
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import sys
import subprocess
import socket
import platform

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client      = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID    = "gemini-2.5-flash" 
MAX_SERPAPI_CALLS = 5  

PREFS = {
    "my_exp"           : 5,
    "needs_sponsorship": True,
    "my_skills": [
         "Python", "SQL", "R", "Java", "C++", "LLMs", "RAG", "NLP", "Clustering", "Segmentation",
         "Recommendation Systems", "Feature Engineering", "Machine Learning", "Deep Learning",
         "Scikit-Learn", "PyTorch", "TensorFlow", "BERT", "XGBoost", "LightGBM", "CatBoost", 
         "Autoencoders", "Hive", "AWS", "Databricks", "Spark", "PySpark", "Hadoop", "MongoDB", 
         "Git", "Tableau", "Power BI", "Matplotlib", "JavaScript", "TypeScript", "HTML", "CSS"
     ],
    "blocked_companies": [
        "jobot", "dice", "hirequest", "indeed.com", "echojobs.com", "upwork.com", "recruit.net", 
        "adzuna.com", "grabjobs.co", "simplyhired.com", "getgreatcareers.com", "jobs.valleycentral.com", 
        "jobs.stevenagefc.com", "jobs.ksnt.com", "us.trabajo.org/", "learn4good.com"
    ],
}

MY_PROFILE = {
    "first_name": os.getenv("PROFILE_FIRST_NAME", "Unknown"),
    "last_name": os.getenv("PROFILE_LAST_NAME", "Unknown"),
    "email": os.getenv("PROFILE_EMAIL"),
    "phone": os.getenv("PROFILE_PHONE"),
    "linkedin": os.getenv("PROFILE_LINKEDIN"),
    "github": os.getenv("PROFILE_GITHUB"),
    "portfolio": os.getenv("PROFILE_PORTFOLIO"),
    "address": os.getenv("PROFILE_ADDRESS"),
    "country": os.getenv("PROFILE_COUNTRY", "United States"),
    "resume_path": os.getenv("RESUME_PATH", "resume.pdf")
}

JOB_TITLES = [
    "Python Developer", "Machine Learning Engineer", "Data Scientist", "AI Engineer",
    "Data Engineer Python", "NLP Engineer", "Software Engineer Python", "ML Engineer",
    "Applied Scientist", "Analytics Engineer", "Deep Learning Engineer", "LLM Engineer",
    "Computer Vision Engineer", "Data Analyst Python", "AI Research Engineer"
]

NON_US_KEYWORDS = [
    "israel", "india", "united kingdom", "canada", "germany", "france", "australia", 
    "netherlands", "singapore", "ireland", "poland", "spain", "brazil", "mexico", 
    "philippines", "ukraine", "pakistan", "china", "japan", "south korea", "new zealand", 
    "sweden", "norway", "denmark", "tel aviv", "bangalore", "bengaluru", "mumbai", 
    "hyderabad", "chennai", "london", "toronto", "vancouver", "berlin", "amsterdam", 
    "sydney", "dublin", "paris", "zurich", "stockholm", "oslo", "copenhagen",
    "£", "€", "₹", "cad$", "aud$", "sgd", "outside the us", "non-us", "apac", "emea", "latam"
]

EXP_PATTERNS = [
    r'\b([3-9]|\d{2,})\+\s*years?\s*(of\s*)?(experience|exp)\b', 
    r'\b([4-9]|\d{2,})\s*years?\s*(of\s*)?(experience|exp)\b',
    r'\bminimum\s+([3-9]|\d{2,})\s*years?\b',
    r'\bat\s+least\s+([3-9]|\d{2,})\s*years?\b',
    r'\b([3-9]|\d{2,})\s*[-–]\s*\d+\s*years?\s*(of\s*)?(experience|exp)\b'
]
SENIORITY_TITLE_PATTERNS = [r'\bsenior\b', r'\bsr\b\.?', r'\bstaff\b', r'\bprincipal\b', r'\bdirector\b', r'\bvp\b', r'\blead\b', r'\bmanager\b']
CLEARANCE_PATTERNS = [r'\bts/sci\b', r'\btop secret\b', r'\bsecurity clearance\b', r'\bactive clearance\b', r'\bus citizen(ship)?\s+required\b']
NO_SPONSORSHIP_PATTERNS = [r'\bno\s+(visa\s+)?sponsorship\b', r'\bwill not\s+sponsor\b', r'\bcannot\s+sponsor\b', r'\bno\s+h.?1.?b\b', r'\bno\s+opt\b', r'\bno\s+cpt\b']
SPONSORSHIP_FRIENDLY_SIGNALS = [r'\be.?verify\b', r'\bopt\b', r'\bcpt\b', r'\bh.?1.?b\b', r'\bvisa sponsorship\s*(is\s*)?(available|provided|offered)\b', r'\buniversity\s+(hire|grad|graduate)\b']

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
def get_chrome_path():
    """Return path to Chrome executable."""
    system = platform.system()
    if system == "Darwin":  # macOS
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Windows":
        return "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    else:  # Linux
        return "google-chrome"

def get_default_chrome_profile():
    """Return path to your default Chrome profile."""
    home = os.path.expanduser("~")
    if platform.system() == "Darwin":
        return os.path.join(home, "Library/Application Support/Google/Chrome/Default")
    elif platform.system() == "Windows":
        return os.path.join(home, "AppData\\Local\\Google\\Chrome\\User Data\\Default")
    else:
        return os.path.join(home, ".config/google-chrome/Default")


def hard_filter(job: dict) -> tuple[bool, str]:
    title       = (job.get("title", "") or "").lower()
    company     = (job.get("company_name", "") or "").lower()
    location    = (job.get("location", "") or "").lower()
    description = (job.get("description", "") or "").lower()
    
    for h in job.get("job_highlights", []):
        for item in h.get("items", []):
            description += " " + item.lower()

    full_text = f"{title} {company} {location} {description}"

    for blocked in PREFS["blocked_companies"]:
        if blocked in company: return True, f"Blocked company: '{company}'"
    for kw in NON_US_KEYWORDS:
        if kw in location or kw in description: return True, f"Non-US keyword: '{kw}'"
    for p in SENIORITY_TITLE_PATTERNS:
        if re.search(p, title): return True, f"Senior title: '{title}'"
    for p in EXP_PATTERNS:
        if re.search(p, description): return True, f"Over-experience: matched '{p}'"
    for p in CLEARANCE_PATTERNS:
        if re.search(p, full_text): return True, f"Clearance required"
    if PREFS["needs_sponsorship"]:
        for p in NO_SPONSORSHIP_PATTERNS:
            if re.search(p, description): return True, f"No sponsorship"
    return False, ""

def get_full_text(job: dict) -> str:
    parts = [job.get("title", ""), job.get("company_name", ""), job.get("location", ""), job.get("description", "")]
    for h in job.get("job_highlights", []):
        for item in h.get("items", []):
            parts.append(item)
    return " ".join(p for p in parts if p)

def regex_skill_count(text: str) -> tuple[int, list[str]]:
    t = text.lower()
    matched = []
    aliases = {
        "Scikit-Learn": r"scikit[\s\-]?learn|sklearn", "PySpark": r"pyspark|py[\s\-]?spark",
        "Spark": r"\bspark\b", "Power BI": r"power[\s\-]?bi", "C++": r"c\+\+|c\s*plus\s*plus",
        "LightGBM": r"lightgbm|light\s*gbm", "XGBoost": r"xgboost|xg\s*boost",
        "TensorFlow": r"tensorflow|tensor\s*flow", "PyTorch": r"pytorch|py\s*torch",
        "JavaScript": r"javascript|\bjs\b", "TypeScript": r"typescript|\bts\b",
        "Machine Learning": r"machine\s*learning|\bml\b", "Deep Learning": r"deep\s*learning|\bdl\b",
        "NLP": r"\bnlp\b|natural\s*language\s*processing", "LLMs": r"\bllm\b|\bllms\b|large\s*language\s*model",
        "RAG": r"\brag\b|retrieval[\s\-]augmented"
    }
    for skill in PREFS["my_skills"]:
        pattern = aliases.get(skill, r'\b' + re.escape(skill.lower()) + r'\b')
        if re.search(pattern, t, re.IGNORECASE):
            matched.append(skill)
    return len(matched), matched

def get_apply_link(job: dict) -> str:
    options = job.get("apply_options", [])
    if options:
        for opt in options:
            link = opt.get("link", "")
            if any(good in link for good in ["greenhouse", "lever", "ashby", "workday", "jobvite", "icims"]): return link
        return options[0].get("link", "")
    return job.get("share_link", "")

def fetch_google_jobs(job_title: str) -> list[dict]:
    params = {
        "engine": "google_jobs", "q": job_title, "location": "United States",
        "hl": "en", "gl": "us", "chips": "date_posted:today", "num": 20, "api_key": SERPAPI_KEY,
    }
    try:
        results = GoogleSearch(params).get_dict()
        if "error" in results:
            print(f"      ⚠️  API error: {results['error']}")
            return []
        return results.get("jobs_results", [])
    except Exception as e: 
        print(f"      ⚠️  SerpAPI exception: {e}")
        return []

def find_jobs_blitz():
    all_jobs, seen_ids = [], set()
    api_calls_made = 0
    
    print(f"\n⚡ GOOGLE JOBS BLITZ (Safety Cap: {MAX_SERPAPI_CALLS} API Calls)...")
    
    for title in JOB_TITLES:
        if api_calls_made >= MAX_SERPAPI_CALLS:
            print(f"   🛑 BUDGET CAP REACHED: Stopping at {MAX_SERPAPI_CALLS} API calls.")
            break
            
        jobs = fetch_google_jobs(title)
        api_calls_made += 1
        
        for job in jobs:
            job_id = job.get("job_id") or (job.get("title", "") + job.get("company_name", ""))
            if job_id not in seen_ids:
                seen_ids.add(job_id)
                all_jobs.append(job)
                
        print(f"   📡 [{api_calls_made}/{MAX_SERPAPI_CALLS}] '{title}' -> Found {len(jobs)} jobs")
        time.sleep(0.5)
        
    return all_jobs

def visa_bonus(text: str) -> int:
    """Returns 0–15 bonus points for sponsorship-friendly signals."""
    t = text.lower()
    hits = sum(1 for p in SPONSORSHIP_FRIENDLY_SIGNALS if re.search(p, t))
    return min(hits * 5, 15)

def agent_1_analyst(full_text: str, pre_matched: list[str], job_title: str) -> dict:
    """
    AGENT 1: The Analyst. 
    Does the initial evaluation and scoring of the job description.
    """
    bonus = visa_bonus(full_text)
    
    prompt = f"""
    You are an AI Job Analyst. Evaluate this job for a candidate with {PREFS["my_exp"]} years of experience.
    Confirmed skills: {', '.join(pre_matched)}
    Needs Visa Sponsorship: {PREFS["needs_sponsorship"]}
    
    JOB TITLE: {job_title}
    
    STEP 1: KNOCKOUT CHECK
    If the job requires strictly >{PREFS["my_exp"]} years of experience, requires US Citizenship/Clearance, or explicitly denies visa sponsorship, mark `is_knockout` as true.
    
    STEP 2: SCORING
    If not a knockout, propose a score (1-100) based on:
    - Base Score: {len(pre_matched)} skills already confirmed by regex.
    - Scoring Table: 2 skills=50, 3 skills=68, 4 skills=80, 5 skills=88, 6+ skills=95+.
    - Add +5 bonus if the role mentions "Junior", "Associate", "Entry Level", or "New Grad".
    - Add +{bonus} visa-friendly bonus points (already detected).
    - Cap the maximum final score at 100.
    
    JOB DESCRIPTION:
    {full_text[:4000]}
    """

    schema = {
        "type": "OBJECT",
        "properties": {
            "analyst_reasoning": {"type": "STRING", "description": "Step-by-step logic."},
            "is_knockout": {"type": "BOOLEAN"},
            "proposed_score": {"type": "INTEGER"},
            "years_required": {"type": "INTEGER", "nullable": True}
        },
        "required": ["analyst_reasoning", "is_knockout", "proposed_score"]
    }

    try:
        resp = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2
            )
        )
        
        raw_text = resp.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"      ⚠️ API Error for {job_title}: {e}")
        return {"is_knockout": True, "proposed_score": 0, "analyst_reasoning": f"Agent Error: {e}"}

def agent_2_supervisor(full_text: str, agent_1_output: dict, job_title: str) -> dict:
    """
    AGENT 2: The Judge.
    Audits Agent 1's work to catch hallucinations, missed red flags, or bad math.
    """
    prompt = f"""
    You are the Supervisor QA Agent. You are auditing "Agent 1", who just evaluated a job posting.
    
    CANDIDATE CONSTRAINTS: Max {PREFS["my_exp"]} years experience, needs Visa Sponsorship.
    JOB TITLE: {job_title}
    
    AGENT 1'S WORK TO AUDIT:
    {json.dumps(agent_1_output, indent=2)}
    
    YOUR JOB:
    1. Read the job description carefully.
    2. Did Agent 1 miss a major red flag? (e.g., The job requires US Citizenship, or >{PREFS["my_exp"]} years exp, but Agent 1 missed it).
    3. If Agent 1 marked `is_knockout` as true, the `final_approved_score` MUST be 0.
    4. Override Agent 1 if they made a mistake, or approve their score if they are correct.
    
    JOB DESCRIPTION:
    {full_text[:4000]}
    """

    schema = {
        "type": "OBJECT",
        "properties": {
            "supervisor_audit_notes": {"type": "STRING", "description": "Critique of Agent 1's work."},
            "agent_1_was_correct": {"type": "BOOLEAN"},
            "final_approved_score": {"type": "INTEGER", "description": "Must be 0 if job is a knockout."},
            "final_verdict_reason": {"type": "STRING", "description": "One sentence explaining the final decision for the user."}
        },
        "required": ["supervisor_audit_notes", "agent_1_was_correct", "final_approved_score", "final_verdict_reason"]
    }

    try:
        resp = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.0
            )
        )
        
        raw_text = resp.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"      ⚠️ API Error for {job_title}: {e}")
        return {"is_knockout": True, "proposed_score": 0, "analyst_reasoning": f"Agent Error: {e}"}
def run_scraper_agent():
    raw_jobs = find_jobs_blitz()
    if not raw_jobs: 
        print("❌ No jobs found today.")
        return []
    
    print(f"\n🧠 Analyzing {len(raw_jobs)} collected roles...")
    print("━"*60)
    
    all_results = []
    skills_counter = {} 
    
    for job in raw_jobs:
        title = job.get("title", "Unknown")
        company = job.get("company_name", "Unknown")
        
        # --- Catch & Save Hard Filter Rejections ---
        rejected, reason = hard_filter(job)
        if rejected:
            print(f" ❌ Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: {reason}")
            all_results.append({
                "score": 0,
                "job_title": title,
                "company": company,
                "apply_link": get_apply_link(job),
                "reason": f"Hard Filter: {reason}"
            })
            continue
        
        full_text = get_full_text(job)
        skill_n, skill_list = regex_skill_count(full_text)
        
        # --- Catch & Save Low Skill Rejections ---
        if skill_n < 3:
            print(f" ⚠️  Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: Only {skill_n} relevant skills")
            all_results.append({
                "score": 0,
                "job_title": title,
                "company": company,
                "apply_link": get_apply_link(job),
                "reason": f"Low Skills: Found only {skill_n} relevant skills"
            })
            continue 
        
        # 1. Analyst evaluates the job and generates the first draft
        agent_1_data = agent_1_analyst(full_text, skill_list, title)
        time.sleep(1) 
        
        # 2. Supervisor audits the draft and issues the final verdict
        agent_2_data = agent_2_supervisor(full_text, agent_1_data, title)
        time.sleep(1) 
        
        score = agent_2_data.get("final_approved_score", 0)
        final_reason = agent_2_data.get("final_verdict_reason", "No reason provided.")
        
        if not agent_2_data.get("agent_1_was_correct", True):
            print(f" 🚨 Overruled: {company[:15]:<15} | Supervisor caught an error! Score adjusted to {score}.")
        
        # --- Save ALL AI evaluations (Pass or Fail) ---
        all_results.append({
            "score": score,
            "job_title": title,
            "company": company,
            "apply_link": get_apply_link(job),
            "reason": final_reason
        })
        
        if score >= 70:
            print(f" ✅ MATCH!  : {company[:15]:<15} | {title[:20]:<20} -> Score: {score}/100")
            for s in skill_list:
                skills_counter[s] = skills_counter.get(s, 0) + 1
        else:
            print(f" 📉 Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: Low AI match score ({score})")

    # Sort everything: highest scores at the top, 0 scores at the bottom
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    with open("usa_jobs_ranked_full.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["score", "job_title", "company", "apply_link", "reason"])
        writer.writeheader()
        writer.writerows(all_results)
    
    print("━"*60)
    print(f"✅ Saved {len(all_results)} total processed jobs to CSV.")
    
    if skills_counter:
        top_skills = sorted(skills_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        skill_names = [s[0] for s in top_skills]
        print(f"🧠 Insight: Most matching roles today require {', '.join(skill_names)}.")
        
    # Return only the passing matches so the summary in the terminal looks clean
    return [job for job in all_results if job["score"] >= 70]

def human_in_the_loop_apply():
    jobs = []
    try:
        with open("usa_jobs_ranked_full.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # --- NEW CODE: Only grab jobs with a score of 70 or higher ---
            jobs = [row for row in reader if int(row["score"]) >= 70]
            
    except FileNotFoundError:
        print("\n ❌ Error: 'usa_jobs_ranked_full.csv' not found. Please run the [discover] phase first!\n")
        return

    if not jobs:
        print("\n ❌ No passing jobs found in the CSV to apply to.\n")
        return

    print("\n" + "━"*60)
    print(f" 🚀 BOOTING APPLICATION ASSISTANT ({len(jobs)} matches to process)")
    print("━"*60 + "\n")

    with sync_playwright() as p:
        print(" 🌐 Launching persistent browser...")
        
        # --- NEW CODE: Use a persistent profile folder to save logins ---
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile_data")
        
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            # Playwright's persistent context sometimes opens a blank tab by default.
            # We will use that existing tab instead of opening a new one.
        )
        
        # Get the default page created by the persistent context
        page = context.pages[0] if context.pages else context.new_page()

        for i, row in enumerate(jobs):
            print(f"\n[{i+1}/{len(jobs)}] APPLYING TO: {row['job_title'][:40]} @ {row['company'][:20]}")
            
            try:
                if page.is_closed():
                    print("   ⚠️ Browser tab was closed! Reopening a new tab...")
                    page = context.new_page()
            except Exception:
                print("   ⚠️ Browser was completely closed! Restarting the browser engine...")
                # Re-launch persistent context if they closed the whole window
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False
                )
                page = context.pages[0] if context.pages else context.new_page()
            
            try:
                print("   ⏳ Loading application page...")
                page.goto(row['apply_link'], timeout=15000, wait_until="domcontentloaded")
                
                # --- TIP: Add a tiny pause here on the very first run ---
                # If you need to log in to LinkedIn/Indeed, you can do it manually now.
                # After you log in once, 'chrome_profile_data' saves it forever.

            except Exception as e:
                if "Timeout" in str(e):
                    print("   🐢 This portal is loading slowly. Letting it finish in the background...")
                else:
                    print(f"   ❌ Error loading page: {e}")
                    print("   ➡️ Skipping to the next job...\n")
                    continue

            print("   ⌨️  Attempting to inject profile data...")                            
            
            # Safe JSON serialization for JavaScript injection
            safe_first = json.dumps(MY_PROFILE.get("first_name", ""))
            safe_last = json.dumps(MY_PROFILE.get("last_name", ""))
            safe_email = json.dumps(MY_PROFILE.get("email", ""))
            safe_phone = json.dumps(MY_PROFILE.get("phone", ""))
            safe_linkedin = json.dumps(MY_PROFILE.get("linkedin", ""))
            safe_github = json.dumps(MY_PROFILE.get("github", ""))

            js_injection = f"""
            () => {{
                const setVal = (selectors, value) => {{
                    if(!value) return;
                    document.querySelectorAll(selectors).forEach(el => {{
                        el.value = value;
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }});
                }};
                
                setVal('input[name*="first" i], input[id*="first" i]', {safe_first});
                setVal('input[name*="last" i], input[id*="last" i]', {safe_last});
                setVal('input[type="email" i], input[name*="email" i]', {safe_email});
                setVal('input[type="tel" i], input[name*="phone" i]', {safe_phone});
                setVal('input[name*="linkedin" i], input[name*="url" i]', {safe_linkedin});
                setVal('input[name*="github" i]', {safe_github});
            }}
            """
            try:
                page.evaluate(js_injection)
                print("   ✅ Auto-fill script executed.")
            except Exception as e:
                pass 

            print("   👤 [HUMAN REQUIRED] Please review the form, answer custom questions, and hit Submit.")
            input("   ➡️  Press [ENTER] in this terminal when you are ready for the NEXT job... ")
            
        try:
            context.close()
        except Exception:
            pass 

        print("\n" + "━"*60)
        print(" 🏁 ALL DONE! You've reached the end of your list.")
        print("━"*60)

def manual_apply_with_real_chrome(jobs):
    """
    Uses Playwright's persistent context (saves login data in chrome_profile_data/).
    You log in once on the first run, then it remembers.
    No manual Chrome start required.
    """
    if not jobs:
        print("❌ No jobs to apply to.")
        return

    print("\n" + "━"*60)
    print(f" 🚀 APPLYING TO {len(jobs)} JOBS (persistent browser profile)")
    print("   Auto‑fill will attempt to fill fields as they appear.")
    print("   You remain in full control to review and submit.")
    print("━"*60 + "\n")

    user_data_dir = os.path.join(os.getcwd(), "chrome_profile_data")
    
    with sync_playwright() as p:
        print(" 🌐 Launching persistent browser...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Get or create a page
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(20000)

        for i, row in enumerate(jobs):
            print(f"\n[{i+1}/{len(jobs)}] APPLYING TO: {row['job_title'][:40]} @ {row['company'][:20]}")
            link = row.get('apply_link', '')
            if not link:
                print("   ⚠️ No apply link – skipping")
                continue

            print("   ⏳ Loading application page...")
            try:
                response = page.goto(link, wait_until="domcontentloaded", timeout=15000)
                if response and response.status >= 400:
                    print(f"   ❌ HTTP error {response.status} – skipping job.")
                    continue
            except Exception as e:
                print(f"   ❌ Error loading page: {e}")
                continue

            # Wait for form fields
            try:
                page.wait_for_selector('input[name*="first" i], input[type="email" i]', timeout=10000)
                print("   ✅ Page ready – form fields detected.")
            except Exception:
                print("   ⚠️ No form fields found – skipping (maybe login required).")
                # If this is the first job, you might need to log in manually now
                if i == 0:
                    print("\n🔐 If you see a login page, please log in manually now.")
                    input("   ➡️ Press ENTER after you have logged in and the form is ready...")
                    page.goto(link, wait_until="domcontentloaded")
                    time.sleep(2)
                else:
                    continue

            # Auto‑fill (same as before)
            safe_first = json.dumps(MY_PROFILE.get("first_name", ""))
            safe_last = json.dumps(MY_PROFILE.get("last_name", ""))
            safe_email = json.dumps(MY_PROFILE.get("email", ""))
            safe_phone = json.dumps(MY_PROFILE.get("phone", ""))
            safe_linkedin = json.dumps(MY_PROFILE.get("linkedin", ""))

            js = f"""
            () => {{
                const setVal = (sel, value) => {{
                    if(!value) return;
                    const fields = document.querySelectorAll(sel);
                    fields.forEach(el => {{
                        el.value = value;
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }});
                    return fields.length;
                }};
                let filled = 0;
                filled += setVal('input[name*="first" i], input[id*="first" i], input[placeholder*="first" i]', {safe_first});
                filled += setVal('input[name*="last" i], input[id*="last" i], input[placeholder*="last" i]', {safe_last});
                filled += setVal('input[type="email" i], input[name*="email" i]', {safe_email});
                filled += setVal('input[type="tel" i], input[name*="phone" i]', {safe_phone});
                filled += setVal('input[name*="linkedin" i], input[name*="url" i]', {safe_linkedin});
                return filled;
            }}
            """
            try:
                filled_count = page.evaluate(js)
                if filled_count > 0:
                    print(f"   ✅ Auto‑fill executed ({filled_count} fields).")
                else:
                    print("   ⚠️ Auto‑fill found no matching fields – you'll need to fill manually.")
            except Exception as e:
                print(f"   ⚠️ Auto‑fill evaluation failed: {e}")

            # Upload resume (to all file inputs)
            resume_path = MY_PROFILE.get("resume_path", "")
            if resume_path and os.path.exists(resume_path):
                try:
                    file_inputs = page.query_selector_all('input[type="file"]')
                    if file_inputs:
                        for inp in file_inputs:
                            inp.set_input_files(resume_path)
                        print(f"   📎 Resume uploaded to {len(file_inputs)} file field(s).")
                    else:
                        print("   ⚠️ No file upload field found – skip resume upload.")
                except Exception as e:
                    print(f"   ⚠️ Resume upload failed: {e}")
            else:
                print(f"   ⚠️ Resume not found at: {resume_path} – please upload manually.")

            # Wait for user to complete
            print("\n" + "─"*50)
            print("✅ Auto‑fill completed (where possible).")
            print("   Please:")
            print("   • Review and correct any missing/wrong fields")
            print("   • Complete multi‑page forms (Next buttons)")
            print("   • Upload additional documents if required")
            print("   • Click the FINAL SUBMIT button")
            print("─"*50)
            input("➡️ Press ENTER after you have FULLY SUBMITTED this application → ")

        context.close()
        print("\n" + "━"*60)
        print(" 🏁 All jobs processed. Good luck!")
        print("━"*60)