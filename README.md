# AutoApply AI — An AI Agent, Your Personal Recruiter in the Terminal
An intelligent CLI-based agent that finds, filters, scores, and helps you apply to jobs tailored to your profile saving hours of manual job searching.

## The Problem

Job searching is time-consuming and inefficient:
- Hundreds of irrelevant listings
- Repetitive applications
- No personalization for experience level or visa needs

Most platforms like LinkedIn or Indeed show generic results that don’t adapt to individual constraints.

## The Solution

This project builds a **personal AI recruiter** that:
- Searches jobs using real-time data (SerpAPI)
- Filters out irrelevant roles (based on experience, location, sponsorship)
- Scores jobs based on skill match + experience constraints
- Assists with applications using browser automation

All from a simple terminal interface.

## Setup

### 1. Clone the repo
git clone https://github.com/Swarna2503/automation_job.git
cd ai-job-agent

### 2. Install dependencies
pip install -r requirements.txt

### 3. Add environment variables
Create a `.env` file: An example .env is given in the repository

### 4. Run the agent
python3 ai_job_agent.py

## Architecture
<img width="355" height="282" alt="Screenshot 2026-03-22 at 8 04 26 PM" src="https://github.com/user-attachments/assets/47c59907-baba-4c78-88b7-5c63d28a59fb" />


