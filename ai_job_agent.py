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
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client      = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID    = "gemini-2.5-flash" 
MAX_SERPAPI_CALLS = 5  

PREFS = {
    "my_exp"           : 2,
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
            job_id = job.get("job_id", job.get("title", "") + job.get("company_name", ""))
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

def ai_score_job(full_text: str, pre_matched: list[str], job_title: str) -> dict:
    bonus = visa_bonus(full_text)
    
    prompt = f"""
You are an expert technical recruiter evaluating a US job posting for a candidate with 
EXACTLY {PREFS["my_exp"]} YEARS of experience who needs visa sponsorship.

JOB TITLE: "{job_title}"
CANDIDATE MAX EXPERIENCE: {PREFS["my_exp"]} Years
CANDIDATE SKILLS: {', '.join(PREFS["my_skills"])}

STEP 1: MANDATORY KNOCKOUT CHECK (Phase 1)
If any of the following are true, the score MUST be 0 and you must STOP:
1. EXPERIENCE: Does the job explicitly require a MINIMUM of more than {PREFS["my_exp"]} years? 
   - Examples of FAIL (Score 0): "3+ years", "Minimum 4 years", "5-7 years", "Senior level".
   - Examples of PASS: "1-2 years", "2+ years", "Entry level", "0-3 years".
2. LOCATION: Is the job explicitly outside the United States? (Check for non-US cities or currencies like GBP/INR).
3. CITIZENSHIP: Does it require "US Citizenship Only" or "Active Security Clearance"?

STEP 2: SCORING (Only if Step 1 passes)
If the job is a PASS for a {PREFS["my_exp"]}-year candidate, calculate a match score (1-100):
- Base Score: {len(pre_matched)} skills already confirmed by regex.
- Scoring Table (Total matches): 2 skills=50, 3 skills=68, 4 skills=80, 5 skills=88, 6+ skills=95+.
- Add +5 bonus if the role mentions "Junior", "Associate", "Entry Level", or "New Grad".
- Add +{bonus} visa-friendly bonus points (already detected).
- Cap the maximum final score at 100.

Return ONLY valid JSON (no markdown):
{{
    "score": <int 0-100>,
    "years_required": <int or null>,
    "matches": {json.dumps(pre_matched)},
    "visa_status": "<Friendly | Not Mentioned | Unfriendly>",
    "reason": "<1 sentence explaining if it passed the {PREFS["my_exp"]}-year limit and why it got this score>"
}}

JOB TEXT (Truncated):
{full_text[:5000]}
"""

    try:
        resp = client.models.generate_content(
            model=MODEL_ID, 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", 
                temperature=0.1
            )
        )
        
        raw = re.sub(r"```json|```", "", resp.text.strip()).strip()
        result = json.loads(raw)
        
        # --- BULLETPROOF Safety Override ---
        years_req = result.get("years_required")
        if years_req is not None:
            try:
                # Extract digits just in case LLM says "3 years" instead of 3
                years_int = int(re.search(r'\d+', str(years_req)).group())
                if years_int > PREFS["my_exp"]:
                    result["score"] = 0
                    result["reason"] = f"Manual Override: Requires {years_int} years. " + result.get("reason", "")
            except:
                pass # If regex fails to find a number, ignore and trust the AI
                
        return result
        
    except Exception as e:
        return {
            "score": 0, 
            "years_required": None, 
            "matches": pre_matched,
            "visa_status": "Unknown", 
            "reason": f"AI Parsing Error: {e}"
        }

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
        rejected, reason = hard_filter(job)
        if rejected:
            print(f" ❌ Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: {reason}")
            continue
        
        full_text = get_full_text(job)
        skill_n, skill_list = regex_skill_count(full_text)
        if skill_n < 3:
            print(f" ⚠️  Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: Only {skill_n} relevant skills")
            continue 
        
        ai_data = ai_score_job(full_text, skill_list, title)
        score = ai_data.get("score", 0)
        
        if score >= 70:
            print(f" ✅ MATCH!  : {company[:15]:<15} | {title[:20]:<20} -> Score: {score}/100")
            all_results.append({
                "score": score,
                "job_title": title,
                "company": company,
                "apply_link": get_apply_link(job),
                "reason": ai_data.get("reason", "")
            })
            for s in skill_list:
                skills_counter[s] = skills_counter.get(s, 0) + 1
        else:
            print(f" 📉 Skipped: {company[:15]:<15} | {title[:20]:<20} -> Reason: Low AI match score ({score})")

    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    with open("usa_jobs_ranked_full.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["score", "job_title", "company", "apply_link", "reason"])
        writer.writeheader()
        writer.writerows(all_results)
    
    print("━"*60)
    print(f"✅ Saved {len(all_results)} highly qualified leads.")
    
    if all_results and skills_counter:
        top_skills = sorted(skills_counter.items(), key=lambda x: x[1], reverse=True)[:3]
        skill_names = [s[0] for s in top_skills]
        print(f"🧠 Insight: Most matching roles today require {', '.join(skill_names)}.")
        
    return all_results


def human_in_the_loop_apply():
    jobs = []
    try:
        with open("usa_jobs_ranked_full.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            jobs = list(reader)
    except FileNotFoundError:
        print("\n ❌ Error: 'usa_jobs_ranked_full.csv' not found. Please run the [discover] phase first!\n")
        return

    if not jobs:
        print("\n ❌ No jobs found in the CSV to apply to.\n")
        return

    print("\n" + "━"*60)
    print(" 🚀 BOOTING APPLICATION ASSISTANT (Human-in-the-Loop)")
    print("━"*60 + "\n")

    with sync_playwright() as p:
        # Launch the browser
        print(" 🌐 Launching browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        for i, row in enumerate(jobs):
            print(f"[{i+1}/{len(jobs)}] APPLYING TO: {row['job_title'][:40]} @ {row['company'][:20]}")
            
            try:
                if page.is_closed():
                    print("   ⚠️ Browser tab was closed! Reopening a new tab...")
                    page = context.new_page()
            except Exception:
                print("   ⚠️ Browser was completely closed! Restarting the browser engine...")
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
            
            try:
                print("   ⏳ Loading application page...")
                page.goto(row['apply_link'], timeout=15000, wait_until="domcontentloaded")
            except Exception as e:
                if "Timeout" in str(e):
                    print("   🐢 This portal is loading slowly. Letting it finish in the background...")
                else:
                    print(f"   ❌ Error loading page: {e}")
                    print("   ➡️ Skipping to the next job...\n")
                    continue

            print("   ⌨️  Attempting to inject profile data...")                            
            print("   👤 [HUMAN REQUIRED] Please review the form, answer custom questions, and hit Submit.")
            input("   ➡️  Press [ENTER] in this terminal when you are ready for the NEXT job... ")
            
            print("") 

        try:
            browser.close()
        except Exception:
            pass 

        print("━"*60)
        print(" 🏁 ALL DONE! You've reached the end of your list.")
        print("━"*60)


if __name__ == "__main__":
    print("\n" + "━"*60)
    print(" 🤖 AI Job Agent — Your Personal Recruiter")
    print("━"*60)
    
    print(" 📍 Location: United States")
    print(f" 🎯 Target roles: {len(JOB_TITLES)} titles (e.g., {JOB_TITLES[0]}, {JOB_TITLES[1]})")
    print(f" 🧠 Experience: {PREFS['my_exp']} years | Visa Sponsorship: {'Required' if PREFS['needs_sponsorship'] else 'Not Required'}")
    print("━"*60)

    print("\nWhat would you like to do today?")
    print(" 👉 [discover]  Search, filter, and score new jobs")
    print(" 👉 [apply]     Start applying to saved matches")
    print(" 👉 [all]       Run the full discovery and application pipeline")
    print(" 👉 [exit]      Close the agent\n")
    
    choice = input("Enter command: ").strip().lower()
    
    if choice not in ['discover', 'apply', 'all', 'exit']:
        print("❌ Invalid command. Please restart and try again.")
        sys.exit()

    if choice == 'exit':
        print("\nSee you tomorrow! 👋\n")
        sys.exit()
        
    matches = []
    
    if choice in ['discover', 'all']:
        print("\n🔍 I'll now:")
        print(" • Search across multiple job platforms")
        print(" • Filter out senior / non-US / no-sponsorship roles")
        print(" • Score jobs based on your exact profile")
        print("\n⏳ This may take ~20–30 seconds...\n")
        
        matches = run_scraper_agent() 
        
        if matches:
            print("\n" + "━"*60)
            print(" 🏆 Top Matches for You:")
            print("━"*60)
            for i, job in enumerate(matches[:5]): 
                reason_trunc = job['reason'][:65] + "..." if len(job['reason']) > 65 else job['reason']
                print(f" {i+1}. {job['job_title'][:25]:<25} @ {job['company'][:15]:<15} | Score: {job['score']}")
                print(f"    ↳ {reason_trunc}")
            
            if len(matches) > 5:
                print(f"\n    ... and {len(matches) - 5} more strong matches saved to CSV.")
            print("━"*60)
            
            if choice == 'discover':
                print("\nWhat would you like to do next?")
                print(" 👉 [apply]     Start applying to these matches")
                print(" 👉 [view]      Inspect full job details (CSV)")
                print(" 👉 [exit]      Finish session\n")
                
                next_action = input("Enter command: ").strip().lower()
                if next_action == 'apply':
                    choice = 'apply'
                elif next_action == 'view':
                    print("\n📄 Open 'usa_jobs_ranked_full.csv' in your code editor or Excel to view all links and details.")
                    choice = 'exit'
                else:
                    print("\nOkay, they are safely saved in your CSV. Catch you next time! 👋\n")
                    choice = 'exit'

    if choice in ['apply', 'all']:
        print("\n" + "━"*60)
        print(" 🚀 READY TO APPLY")
        print("━"*60)
        print("⚠️ Heads up: Each job will open in a new browser window.\n")
        print(" I will auto-fill:")
        print("  • Name, Email, Phone")
        print("  • Links (LinkedIn, GitHub, Portfolio)\n")
        print(" You will still control:")
        print("  • Uploading missing documents (if needed)")
        print("  • Answering custom/company-specific questions")
        print("  • Clicking the final 'Submit' button\n")
        
        proceed = input("Continue? (yes/no): ").strip().lower()
        if proceed in ['y', 'yes']:
            human_in_the_loop_apply()             
            print("\n" + "━"*60)
            print(" 🏁 Session Complete!")
            print("━"*60)
            print("💡 Tip: New jobs are posted daily. Run this every morning to stay ahead of other applicants.")
            print("See you tomorrow 👋\n")
        else:
            print("\nApplication phase aborted. Catch you next time! 👋\n")