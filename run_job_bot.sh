#!/bin/bash
cd /Users/swarna/Desktop/ai_job_agent
echo "=== Starting discovery at $(date) ===" >> bot_log.txt
python run_discovery.py
echo "=== Discovery finished at $(date) ===" >> bot_log.txt
echo "=== Starting manual applications at $(date) ===" >> bot_log.txt
python -c "from ai_job_agent import manual_apply_with_real_chrome; import csv; jobs = [row for row in csv.DictReader(open('usa_jobs_ranked_full.csv')) if int(row['score']) >= 70]; print(f'Found {len(jobs)} jobs to apply'); manual_apply_with_real_chrome(jobs)"
echo "=== Applications finished at $(date) ===" >> bot_log.txt
