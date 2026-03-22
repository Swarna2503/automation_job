import time
import os
import re
from playwright.sync_api import sync_playwright

# 📁 Path to store your LinkedIn session
USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/PlaywrightLinkedIn")

MY_PROFILE = {
    "first_name": "Lakshmi Swarna Durga",
    "last_name": "Nallam",
    "email": "swarnadurga.nallam@gmail.com",
    "phone": "7133596070",
    "linkedin": "https://www.linkedin.com/in/swarna-nallam/",
    "github": "https://github.com/Swarna2503",
    "address": "1 Hermann Museum Circle Dr, 77004, Houston, TX",
    "country": "United States",
    "resume_path": os.path.abspath("SwarnaNallam.pdf") 
}

def universal_fill(page):
    """The 0-cost local filler that works on ANY website."""
    print(f"⌨️  Scanning for fields on: {page.url[:50]}...")
    
    field_map = {
        'input[name*="first" i], input[id*="first" i], input[placeholder*="First" i]': MY_PROFILE["first_name"],
        'input[name*="last" i], input[id*="last" i], input[placeholder*="Last" i]': MY_PROFILE["last_name"],
        'input[name*="email" i], input[id*="email" i]': MY_PROFILE["email"],
        'input[name*="phone" i], input[id*="phone" i]': MY_PROFILE["phone"],
        'input[name*="linkedin" i], input[placeholder*="LinkedIn" i]': MY_PROFILE["linkedin"],
        'input[name*="github" i], input[placeholder*="GitHub" i]': MY_PROFILE["github"],
        'textarea[name*="address" i], input[name*="address" i]': MY_PROFILE["address"],
        'input[name*="country" i], select[name*="country" i]': MY_PROFILE["country"]
    }

    for selector, value in field_map.items():
        try:
            element = page.locator(selector).first
            if element.is_visible(timeout=2000):
                if element.evaluate("el => el.tagName") == "SELECT":
                    element.select_option(label=value)
                else:
                    element.fill(value)
        except: continue

    # Resume upload
    try:
        file_input = page.locator('input[type="file"]').first
        if file_input.is_visible(timeout=2000):
            file_input.set_input_files(MY_PROFILE["resume_path"])
            print("   📄 Resume uploaded!")
    except: pass

def live_apply_and_fill(url):
    print(f"\n🚀 STARTING UNIVERSAL AGENT: {url}")
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            USER_DATA_DIR, 
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(5000)

            # 1. SEARCH FOR ANY APPLY BUTTON (LinkedIn or Other)
            # This looks for standard buttons or LinkedIn-specific Easy Apply
            easy_apply = page.locator("button.jobs-apply-button--top-card, button:has-text('Easy Apply')").first
            external_apply = page.locator("text='Apply on company site', button:has-text('Apply Now'), a:has-text('Apply Now')").first

            if easy_apply.is_visible():
                print("🎯 Action: EASY APPLY")
                easy_apply.click()
                page.wait_for_timeout(2000)
                # We reuse the logic to fill the popup
                universal_fill(page)
                # Look for 'Next' buttons
                for _ in range(5):
                    next_btn = page.locator("button:has-text('Next'), button:has-text('Review')").first
                    if next_btn.is_visible():
                        next_btn.click()
                        page.wait_for_timeout(1000)
                
            elif external_apply.is_visible():
                print("🎯 Action: EXTERNAL APPLY / REDIRECT")
                # Wait for the new tab to open
                with context.expect_page() as new_page_info:
                    external_apply.click()
                
                new_tab = new_page_info.value
                new_tab.bring_to_front()
                print("   ⏳ Waiting for external site to load...")
                new_tab.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(4000)
                
                # Apply the universal fill to the new tab
                universal_fill(new_tab)
            
            else:
                # If it's a direct job link (Not LinkedIn), just fill it immediately
                print("🎯 Action: DIRECT PAGE FILL")
                universal_fill(page)

            print("\n✨ TASK FINISHED.")
            input(">> Review and Press ENTER to close...")

        except Exception as e:
            print(f"⚠️ Error: {e}")
            input(">> Press ENTER to exit...")
        finally:
            context.close()

if __name__ == "__main__":
    target = "https://www.linkedin.com/jobs/view/machine-learning-ml-engineer-with-active-top-secret-or-dhs-clearance-at-indev-4388745537/"
    live_apply_and_fill(target)