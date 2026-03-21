import os
import json
import time
import csv
import re
from serpapi import GoogleSearch
from playwright.sync_api import sync_playwright
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# ⚙️  CONFIG
# ==========================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client      = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_ID    = "gemini-2.5-flash"

PREFS = {
    "my_exp"           : 2,
    "needs_sponsorship": True,

    # ✅ UPDATED: Full skill list from your profile
    "my_skills": [
        # Programming Languages
        "Python", "SQL", "R", "Java", "C++",

        # Machine Learning & AI
        "LLMs", "RAG", "NLP", "Clustering", "Segmentation",
        "Recommendation Systems", "Feature Engineering",
        "ADK", "Machine Learning", "Deep Learning",

        # Libraries & Models
        "Scikit-Learn", "PyTorch", "TensorFlow", "BERT",
        "XGBoost", "LightGBM", "CatBoost", "Autoencoders",

        # Data Engineering & Platforms
        "Hive", "AWS", "Databricks", "Spark", "PySpark",
        "Hadoop", "MongoDB", "Git",

        # Analytics & Visualization
        "Tableau", "Power BI", "Matplotlib",

        # Web Technologies
        "JavaScript", "TypeScript", "HTML", "CSS", "Bootstrap",
    ],

    "blocked_sites": [
        "indeed.com", "linkedin.com", "ziprecruiter.com",
        "glassdoor.com", "simplyhired.com", "monster.com",
    ],
}

# ==========================================
# 💡 FREE SERPAPI STRATEGY  (100 calls/month)
# ------------------------------------------
# BUG FIXED: "United States" in query string was the #1
# cause of only 24 leads. Most ATS pages (greenhouse, lever)
# don't contain the literal phrase "United States" so Google
# returned 0-1 results per search.
#
# NEW approach:
#   • Use gl=us (Google geo-targeting) — no text requirement
#   • Use broader job title queries
#   • Add pagination on top 3 platforms (+20 results each)
#   • Seniority checked on JOB TITLE ONLY (not full body)
#
# Budget: 7 platforms × 10 titles × 1 page = 70 calls
#       + 3 platforms × 10 titles × 1 extra page = 30 calls
#       = 100 calls exactly  ✓
# ==========================================

# ── Platforms split: TOP (get 2 pages) vs STANDARD (1 page) ──
PLATFORMS_TOP = [
    # These 3 have the highest US job density — worth paginating
    "site:greenhouse.io",
    "site:lever.co",
    "site:ashbyhq.com",
]

PLATFORMS_STANDARD = [
    "site:myworkdayjobs.com",
    "site:wellfound.com",
    "site:workatastartup.com",
    "site:handshake.com",       # Best for OPT/new-grad
    "site:himalayas.app",       # Remote-US focused
    "site:smartrecruiters.com",
    "site:icims.com",
]

# 10 broad job titles — maximum result density per search call
JOB_TITLES = [
    '"python developer"',
    '"machine learning engineer"',
    '"data scientist"',
    '"AI engineer"',
    '"data engineer"',
    '"NLP engineer"',
    '"software engineer" python',
    '"ML engineer"',
    '"applied scientist"',
    '"analytics engineer"',
]

# ==========================================
# 🌎 USA FILTERS
# ------------------------------------------
# FIX: Seniority words (senior/lead/manager) now checked
# ONLY in the first 350 chars (the job title / header area)
# NOT the entire body — "reports to a senior manager" was
# wrongly rejecting junior roles.
# ==========================================
NON_US_KEYWORDS = [
    # Countries
    "israel", "india", "united kingdom", "canada", "germany", "france",
    "australia", "netherlands", "singapore", "ireland", "poland", "spain",
    "brazil", "mexico", "philippines", "ukraine", "pakistan", "china",
    "japan", "south korea", "new zealand", "sweden", "norway", "denmark",
    # Non-US cities
    "tel aviv", "bangalore", "bengaluru", "mumbai", "hyderabad", "chennai",
    "london", "toronto", "vancouver", "berlin", "amsterdam", "sydney",
    "dublin", "paris", "zurich", "stockholm", "oslo", "copenhagen",
    # Currency / domain giveaways
    "£", "€", "₹", "cad$", "aud$", "sgd",
    ".co.uk", ".co.in", ".com.au", ".ca/jobs",
    "outside the us", "non-us", "apac", "emea", "latam",
    "work from anywhere outside", "based outside the united states",
]

# Experience patterns — checked on FULL BODY (years of exp is always explicit)
EXP_BODY_PATTERNS = [
    r'\b([3-9]|\d{2,})\+\s*years?\s*(of\s*)?(experience|exp)\b',
    r'\b([4-9]|\d{2,})\s*years?\s*(of\s*)?(experience|exp)\b',
    r'\bminimum\s+([3-9]|\d{2,})\s*years?\b',
    r'\bat\s+least\s+([3-9]|\d{2,})\s*years?\b',
    r'\b([3-9]|\d{2,})\s*[-–]\s*\d+\s*years?\s*(of\s*)?(experience|exp)\b',
]

# Seniority title patterns — checked on FIRST 350 CHARS ONLY (job title area)
# This prevents false positives from phrases like "reports to a senior manager"
SENIORITY_TITLE_PATTERNS = [
    r'\bsenior\b', r'\bsr\.\b', r'\bstaff\b', r'\bprincipal\b',
    r'\bdirector\b', r'\bvp\b', r'\bvice president\b',
    r'\bmanager\b',
    r'\blead\s+(engineer|developer|scientist|analyst)\b',  # "lead engineer" but not "you will lead"
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
    r'\be.?verify\b',
    r'\bopt\b', r'\bcpt\b',
    r'\bh.?1.?b\b',
    r'\bvisa sponsorship\s*(is\s*)?(available|provided|offered|considered|welcome)\b',
    r'\bwill\s+sponsor\b',
    r'\bopen to\s+sponsorship\b',
    r'\buniversity\s+(hire|grad|graduate|recruit)\b',
    r'\bnew\s*grad(uate)?\b',
    r'\brelocation\s+(assistance|package)\b',
]


# ==========================================
# 🔧 FILTER HELPERS
# ==========================================

def hard_filter(text: str) -> tuple[bool, str]:
    """
    Free regex checks — run before any AI or scraping cost.
    FIX: Seniority checked on title area only (first 350 chars).
    Returns (should_reject, reason).
    """
    t      = text.lower()
    title_area = t[:350]   # Job title + first paragraph only

    # 1. Non-US location in full body
    for kw in NON_US_KEYWORDS:
        if kw in t:
            return True, f"Non-US keyword: '{kw}'"

    # 2. Experience years — full body (explicit, never false-positive)
    for p in EXP_BODY_PATTERNS:
        if re.search(p, t):
            return True, f"Over-experience: '{p}'"

    # 3. Seniority — TITLE AREA ONLY (fixes false rejections)
    for p in SENIORITY_TITLE_PATTERNS:
        if re.search(p, title_area):
            return True, f"Senior title: '{p}'"

    # 4. Security clearance — full body
    for p in CLEARANCE_PATTERNS:
        if re.search(p, t):
            return True, f"Clearance required: '{p}'"

    # 5. Sponsorship rejection — full body
    if PREFS["needs_sponsorship"]:
        for p in NO_SPONSORSHIP_PATTERNS:
            if re.search(p, t):
                return True, f"No sponsorship: '{p}'"

    return False, ""


def regex_skill_count(text: str) -> tuple[int, list[str]]:
    """
    Fast free skill counter — no AI needed.
    With 30+ skills in the list, even 2-3 matches = relevant job.
    Returns (count, matched_skills_list).
    """
    t       = text.lower()
    matched = []
    aliases = {
        "Scikit-Learn" : r"scikit[\s\-]?learn|sklearn",
        "PySpark"      : r"pyspark|py[\s\-]?spark",
        "Spark"        : r"\bspark\b",
        "Power BI"     : r"power[\s\-]?bi",
        "C++"          : r"c\+\+|c\s*plus\s*plus",
        "LightGBM"     : r"lightgbm|light\s*gbm",
        "XGBoost"      : r"xgboost|xg\s*boost",
        "TensorFlow"   : r"tensorflow|tensor\s*flow",
        "PyTorch"      : r"pytorch|py\s*torch",
        "JavaScript"   : r"javascript|js\b",
        "TypeScript"   : r"typescript|ts\b",
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


# ==========================================
# 🔍 PHASE 1: SEARCH
# ------------------------------------------
# KEY FIXES vs v3:
# 1. Removed "United States" from query string (was killing results)
# 2. gl=us handles geo-targeting at Google API level
# 3. Pagination on top 3 platforms (2 pages = 20 results each)
# 4. No seniority exclusions in query (handled by title-area filter)
# Budget: 3×10×2 + 7×10×1 = 60+70 = 100 calls ✓ 
# Expected: 100 calls × ~8 results avg = ~800 raw leads
# ==========================================

def _serpapi_fetch(query: str, start: int = 0) -> list[str]:
    """
    One SerpAPI call → list of clean job URLs.
    start=0  → results 1-10
    start=10 → results 11-20  (pagination)
    """
    params = {
        "engine" : "google",
        "q"      : query,
        "api_key": SERPAPI_KEY,
        "tbs"    : "qdr:d",    # Strictly 1 day ✅
        "gl"     : "us",       # US geo-targeting (replaces "United States" text)
        "hl"     : "en",
        "num"    : 10,
        "start"  : start,
    }
    try:
        results = GoogleSearch(params).get_dict().get("organic_results", [])
        urls = []
        for r in results:
            link = r.get("link", "")
            if link and not any(b in link for b in PREFS["blocked_sites"]):
                urls.append(link)
        return urls
    except Exception as e:
        print(f"      ⚠️  SerpAPI error: {e}")
        return []


def find_jobs_blitz() -> list[str]:
    all_urls   = set()
    n_calls    = 0
    BUDGET     = 96   # Leave 4 buffer from 100/month

    # No "United States" text — gl=us handles geo
    # No -Senior/-Lead in query — title-area filter handles it in scraping
    # This alone should 5-10x the results vs v3
    exclude = '-Director -VP'   # Only block the most extreme seniority at search level

    total_calls_planned = (
        len(PLATFORMS_TOP)      * len(JOB_TITLES) * 2 +   # 2 pages
        len(PLATFORMS_STANDARD) * len(JOB_TITLES) * 1     # 1 page
    )
    print(f"⚡ BLITZ START")
    print(f"   TOP platforms    : {len(PLATFORMS_TOP)} × {len(JOB_TITLES)} titles × 2 pages = {len(PLATFORMS_TOP)*len(JOB_TITLES)*2} calls")
    print(f"   STD platforms    : {len(PLATFORMS_STANDARD)} × {len(JOB_TITLES)} titles × 1 page  = {len(PLATFORMS_STANDARD)*len(JOB_TITLES)} calls")
    print(f"   Total planned    : {total_calls_planned} / {BUDGET} budget")
    print(f"   Time window      : 24h | Geo: US only\n")

    all_platforms = [
        (p, [0, 10]) for p in PLATFORMS_TOP        # 2 pages
    ] + [
        (p, [0])     for p in PLATFORMS_STANDARD   # 1 page
    ]

    for p_idx, (platform, pages) in enumerate(all_platforms):
        hits_this = 0
        label     = "TOP" if pages == [0, 10] else "STD"

        for title in JOB_TITLES:
            for start in pages:
                if n_calls >= BUDGET:
                    print(f"\n   🛑 Budget cap ({BUDGET}) reached.")
                    break

                query = f'{platform} {title} {exclude}'
                urls  = _serpapi_fetch(query, start=start)
                n_calls += 1

                new = [u for u in urls if u not in all_urls]
                all_urls.update(new)
                hits_this += len(new)
                time.sleep(0.35)

            if n_calls >= BUDGET:
                break

        print(
            f"   [{p_idx+1:02d}/{len(all_platforms)}][{label}] {platform:<30}"
            f"  +{hits_this:>3} leads   total={len(all_urls)}"
        )

        if n_calls >= BUDGET:
            break

    print(f"\n✅ SEARCH DONE | {len(all_urls)} unique URLs | {n_calls} API calls used\n")
    return list(all_urls)


# ==========================================
# 🧠 PHASE 2: AI SCORER
# ==========================================

def ai_score_job(text: str, pre_matched: list[str]) -> dict:
    """AI scoring — called only when regex finds ≥ 2 skill matches."""
    bonus = visa_bonus(text)

    prompt = f"""
You are a technical recruiter evaluating a US job posting for a candidate with
EXACTLY 2 YEARS of experience who needs visa sponsorship (H1B/OPT).

Candidate's full skill set:
{', '.join(PREFS["my_skills"])}

Skills already confirmed present by regex scan: {pre_matched} ({len(pre_matched)} skills)

YOUR TASK: Score this job 0-100 based on skill fit.

SCORING RULES:
- Regex already confirmed {len(pre_matched)} skills. Verify and find any additional matches.
- Score by TOTAL confirmed skills:
    1  → 25    2  → 50    3  → 68
    4  → 80    5  → 88    6  → 93    7+ → 96-100
- Bonus +5  if role says "entry-level", "junior", "0-2 years", or "new grad"
- Visa bonus: +{bonus} pts (pre-computed — add this directly to your score)
- Do NOT penalise for missing skills — score what IS there

Return ONLY valid JSON (no markdown fences, no extra text):
{{
    "score"      : <int 0-100>,
    "matches"    : ["every", "matched", "skill"],
    "skill_count": <int>,
    "reason"     : "<2 sentences: why this role fits a 2yr candidate>",
    "visa_status": "<Friendly | Not Mentioned | Unfriendly>",
    "job_title"  : "<exact job title extracted from JD>"
}}

JD TEXT:
{text[:5500]}
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
        # Graceful fallback — don't lose the job just because AI errored
        return {
            "score"      : max(25, len(pre_matched) * 14),
            "matches"    : pre_matched,
            "skill_count": len(pre_matched),
            "reason"     : f"AI error — scored by regex only. {e}",
            "visa_status": "Unknown",
            "job_title"  : "Unknown",
        }


# ==========================================
# 🕷️  PHASE 3: SCRAPE → FILTER → SCORE → RANK
# ==========================================

def run_agent():
    raw_leads = find_jobs_blitz()
    if not raw_leads:
        print("❌ No leads found. Check SERPAPI_KEY in .env")
        return

    print(f"🕷️  SCRAPING & SCORING {len(raw_leads)} leads...\n")

    all_scored      = []
    hard_rejected   = 0
    low_skill_skip  = 0
    rejection_log   = {}   # Count rejection reasons for debugging

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for i, url in enumerate(raw_leads):
            print(f"[{i+1:>4}/{len(raw_leads)}] {url[:72]}")
            try:
                page = browser.new_page()
                # Block images/fonts to speed up scraping
                page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf,otf}",
                           lambda r: r.abort())
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(1200)
                content = page.inner_text("body")[:10000]
                page.close()

                # ── STEP 1: Free hard filter ────────────────────
                rejected, reason = hard_filter(content)
                if rejected:
                    hard_rejected += 1
                    category = reason.split(":")[0]
                    rejection_log[category] = rejection_log.get(category, 0) + 1
                    print(f"         🚫 {reason}")
                    continue

                # ── STEP 2: Free regex skill pre-check ──────────
                skill_n, skill_list = regex_skill_count(content)
                if skill_n < 2:
                    low_skill_skip += 1
                    print(f"         ⬇️  {skill_n} skill match — too low, skip AI")
                    continue

                print(f"         ✅ {skill_n} skills: {skill_list}")

                # ── STEP 3: AI detailed score ────────────────────
                result              = ai_score_job(content, skill_list)
                result["url"]       = url
                result["visa_bonus"]= visa_bonus(content)
                all_scored.append(result)

            except Exception as e:
                print(f"         ⚠️  Error: {e}")
                continue

        browser.close()

    # ── RANK: Best score first ──────────────────────────────────
    all_scored.sort(key=lambda x: x["score"], reverse=True)

    # ── SAVE ────────────────────────────────────────────────────
    output_file = "usa_jobs_ranked.csv"
    fieldnames  = ["score", "skill_count", "job_title", "matches",
                   "visa_status", "visa_bonus", "reason", "url"]
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_scored)

    # ── REJECTION BREAKDOWN (helps debug) ───────────────────────
    top_n = all_scored[:10]
    print(f"\n{'='*68}")
    print(f"🎯 OPERATION COMPLETE")
    print(f"{'='*68}")
    print(f"  📡 Raw leads collected         : {len(raw_leads)}")
    print(f"  🚫 Hard rejected               : {hard_rejected}")
    if rejection_log:
        for reason, count in sorted(rejection_log.items(), key=lambda x: -x[1]):
            print(f"       └─ {reason:<30}: {count}")
    print(f"  ⬇️  Skipped (< 2 skill match)  : {low_skill_skip}")
    print(f"  🧠 AI-scored & saved           : {len(all_scored)}")
    print(f"  💾 Output file                 : {output_file}")
    print(f"{'='*68}")

    if top_n:
        print(f"\n🏆 TOP {len(top_n)} MATCHES (sorted by score):\n")
        for rank, job in enumerate(top_n, 1):
            visa_icon = {"Friendly": "🟢", "Not Mentioned": "🟡", "Unfriendly": "🔴"}.get(
                job.get("visa_status", ""), "⚪"
            )
            print(f"  #{rank:>2}  [{job['score']:>3}/100]  {visa_icon}  "
                  f"{job.get('job_title','Unknown'):<38}  Skills:{job.get('skill_count',0)}")
            print(f"        {job['url'][:75]}")
        print()

    print(f"💡 TIPS:")
    print(f"   • Open '{output_file}' → sort 'score' column descending")
    print(f"   • Filter 'visa_status' = Friendly for safest applications")
    print(f"   • handshake.com & wellfound.com = most OPT-friendly platforms")
    if len(all_scored) < 20:
        print(f"\n⚠️  Got {len(all_scored)} jobs (target: 20+). If consistently low:")
        print(f"   • Run once per day (24h window refreshes midnight UTC)")
        print(f"   • Add more job titles to JOB_TITLES list")
        print(f"   • Check rejection breakdown above — loosen filters if needed")


if __name__ == "__main__":
    run_agent()