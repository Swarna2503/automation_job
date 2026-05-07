# run_discovery.py
from ai_job_agent import run_scraper_agent

if __name__ == "__main__":
    print("Running job discovery...")
    matches = run_scraper_agent()
    print(f"Discovery done. {len(matches)} jobs with score >=70 saved to usa_jobs_ranked_full.csv")
