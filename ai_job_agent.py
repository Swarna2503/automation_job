import csv
import os
import time
from playwright.sync_api import sync_playwright

# --- YOUR PROFILE DETAILS ---
MY_PROFILE = {
    "first_name": "Lakshmi Swarna Durga",
    "last_name": "Nallam",
    "email": "swarnadurga.nallam@gmail.com",
    "phone": "7133596070",
    "linkedin": "https://www.linkedin.com/in/swarna-nallam/",
    "github": "https://github.com/Swarna2503",
    "portfolio": "https://swarna2503.github.io/swarna-portfolio/",
    "address": "1 Hermann Museum Circle Dr, 77004, Houston, TX",
    "country": "United States",                
    "resume_path": os.path.expanduser("SwarnaNallam.pdf") 
}

def auto_fill_form(page, profile):
    """
    Finds standard HTML fields and injects profile data locally using generic selectors.
    """
    print("   ⌨️  Searching for form fields to auto-fill...")
    
    field_map = {
        'input[name*="first" i], input[id*="first" i], input[placeholder*="first" i]': profile["first_name"],
        'input[name*="last" i], input[id*="last" i], input[placeholder*="last" i]': profile["last_name"],
        'input[name*="email" i], input[id*="email" i], input[type="email"]': profile["email"],
        'input[name*="phone" i], input[id*="phone" i], input[type="tel"]': profile["phone"],
        'input[name*="linkedin" i], input[placeholder*="LinkedIn" i]': profile["linkedin"],
        'input[name*="github" i], input[placeholder*="GitHub" i]': profile["github"],
        'input[name*="portfolio" i], input[name*="website" i]': profile["portfolio"],
        'textarea[name*="address" i], input[name*="address" i]': profile["address"],
        'input[name*="country" i], input[id*="country" i], input[placeholder*="Country" i]': profile["country"],
        'select[name*="country" i], select[id*="country" i]': profile["country"]
    }

    # 1. Fill text and select fields
    for selector, value in field_map.items():
        locator = page.locator(selector).first
        try:
            # Wait up to 2 seconds for the field to appear
            locator.wait_for(state="attached", timeout=2000)
            
            tag_name = locator.evaluate("el => el.tagName").upper()
            if tag_name == "SELECT":
                locator.select_option(label=value)
                print(f"      ✅ Selected: {value}")
            else:
                locator.fill(value)
                # Keep terminal output clean by just showing the first part of the selector
                clean_name = selector.split('[')[1].split(']')[0]
                print(f"      ✅ Filled: {clean_name}")
        except Exception:
            # Field doesn't exist on this specific ATS, just move to the next one
            continue

    # 2. Upload Resume
    try:
        # file inputs are often hidden by CSS for styling, so we wait for "attached" not "visible"
        file_input = page.locator('input[type="file"]').first
        file_input.wait_for(state="attached", timeout=2000)
        
        if os.path.exists(profile["resume_path"]):
            file_input.set_input_files(profile["resume_path"])
            print("      📄 Resume uploaded successfully!")
        else:
            print(f"      ⚠️ Resume file NOT FOUND at: {profile['resume_path']}")
    except Exception:
        print("      ⚠️ No resume upload field detected.")


def process_job(page, company, job_title, url):
    """
    Navigates to the job, tries to click Apply, and fills the form.
    """
    print(f"\n=========================================================")
    print(f"🚀 APPLYING TO: {job_title} @ {company}")
    print(f"🔗 URL: {url}")
    
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3000) # Give React/Angular pages a moment to render

        # 1. Detect Apply Button (Some ATS platforms need this clicked first to show the form)
        apply_patterns = [
            "text=/^Apply$/i", 
            "text=/^Apply Now$/i", 
            "button:has-text('Apply')",
            "a:has-text('Apply')"
        ]
        
        for pattern in apply_patterns:
            locator = page.locator(pattern).first
            try:
                if locator.is_visible(timeout=1500):
                    locator.click()
                    print("   🖱️ Clicked 'Apply' button.")
                    page.wait_for_timeout(2000) # Wait for form to expand/load
                    break
            except Exception:
                continue

        # 2. Auto-Fill the form
        auto_fill_form(page, MY_PROFILE)
        
        print("\n✨ LOCAL FILL COMPLETE.")
        print("⚠️  Please review the form, answer any custom questions, and hit SUBMIT manually.")
        
    except Exception as e:
        print(f"   ❌ Failed to load or process page: {e}")


def run_batch_apply():
    # 1. Load the jobs from Phase 1
    jobs = []
    try:
        with open("usa_jobs_qualified_only.csv", "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            jobs = list(reader)
    except FileNotFoundError:
        print("❌ CSV file not found. Make sure you run the scraper script first!")
        return

    if not jobs:
        print("🤷‍♂️ No jobs found in the CSV.")
        return

    print(f"🎯 Loaded {len(jobs)} jobs. Booting up browser...")

    # 2. Launch persistent browser
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context()
        page = context.new_page()

        for job in jobs:
            apply_link = job.get("apply_link")
            if not apply_link:
                print(f"\n⏭️ Skipping {job['company']} - No apply link found.")
                continue

            # Run the automation for this specific job
            process_job(page, job["company"], job["job_title"], apply_link)
            
            # 3. Pause and wait for user permission to proceed to the next job
            input("\n>> Press ENTER to move to the next job in the queue... ")

        print("\n🏁 All jobs in the CSV have been processed!")
        browser.close()


if __name__ == "__main__":
    # Ensure resume exists before starting the long loop
    if not os.path.exists(MY_PROFILE["resume_path"]):
        print(f"🚨 WARNING: Could not find resume at {MY_PROFILE['resume_path']}")
        print("🚨 Please check the file name and path.")
        exit()
        
    run_batch_apply()