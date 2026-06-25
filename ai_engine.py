import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import PyPDF2
import json
import time

# Replace with your actual API key, or use an environment variable
GEMINI_API_KEY = "AIzaSyCW3BsMUynHXeltKtBFSa4pNmbTvf0Dkh4"
genai.configure(api_key=GEMINI_API_KEY)

def call_gemini_with_retry(model, prompt, max_retries=6, delay=8):
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except ResourceExhausted as e:
            if attempt == max_retries - 1:
                raise e
            print(f"Quota hit. Waiting {delay}s before retry (Attempt {attempt+1}/{max_retries})...")
            time.sleep(delay)


def extract_text_from_pdf(pdf_file):
    """Utility function to extract raw text from an uploaded PDF stream."""
    text = ""
    reader = PyPDF2.PdfReader(pdf_file)
    for page in range(len(reader.pages)):
        text += reader.pages[page].extract_text()
    return text

def analyze_resume_ats(resume_text, job_description):
    """Sends the resume and JD to the AI and asks for an ATS analysis with course recommendations."""
    
    # Using the latest model
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are an expert ATS (Applicant Tracking System) software and a senior technical recruiter/mentor.
    Evaluate the following Resume against the given Job Description.
    
    You must return the result as a raw JSON object string with the following exact keys:
    {{
        "ats_score": (A number from 0 to 100 based on keyword match, experience relevance, and project alignment),
        "matching_skills": [(List of key skills that match the JD)],
        "missing_skills": [(List of crucial skills in the JD that are NOT in the resume)],
        "recommendation": (A 2-3 sentence summary evaluating the candidate),
        "suggested_job_roles": [(List of 3 alternative job roles this resume is best suited for)],
        "course_recommendations": [
            {{
                "skill": "Name of the missing skill",
                "course_name": "Suggested online course title",
                "platform": "e.g., Coursera, Udemy, YouTube",
                "link": "A generic search link or real link, e.g., 'https://www.coursera.org/search?query=skillname'"
            }}
        ]
    }}
    
    --- RESUME TEXT ---
    {resume_text}
    
    --- JOB DESCRIPTION ---
    {job_description}
    """
    
    try:
        response = call_gemini_with_retry(model, prompt)
    except Exception as e:
        print(f"Failed to generate ATS analysis: {e}")
        return None
    
    
    try:
        # Clean up any markdown formatting wrapping the JSON
        clean_text = response.text.strip('`').replace('json\n', '', 1).strip()
        result_dict = json.loads(clean_text)
        return result_dict
    except Exception as e:
        print("Error parsing AI response:", e)
        print("Raw text was:", response.text)
        return None

def analyze_resume_general(resume_text):
    """Analyzes a resume specifically to recommend job roles (No JD required)."""
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    You are an expert technical recruiter and career coach.
    Analyze the following Resume. Determine the top 5 job roles the candidate is most qualified for
    based purely on the skills, experience, and projects listed.
    
    You must return a raw JSON object string with the following exact structure:
    {{
        "profile_summary": "A 2-sentence summary of the candidate's core strengths.",
        "recommended_roles": [
            {{
                "role": "Specific Job Title (e.g., Senior Frontend Engineer)",
                "match_percentage": (A number from 0 to 100 based on how well their resume naturally aligns with this role's industry standard requirements),
                "reason": "One sentence explaining why they are a strong fit for this role."
            }}
        ]
    }}
    
    --- RESUME TEXT ---
    {resume_text}
    """
    
    try:
        response = call_gemini_with_retry(model, prompt)
    except Exception as e:
        print(f"Failed to generate general analysis: {e}")
        return None
    
    try:
        clean_text = response.text.strip('`').replace('json\n', '', 1).strip()
        result_dict = json.loads(clean_text)
        return result_dict
    except Exception as e:
        print("Error parsing general AI response:", e)
        return None

def career_chat_response(analysis_context: dict, chat_history: list, user_message: str) -> str:
    """
    Provides a context-aware career advice response using Gemini.
    
    - analysis_context: the ATS result dict (ats_score, missing_skills, etc.)
    - chat_history: list of {"role": "user"/"assistant", "content": "..."} dicts
    - user_message: the latest message from the candidate
    """
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # Build a concise context string from the ATS analysis
    score = analysis_context.get("ats_score", "N/A")
    matched = ", ".join(analysis_context.get("matching_skills", [])) or "None"
    missing = ", ".join(analysis_context.get("missing_skills", [])) or "None"
    recommendation = analysis_context.get("recommendation", "")
    
    system_context = f"""You are an expert AI Career Advisor embedded inside a Resume Analysis platform.
You have just finished analyzing the candidate's resume and here are their results:

- ATS Compatibility Score: {score}%
- Matched Skills: {matched}
- Missing Skills: {missing}
- Overall Recommendation: {recommendation}

Your job is to be a conversational coach. Answer the user's questions with specific, actionable advice.
Reference their actual score, matched skills, and missing skills when relevant.
Be encouraging but honest. Keep answers concise and helpful.
"""

    # Build the full conversation for Gemini
    full_prompt = system_context + "\n\n--- Conversation so far ---\n"
    for msg in chat_history:
        role_label = "Candidate" if msg["role"] == "user" else "Career Advisor"
        full_prompt += f"\n{role_label}: {msg['content']}"
    full_prompt += f"\n\nCandidate: {user_message}\n\nCareer Advisor:"
    
    try:
        response = call_gemini_with_retry(model, full_prompt)
        return response.text.strip()
    except Exception:
        return "I'm sorry, I'm currently backed up with requests! Please wait a moment and try again."
