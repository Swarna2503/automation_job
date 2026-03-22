import time
import os
from playwright.sync_api import sync_playwright

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

# Target URL for the live test
TARGET_URL = "https://cloudacio.freshteam.com/jobs/M3OeGezGiaI-/machine-learning-engineer-in-nlp-contract-remote"

def auto_fill_form(page, profile):
    """
    Finds standard HTML fields and injects profile data locally.
    """
    print("\n⌨️  Searching for form fields to auto-fill...")
    
    # Mapping of common HTML attributes to your profile data
    field_map = {
        'input[name*="first" i], input[id*="first" i]': profile["first_name"],
        'input[name*="last" i], input[id*="last" i]': profile["last_name"],
        'input[name*="email" i], input[id*="email" i]': profile["email"],
        'input[name*="phone" i], input[id*="phone" i]': profile["phone"],
        'input[name*="linkedin" i], input[placeholder*="LinkedIn" i]': profile["linkedin"],
        'input[name*="github" i], input[placeholder*="GitHub" i]': profile["github"],
        'textarea[name*="address" i], input[name*="address" i]': profile["address"],
        
        # ✨ NEW SELECTORS FOR COUNTRY
        'input[name*="country" i], input[id*="country" i], input[placeholder*="Country" i]': profile["country"],
        'select[name*="country" i], select[id*="country" i]': profile["country"]
    }

    for selector, value in field_map.items():
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=2000):
                # Check if it's a dropdown (select) or text input
                tag_name = element.evaluate("el => el.tagName")
                if tag_name == "SELECT":
                    element.select_option(label=value)
                    print(f"   ✅ Selected Country: {value}")
                else:
                    element.fill(value)
                    print(f"   ✅ Filled: {selector.split('[')[1].split(']')[0]}")
        except:
            continue

    # Resume Upload
    try:
        file_input = page.locator('input[type="file"]').first
        if file_input.is_visible(timeout=2000):
            if os.path.exists(profile["resume_path"]):
                file_input.set_input_files(profile["resume_path"])
                print("   📄 Resume uploaded successfully!")
    except Exception as e:
        print(f"   ⚠️ Resume upload skipped: {e}")

def live_apply_and_fill(url):
    print(f"\n🚀 STARTING AUTO-FILL APPLICATION: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Keep browser visible
        context = browser.new_context()
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            # 1. Detect Apply Button
            apply_patterns = ["text=/^Apply$/i", "text='Apply Now'", "button:has-text('Apply')"]
            found_button = None
            for pattern in apply_patterns:
                locator = page.locator(pattern).first
                if locator.is_visible():
                    found_button = locator
                    break

            if found_button:
                found_button.click()
                print("   🖱️ Apply Button Clicked.")
                page.wait_for_timeout(3000)

                # 2. Auto-Fill with New Parameters
                auto_fill_form(page, MY_PROFILE)
                
                print("\n✨ LOCAL FILL COMPLETE.")
                print("⚠️  Review the form and hit SUBMIT manually.")
                input(">> Press ENTER to close browser...")
            else:
                print("   ❌ No apply button found.")
        finally:
            browser.close()

if __name__ == "__main__":
    live_apply_and_fill(TARGET_URL)