# AI Job Agent — Your Personal Recruiter in the Terminal
An intelligent CLI-based agent that finds, filters, scores, and helps you apply to jobs tailored to your profile — saving hours of manual job searching.

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

## Features

- AI-powered job scoring using Gemini
- Experience-aware filtering (strict 2-year cap logic)
- Automatic removal of non-US roles
- Visa-aware filtering and scoring
- Fast job discovery with API budget optimization
- Human-in-the-loop auto application (Playwright)
- Ranked job output (CSV)
- Interactive CLI experience (guided workflow)

## Setup

### 1. Clone the repo
git clone https://github.com/your-username/ai-job-agent.git
cd ai-job-agent

### 2. Install dependencies
pip install -r requirements.txt

### 3. Add environment variables
Create a `.env` file: An example .env is given in the repository

### 4. Run the agent
python3 ai_job_agent.py

## Architecture

<img width="803" height="628" alt="Screenshot 2026-03-22 at 6 17 55 PM" src="https://github.com/user-attachments/assets/be23f5f0-01c2-408c-b394-b4c284d1c5e3" />
