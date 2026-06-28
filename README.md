# ResuScan — AI Resume Scanner & ATS Platform

An AI-powered resume screening platform built with Streamlit and Google Gemini. Candidates upload their resume, get an ATS compatibility score against a real job description, identify skill gaps, and receive course recommendations. Recruiters get a portal to post jobs and rank applicants automatically.

---

## Features

**For candidates**
- Upload a PDF resume and analyse it against any job description
- ATS compatibility score (0–100) with matched and missing skills breakdown
- Course recommendations for every missing skill with direct links
- General job matcher — get the top 5 roles you qualify for without needing a JD
- AI career chat advisor that gives personalised advice based on your actual results

**For recruiters**
- Post job listings with required skills and experience level
- View all applicants ranked by ATS score
- Read AI-generated summaries and skill breakdowns per candidate

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| AI / LLM | Google Gemini 2.5 Flash (`google-generativeai`) |
| PDF parsing | PyPDF2 |
| Database | SQLite (via `sqlite3`) |
| Auth | Username / password with role-based access (candidate / recruiter) |
| Environment | python-dotenv |

---

## Screenshots

### Home dashboard
![Home](screenshots/screenshot_home.png)

### ATS analysis result
![ATS Result](screenshots/screenshot_ats_result.png)

### Recruiter portal
![Recruiter Portal](screenshots/screenshot_recruiter_portal.png)

### Candidate portal
![Candidate Portal](screenshots/screenshot_candidate_portal.png)

### General job matcher
![Job Matcher](screenshots/screenshot_job_matcher.png)

---

## Getting started

### 1. Clone the repository
```bash
git clone https://github.com/Amal-Mahesh/ResuScan.git
cd ResuScan
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key

Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com).

> **Never commit your `.env` file.** It is listed in `.gitignore`.

### 4. Run the app
```bash
streamlit run app_v2.py
```

The app opens at `http://localhost:8501`

---

## Project structure

```
ResuScan/
├── app_v2.py          # Main Streamlit app — routing, UI, session state
├── ai_engine.py       # Gemini API calls — ATS analysis, job matching, career chat
├── database.py        # SQLite schema and all DB helper functions
├── requirements.txt   # Python dependencies
├── .env               # API key (not committed — add your own)
├── .gitignore
└── screenshots/       # UI screenshots for README
```

---

## How it works

1. A candidate registers and uploads their resume PDF
2. PyPDF2 extracts the raw text
3. The resume text + job description are sent to Gemini 2.5 Flash with a structured prompt
4. Gemini returns a JSON object with ATS score, matched skills, missing skills, and course recommendations
5. Results are stored in SQLite and displayed in the Streamlit UI
6. The candidate can then chat with an AI career advisor that has full context of their results
7. Recruiters see all applicants for their job listings ranked by ATS score

---

## Known issues / future improvements

- Passwords are currently stored as plaintext — bcrypt hashing planned
- JSON parsing from Gemini could be made more robust with regex fallback
- No cloud deployment yet — SQLite will be migrated to PostgreSQL for production
- LinkedIn and job portal integration planned

---

## Author

**Amal N V**  
B.Tech — Artificial Intelligence & Machine Learning  
Nehru College of Engineering and Research Centre, Kerala

- Email: amalmahesh2020@gmail.com  
- LinkedIn: [linkedin.com/in/amal-n-v-242903330](https://www.linkedin.com/in/amal-n-v-242903330/)  
- GitHub: [github.com/Amal-Mahesh](https://github.com/Amal-Mahesh)

---

## License

MIT License — see [LICENSE](LICENSE) for details.
