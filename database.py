import sqlite3
import os

DB_PATH = "sqlite_data.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Users Table (Candidates & Recruiters)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('candidate', 'recruiter'))
        )
    ''')

    # 2. Jobs Table (Created by Recruiters)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruiter_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            required_skills TEXT NOT NULL,
            experience_level TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recruiter_id) REFERENCES users(id)
        )
    ''')

    # 3. Applications Table (Submitted by Candidates)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            resume_text TEXT NOT NULL,
            ats_score INTEGER,
            ai_analysis_json TEXT, -- Store the full JSON response from Gemini
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (candidate_id) REFERENCES users(id),
            UNIQUE(job_id, candidate_id) -- Prevent double applications
        )
    ''')

    conn.commit()
    conn.close()

# --- Helper Functions for Authentication ---

def create_user(username, password, role):
    """Creates a new user. Returns True if successful, False if username exists."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(username, password):
    """Checks login credentials. Returns the user tuple (id, username, password, role) or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

# --- Helper Functions for Jobs & Applications ---

def create_job(recruiter_id, title, description, required_skills, experience_level):
    """Creates a new job posting."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO jobs (recruiter_id, title, description, required_skills, experience_level) 
        VALUES (?, ?, ?, ?, ?)
    ''', (recruiter_id, title, description, required_skills, experience_level))
    conn.commit()
    conn.close()

def get_recruiter_jobs(recruiter_id):
    """Fetches all jobs created by a specific recruiter."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status, created_at FROM jobs WHERE recruiter_id = ? ORDER BY created_at DESC", (recruiter_id,))
    jobs = cursor.fetchall()
    conn.close()
    return jobs

def get_job_applications(job_id):
    """Fetches all candidate applications for a specific job, including detailed JSON."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, u.username, a.ats_score, a.applied_at, a.ai_analysis_json
        FROM applications a
        JOIN users u ON a.candidate_id = u.id
        WHERE a.job_id = ?
        ORDER BY a.ats_score DESC
    ''', (job_id,))
    applications = cursor.fetchall()
    conn.close()
    return applications

def get_all_open_jobs():
    """Fetches all open jobs for candidates to view."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.id, j.title, j.description, j.required_skills, j.experience_level, u.username, j.created_at
        FROM jobs j
        JOIN users u ON j.recruiter_id = u.id
        WHERE j.status = 'open'
        ORDER BY j.created_at DESC
    ''')
    jobs = cursor.fetchall()
    conn.close()
    return jobs

def submit_application(job_id, candidate_id, resume_text, ats_score, ai_analysis_json):
    """Submits a candidate's application to a job."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO applications (job_id, candidate_id, resume_text, ats_score, ai_analysis_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (job_id, candidate_id, resume_text, ats_score, ai_analysis_json))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Candidate has already applied to this job (Unique Constraint violated)
        return False
    finally:
        conn.close()



