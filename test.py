from serpapi import GoogleSearch

# 1. Define parameters inside a dictionary
# The "engine" key tells SerpApi specifically to scrape Google Jobs
params = {
  "engine": "google_jobs", 
  "q": "Python Developer",
  "location": "United States",
  "google_domain": "google.com",
  "hl": "en",
  "gl": "us",
  "api_key": "2f83060ca035701980298ef1191c2387c11e14b61141915a0e3b29ce658382b3" # Use the key from your dashboard
}

# 2. Pass the params dictionary to GoogleSearch
search = GoogleSearch(params)
results = search.get_dict()

# 3. Safely access the results
if "jobs_results" in results:
    jobs = results["jobs_results"]
    print(f"Successfully found {len(jobs)} jobs.")
    for job in jobs:
        print(f"- {job.get('title')} at {job.get('company_name')}")
else:
    print("Error or no results. Response from API:", results.get("error"))