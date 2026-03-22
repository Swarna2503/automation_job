import os
import json
import time
import csv
import re
from serpapi import GoogleSearch
from google import genai
from google.genai import types
from dotenv import load_dotenv


load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client      = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID    = "gemini-2.5-flash"

PREFS = {
    "my_exp"           : 2,
    "needs_sponsorship": True,

    "my_skills": [
        # Programming Languages
        "Python", "SQL", "R", "Java", "C++",
        # Machine Learning & AI
        "LLMs", "RAG", "NLP", "Clustering", "Segmentation",
        "Recommendation Systems", "Feature Engineering",
        "Machine Learning", "Deep Learning",
        # Libraries & Models
        "Scikit-Learn", "PyTorch", "TensorFlow", "BERT",
        "XGBoost", "LightGBM", "CatBoost", "Autoencoders",
        # Data Engineering & Platforms
        "Hive", "AWS", "Databricks", "Spark", "PySpark",
        "Hadoop", "MongoDB", "Git",
        # Analytics & Visualization
        "Tableau", "Power BI", "Matplotlib",
        # Web Technologies
        "JavaScript", "TypeScript", "HTML", "CSS",
    ],

    "blocked_companies": [
        # Add company names here to skip them (e.g. "Dice", "Jobot")
        "jobot", "dice", "hirequest", "indeed.com", "echojobs.com", "upwork.com", "recruit.net", "adzuna.com", "grabjobs.co",
        "simplyhired.com", "getgreatcareers.com", "jobs.valleycentral.com", "jobs.stevenagefc.com", "jobs.ksnt.com", "us.trabajo.org/",
        "jobs.stevenagefc.com", 
    ],
}

JOB_TITLES = [
    "Python Developer",
    "Machine Learning Engineer",
    "Data Scientist",
    "AI Engineer",
    "Data Engineer Python",
    "NLP Engineer",
    "Software Engineer Python",
    "ML Engineer",
    "Applied Scientist",
    "Analytics Engineer",
    "Deep Learning Engineer",
    "LLM Engineer",
    "Computer Vision Engineer",
    "Data Analyst Python",
    "AI Research Engineer",
]

NON_US_KEYWORDS = [
    "israel", "india", "united kingdom", "canada", "germany", "france",
    "australia", "netherlands", "singapore", "ireland", "poland", "spain",
    "brazil", "mexico", "philippines", "ukraine", "pakistan", "china",
    "japan", "south korea", "new zealand", "sweden", "norway", "denmark",
    "tel aviv", "bangalore", "bengaluru", "mumbai", "hyderabad", "chennai",
    "london", "toronto", "vancouver", "berlin", "amsterdam", "sydney",
    "dublin", "paris", "zurich", "stockholm", "oslo", "copenhagen",
    "£", "€", "₹", "cad$", "aud$", "sgd",
    "outside the us", "non-us", "apac", "emea", "latam",
    "work from anywhere outside", "based outside the united states",
]

EXP_PATTERNS = [
    r'\b([3-9]|\d{2,})\+\s*years?\s*(of\s*)?(experience|exp)\b',
    r'\b([4-9]|\d{2,})\s*years?\s*(of\s*)?(experience|exp)\b',
    r'\bminimum\s+([3-9]|\d{2,})\s*years?\b',
    r'\bat\s+least\s+([3-9]|\d{2,})\s*years?\b',
    r'\b([3-9]|\d{2,})\s*[-–]\s*\d+\s*years?\s*(of\s*)?(experience|exp)\b',
]

SENIORITY_TITLE_PATTERNS = [
    r'\bsenior\b', r'\bsr\b\.?', r'\bstaff\b', r'\bprincipal\b',
    r'\bdirector\b', r'\bvp\b', r'\bvice\s+president\b',
    r'\bmanager\b',
    r'\blead\s+(engineer|developer|scientist|analyst|architect)\b',
]

CLEARANCE_PATTERNS = [
    r'\bts/sci\b', r'\btop secret\b', r'\bsecurity clearance\b',
    r'\bactive clearance\b', r'\bus citizen(ship)?\s+required\b',
    r'\bmust be a us citizen\b',
]

NO_SPONSORSHIP_PATTERNS = [
    r'\bno\s+(visa\s+)?sponsorship\b',
    r'\bwill not\s+sponsor\b',
    r'\bcannot\s+sponsor\b',
    r'\bdoes not\s+sponsor\b',
    r'\bno\s+h.?1.?b\b',
    r'\bno\s+f.?1\b',
    r'\bno\s+opt\b',
    r'\bno\s+cpt\b',
    r'\bsponsorship\s+not\s+(available|provided|offered)\b',
    r'\bauthorized to work\b.{0,60}\bwithout\b.{0,30}\bsponsorship\b',
    r'\beligible to work\b.{0,60}\bwithout\b.{0,30}\bvisa\b',
    r'\bmust be (legally\s+)?authorized\b.{0,40}\bwithout\b',
]

SPONSORSHIP_FRIENDLY_SIGNALS = [
    r'\be.?verify\b', r'\bopt\b', r'\bcpt\b', r'\bh.?1.?b\b',
    r'\bvisa sponsorship\s*(is\s*)?(available|provided|offered|considered|welcome)\b',
    r'\bwill\s+sponsor\b', r'\bopen to\s+sponsorship\b',
    r'\buniversity\s+(hire|grad|graduate|recruit)\b',
    r'\bnew\s*grad(uate)?\b', r'\brelocation\s+(assistance|package)\b',
]



def hard_filter(job: dict) -> tuple[bool, str]:
    """
    Checks structured google_jobs fields.
    Uses job title separately from description for seniority check.
    Returns (should_reject, reason).
    """
    title       = (job.get("title", "") or "").lower()
    company     = (job.get("company_name", "") or "").lower()
    location    = (job.get("location", "") or "").lower()
    description = (job.get("description", "") or "").lower()

    # Combine highlights into description for richer text
    highlights = job.get("job_highlights", [])
    for h in highlights:
        for item in h.get("items", []):
            description += " " + item.lower()

    full_text = f"{title} {company} {location} {description}"

    # 1. Blocked companies
    for blocked in PREFS["blocked_companies"]:
        if blocked in company:
            return True, f"Blocked company: '{company}'"

    # 2. Non-US location
    for kw in NON_US_KEYWORDS:
        if kw in location or kw in description:
            return True, f"Non-US keyword: '{kw}'"

    # 3. Seniority — TITLE ONLY (prevents false rejections)
    for p in SENIORITY_TITLE_PATTERNS:
        if re.search(p, title):
            return True, f"Senior title: '{title}'"

    # 4. Experience years — full description
    for p in EXP_PATTERNS:
        if re.search(p, description):
            return True, f"Over-experience: matched '{p}'"

    # 5. Security clearance
    for p in CLEARANCE_PATTERNS:
        if re.search(p, full_text):
            return True, f"Clearance required"

    # 6. Sponsorship rejection
    if PREFS["needs_sponsorship"]:
        for p in NO_SPONSORSHIP_PATTERNS:
            if re.search(p, description):
                return True, f"No sponsorship"

    return False, ""


def get_full_text(job: dict) -> str:
    """Merge all text fields from a google_jobs result into one string."""
    parts = [
        job.get("title", ""),
        job.get("company_name", ""),
        job.get("location", ""),
        job.get("description", ""),
    ]
    for h in job.get("job_highlights", []):
        for item in h.get("items", []):
            parts.append(item)
    return " ".join(p for p in parts if p)


def regex_skill_count(text: str) -> tuple[int, list[str]]:
    """Fast free skill counter. Returns (count, matched_skills_list)."""
    t       = text.lower()
    matched = []
    aliases = {
        "Scikit-Learn"        : r"scikit[\s\-]?learn|sklearn",
        "PySpark"             : r"pyspark|py[\s\-]?spark",
        "Spark"               : r"\bspark\b",
        "Power BI"            : r"power[\s\-]?bi",
        "C++"                 : r"c\+\+|c\s*plus\s*plus",
        "LightGBM"            : r"lightgbm|light\s*gbm",
        "XGBoost"             : r"xgboost|xg\s*boost",
        "TensorFlow"          : r"tensorflow|tensor\s*flow",
        "PyTorch"             : r"pytorch|py\s*torch",
        "JavaScript"          : r"javascript|\bjs\b",
        "TypeScript"          : r"typescript|\bts\b",
        "Machine Learning"    : r"machine\s*learning|\bml\b",
        "Deep Learning"       : r"deep\s*learning|\bdl\b",
        "Recommendation Systems": r"recommendation\s*(system|engine|model)s?",
        "Feature Engineering" : r"feature\s*engineering",
        "NLP"                 : r"\bnlp\b|natural\s*language\s*processing",
        "LLMs"                : r"\bllm\b|\bllms\b|large\s*language\s*model",
        "RAG"                 : r"\brag\b|retrieval[\s\-]augmented",
    }
    for skill in PREFS["my_skills"]:
        if skill in aliases:
            pattern = aliases[skill]
        else:
            pattern = r'\b' + re.escape(skill.lower()) + r'\b'
        if re.search(pattern, t, re.IGNORECASE):
            matched.append(skill)
    return len(matched), matched


def visa_bonus(text: str) -> int:
    """Returns 0–15 bonus points for sponsorship-friendly signals."""
    t    = text.lower()
    hits = sum(1 for p in SPONSORSHIP_FRIENDLY_SIGNALS if re.search(p, t))
    return min(hits * 5, 15)


def get_apply_link(job: dict) -> str:
    """Extract the best direct apply link from a google_jobs result."""
    options = job.get("apply_options", [])
    if options:
        # Prefer direct company links over aggregators
        for opt in options:
            link = opt.get("link", "")
            if any(good in link for good in ["greenhouse", "lever", "ashby",
                                             "workday", "jobvite", "icims"]):
                return link
        return options[0].get("link", "")
    return job.get("share_link", "")


# ==========================================
# 🧠 AI SCORER
# ==========================================

def ai_score_job(full_text: str, pre_matched: list[str], job_title: str) -> dict:
    """
    AI scoring with strict Phase 1 Knockout for Experience > 2 years.
    """
    bonus = visa_bonus(full_text)

    # We define the candidate's ceiling as 2 years. 
    # The prompt forces a 0 score if the job asks for 3, 4, 5+ etc.
    prompt = f"""
You are an expert technical recruiter evaluating a US job posting for a candidate with 
EXACTLY 2 YEARS of experience who needs visa sponsorship.

JOB TITLE: "{job_title}"
CANDIDATE MAX EXPERIENCE: 2 Years
CANDIDATE SKILLS: {', '.join(PREFS["my_skills"])}

STEP 1: MANDATORY KNOCKOUT CHECK (Phase 1)
If any of the following are true, the score MUST be 0 and you must STOP:
1. EXPERIENCE: Does the job explicitly require a MINIMUM of more than 2 years? 
   - Examples of FAIL (Score 0): "3+ years", "Minimum 4 years", "5-7 years", "Senior level".
   - Examples of PASS: "1-2 years", "2+ years", "Entry level", "0-3 years".
2. LOCATION: Is the job explicitly outside the United States? (Check for non-US cities or currencies like GBP/INR).
3. CITIZENSHIP: Does it require "US Citizenship Only" or "Active Security Clearance"?

STEP 2: SCORING (Only if Step 1 passes)
If the job is a PASS for a 2-year candidate, calculate a match score (1-100):
- Base Score: {len(pre_matched)} skills already confirmed by regex.
- Scoring Table (Total matches): 2 skills=50, 3 skills=68, 4 skills=80, 5 skills=88, 6+ skills=95+.
- Add +5 bonus if the role mentions "Junior", "Associate", "Entry Level", or "New Grad".
- Add +{bonus} visa-friendly bonus points (already detected).

Return ONLY valid JSON (no markdown):
{{
    "score": <int 0-100>,
    "years_required": <int or null>,
    "matches": ["list", "of", "skills", "found"],
    "visa_status": "<Friendly | Not Mentioned | Unfriendly>",
    "reason": "<1 sentence explaining if it passed the 2-year limit and why it got this score>"
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
                temperature=0.1,  # Low temperature for strict adherence to rules
            ),
        )
        
        # Clean potential markdown from response
        raw = re.sub(r"```json|```", "", resp.text.strip()).strip()
        result = json.loads(raw)
        
        # Final safety check: if AI says years > 2 but didn't 0 the score, we override it here.
        if result.get("years_required") and int(result["years_required"]) > 2:
            result["score"] = 0
            result["reason"] = f"Manual Override: Requires {result['years_required']} years. {result['reason']}"
            
        return result

    except Exception as e:
        # Fallback if AI crashes
        return {
            "score": 0,
            "years_required": None,
            "matches": pre_matched,
            "skill_count": len(pre_matched),
            "reason": f"AI Evaluation Error: {e}",
            "visa_status": "Unknown",
        }


def fetch_google_jobs(job_title: str, start: int = 0) -> list[dict]:
    """
    One SerpAPI call using google_jobs engine.
    Returns list of structured job dicts.
    """
    params = {
        "engine"       : "google_jobs",   
        "q"            : job_title,
        "location"     : "United States", 
        "google_domain": "google.com",
        "hl"           : "en",
        "gl"           : "us",
        "chips"        : "date_posted:today",  
        "num"          : 20,
        "api_key"      : SERPAPI_KEY,
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


def find_jobs_blitz() -> list[dict]:
    """
    Fetch jobs for all job titles using google_jobs engine.
    Budget: 15 titles × 1 call = 15 calls/run  (very safe for 100/month)
    Each call returns up to 10 structured jobs.
    Expected raw jobs: 15 × 10 = ~150 per run.
    """
    all_jobs    = []
    seen_ids    = set()   # Deduplicate by job_id
    n_calls     = 0
    BUDGET      = 15      # Max calls per run

    print(f"⚡ GOOGLE JOBS ENGINE BLITZ")
    print(f"   Engine         : google_jobs (structured — no scraping needed)")
    print(f"   Job titles     : {len(JOB_TITLES)}")
    print(f"   Date filter    : Today only (chips=date_posted:today)")
    print(f"   Location       : United States\n")

    for title in JOB_TITLES:
        if n_calls >= BUDGET:
            print(f"   🛑 Budget cap ({BUDGET} calls) reached.")
            break

        jobs = fetch_google_jobs(title)
        n_calls += 1

        new_jobs = []
        for job in jobs:
            job_id = job.get("job_id", job.get("title", "") + job.get("company_name", ""))
            if job_id not in seen_ids:
                seen_ids.add(job_id)
                new_jobs.append(job)

        all_jobs.extend(new_jobs)
        print(f"   [{n_calls:>2}/{BUDGET}] '{title:<35}' → {len(new_jobs)} jobs  (total: {len(all_jobs)})")
        time.sleep(0.4)

    print(f"\n✅ FETCH DONE | {len(all_jobs)} unique raw jobs | {n_calls} API calls used\n")
    return all_jobs


# ==========================================
# 🕷️  PHASE 2: FILTER → SKILL COUNT → AI SCORE → RANK
# (No Playwright — description already in API response)
# ==========================================

def run_agent():
    # STEP 1: Fetch structured jobs
    raw_jobs = find_jobs_blitz()
    if not raw_jobs:
        print("❌ No jobs found.")
        return

    all_results = [] # To store every job for the CSV
    scored_only = [] # To assist in ranking the top 25

    print(f"🧠 PROCESSING {len(raw_jobs)} jobs...\n")

    for i, job in enumerate(raw_jobs):
        title   = job.get("title", "Unknown")
        company = job.get("company_name", "Unknown")
        
        # Metadata for CSV
        row = {
            "job_title": title,
            "company": company,
            "location": job.get("location", "Unknown"),
            "apply_link": get_apply_link(job),
            "posted": (job.get("detected_extensions", {}) or {}).get("posted_at", "Today"),
            "visa_status": "Not Evaluated",
            "score": 0,
            "rejection_reason": ""
        }

        # STEP 2: Hard filter
        rejected, reason = hard_filter(job)
        if rejected:
            row["rejection_reason"] = f"REJECTED: {reason}"
            all_results.append(row)
            continue

        # STEP 3: Regex skill count
        full_text = get_full_text(job)
        skill_n, skill_list = regex_skill_count(full_text)

        if skill_n < 2:
            row["rejection_reason"] = f"SKIPPED: Low skill match ({skill_n})"
            all_results.append(row)
            continue

        # STEP 4: AI Scoring
        ai_data = ai_score_job(full_text, skill_list, title)
        
        # Merge AI data into our row
        row.update({
            "score": ai_data.get("score", 0),
            "visa_status": ai_data.get("visa_status", "Unknown"),
            "rejection_reason": "PASSED",
            "matches": ", ".join(ai_data.get("matches", []))
        })
        
        all_results.append(row)
        scored_only.append(row)

    # STEP 5: Sort by Score (Ranked Order)
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # STEP 6: Save to CSV
    output_file = "usa_jobs_ranked_full.csv"
    fieldnames = ["score", "job_title", "company", "location", "visa_status", "posted", "apply_link", "rejection_reason"]
    
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_results)

    print(f"\n✅ Saved {len(all_results)} total entries to {output_file}")
    
    # Display Top 25
    top_25 = [j for j in all_results if j["rejection_reason"] == "PASSED"][:25]
    print(f"\n🏆 TOP {len(top_25)} QUALIFIED MATCHES:")
    for rank, job in enumerate(top_25, 1):
        print(f"  #{rank:>2} [{job['score']:>3}/100] {job['job_title']} @ {job['company']}")


if __name__ == "__main__":
    run_agent()