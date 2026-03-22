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
        "jobot", "dice", "hirequest",
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
    """AI scoring — only called when regex finds ≥ 2 skill matches."""
    bonus = visa_bonus(full_text)

    prompt = f"""
You are a technical recruiter evaluating a US job posting for a candidate with
EXACTLY 2 YEARS of experience who needs visa sponsorship (H1B/OPT).

Job title being evaluated: "{job_title}"

Candidate's full skill set:
{', '.join(PREFS["my_skills"])}

Skills ALREADY CONFIRMED present by regex scan: {pre_matched} ({len(pre_matched)} confirmed)

YOUR TASK: Score this job 0-100 purely on skill fit.

SCORING TABLE (by total confirmed skill count):
  1 skill  → 25     2 skills → 50     3 skills → 68
  4 skills → 80     5 skills → 88     6 skills → 93
  7+ skills → 96-100

BONUSES (add to base score):
  +5  if role says "entry-level", "junior", "0-2 years", or "new grad"
  +{bonus} visa-friendly signals already detected (add directly)

RULES:
  - Verify the {len(pre_matched)} regex-confirmed skills, then find any extras
  - Do NOT penalise for missing skills
  - Do NOT apply any sponsorship penalty (already filtered upstream)

Return ONLY valid JSON (no markdown, no extra text):
{{
    "score"      : <int 0-100>,
    "matches"    : ["every", "matched", "skill"],
    "skill_count": <int>,
    "reason"     : "<2 sentences: why this fits a 2yr candidate>",
    "visa_status": "<Friendly | Not Mentioned | Unfriendly>"
}}

JOB TEXT:
{full_text[:5000]}
"""
    try:
        resp = client.models.generate_content(
            model    = MODEL_ID,
            contents = prompt,
            config   = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        raw = re.sub(r"```json|```", "", resp.text.strip()).strip()
        return json.loads(raw)
    except Exception as e:
        return {
            "score"      : max(25, len(pre_matched) * 14),
            "matches"    : pre_matched,
            "skill_count": len(pre_matched),
            "reason"     : f"AI error — regex fallback. {e}",
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
    # ── STEP 1: Fetch structured jobs ─────────────────────
    raw_jobs = find_jobs_blitz()
    if not raw_jobs:
        print("❌ No jobs found. Check SERPAPI_KEY in .env")
        return

    print(f"🧠 FILTERING & SCORING {len(raw_jobs)} jobs...\n")

    all_scored      = []
    hard_rejected   = 0
    low_skill_skip  = 0
    rejection_log   = {}

    for i, job in enumerate(raw_jobs):
        title   = job.get("title", "Unknown")
        company = job.get("company_name", "Unknown")
        loc     = job.get("location", "Unknown")
        print(f"[{i+1:>3}/{len(raw_jobs)}] {title:<40} @ {company:<25} | {loc}")

        # ── STEP 2: Hard filter (free) ─────────────────────
        rejected, reason = hard_filter(job)
        if rejected:
            hard_rejected += 1
            category = reason.split(":")[0]
            rejection_log[category] = rejection_log.get(category, 0) + 1
            print(f"         🚫 {reason}")
            continue

        # ── STEP 3: Regex skill count (free) ──────────────
        full_text           = get_full_text(job)
        skill_n, skill_list = regex_skill_count(full_text)

        if skill_n < 2:
            low_skill_skip += 1
            print(f"         ⬇️  Only {skill_n} skill match — skipped")
            continue

        print(f"         ✅ {skill_n} skills: {skill_list}")

        # ── STEP 4: AI detailed score ──────────────────────
        result = ai_score_job(full_text, skill_list, title)

        # ── Attach metadata ────────────────────────────────
        result["job_title"]  = title
        result["company"]    = company
        result["location"]   = loc
        result["visa_bonus"] = visa_bonus(full_text)
        result["apply_link"] = get_apply_link(job)
        result["posted"]     = (job.get("detected_extensions", {}) or {}).get("posted_at", "Today")
        all_scored.append(result)

    # ── STEP 5: Rank by score ──────────────────────────────
    all_scored.sort(key=lambda x: x["score"], reverse=True)

    # ── STEP 6: Save to CSV ────────────────────────────────
    output_file = "usa_jobs_ranked.csv"
    fieldnames  = [
        "score", "skill_count", "job_title", "company", "location",
        "matches", "visa_status", "visa_bonus", "posted", "reason", "apply_link"
    ]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_scored)

    # ── STEP 7: Summary ────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"🎯 OPERATION COMPLETE")
    print(f"{'='*70}")
    print(f"  📡 Raw jobs from Google Jobs API   : {len(raw_jobs)}")
    print(f"  🚫 Hard rejected                   : {hard_rejected}")
    if rejection_log:
        for cat, cnt in sorted(rejection_log.items(), key=lambda x: -x[1]):
            print(f"       └─ {cat:<35}: {cnt}")
    print(f"  ⬇️  Skipped (< 2 skill match)      : {low_skill_skip}")
    print(f"  🧠 AI-scored & saved               : {len(all_scored)}")
    print(f"  💾 Output                          : {output_file}")
    print(f"{'='*70}")

    if all_scored:
        top = all_scored[:10]
        print(f"\n🏆 TOP {len(top)} MATCHES:\n")
        for rank, job in enumerate(top, 1):
            visa_icon = {"Friendly": "🟢", "Not Mentioned": "🟡",
                         "Unfriendly": "🔴"}.get(job.get("visa_status", ""), "⚪")
            print(
                f"  #{rank:>2}  [{job['score']:>3}/100] {visa_icon}  "
                f"{job['job_title']:<38} @ {job['company']:<22}"
            )
            print(f"        Skills:{job.get('skill_count',0)}  "
                  f"Location:{job['location']:<25}  Posted:{job.get('posted','?')}")
            print(f"        Apply: {job['apply_link'][:72]}")
            print()

    print(f"💡 TIPS:")
    print(f"   • Sort 'score' column descending → best matches first")
    print(f"   • Filter visa_status = Friendly  → safest to apply")
    print(f"   • 'apply_link' column has the direct application URL")
    if len(all_scored) < 20:
        print(f"\n⚠️  Got {len(all_scored)} scored jobs (target: 20+).")
        print(f"   → Add more titles to JOB_TITLES list in the config")
        print(f"   → Or run at different times of day (new jobs post throughout the day)")


if __name__ == "__main__":
    run_agent()