import streamlit as st
import json
import urllib.parse
import streamlit.components.v1 as components
from database import (
    init_db, create_user, authenticate_user, 
    create_job, get_recruiter_jobs, get_job_applications,
    get_all_open_jobs, submit_application
)
from ai_engine import extract_text_from_pdf, analyze_resume_ats, analyze_resume_general, career_chat_response

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Resume Analyzer & ATS",
    page_icon="🤖",
    layout="wide"
)

# --- Session State Initialization ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = None
if 'current_analysis_job_id' not in st.session_state:
    st.session_state.current_analysis_job_id = None
if 'current_resume_text' not in st.session_state:
    st.session_state.current_resume_text = None
if 'landing_choice' not in st.session_state:
    st.session_state.landing_choice = 'home' # Default to home
if 'is_dark_theme' not in st.session_state:
    st.session_state.is_dark_theme = False
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'chat_context' not in st.session_state:
    st.session_state.chat_context = None
if 'current_general_analysis' not in st.session_state:
    st.session_state.current_general_analysis = None

def logout():
    """Clears the session state and logs the user out."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.landing_choice = 'home'
    st.session_state.is_dark_theme = False
    st.rerun()

def go_home():
    """Returns to the main landing page"""
    st.session_state.landing_choice = 'home'
    st.rerun()

# --- Recruiter Portal ---
def render_recruiter_portal():
    st.title(f"Employer Portal")
    st.write(f"Welcome back, **{st.session_state.username}**!")
    
    tab1, tab2, tab3 = st.tabs(["Active Jobs", "Post a New Job", "Evaluate Candidates"])
    
    with tab1:
        st.subheader("Your Job Postings")
        jobs = get_recruiter_jobs(st.session_state.user_id)
        if not jobs:
            st.info("You haven't posted any jobs yet. Go to the 'Post a New Job' tab to get started.")
        else:
            for job in jobs:
                # job tuple: (id, title, status, created_at)
                with st.container(border=True):
                    st.write(f"### {job[1]}")
                    col1, col2 = st.columns(2)
                    col1.metric("Status", job[2].capitalize())
                    col2.metric("Posted On", job[3].split()[0])
    
    with tab2:
        st.subheader("Create a New Job Description")
        with st.form("new_job_form"):
            job_title = st.text_input("Job Title", placeholder="e.g. Junior Python Developer")
            experience = st.selectbox("Required Experience", ["Entry Level", "1-3 Years", "3-5 Years", "Senior"])
            skills = st.text_area("Required Skills (Comma separated)", placeholder="Python, FastAPI, Docker, Communication")
            description = st.text_area("Full Job Description / Extra Criteria", height=150)
            
            submitted = st.form_submit_button("Post Job", type="primary")
            if submitted:
                if job_title and skills and description:
                    create_job(st.session_state.user_id, job_title, description, skills, experience)
                    st.success("Job Posted Successfully!")
                    st.rerun()
                else:
                    st.error("Please fill out all fields.")

    with tab3:
        st.subheader("Review Candidate Applications")
        jobs = get_recruiter_jobs(st.session_state.user_id)
        if not jobs:
            st.warning("You need to post a job before you can review applicants.")
        else:
            job_dict = {f"{j[1]} (ID: {j[0]})": j[0] for j in jobs}
            selected_job = st.selectbox("Select a Job to view applicants:", list(job_dict.keys()))
            
            if selected_job:
                job_id = job_dict[selected_job]
                applicants = get_job_applications(job_id)
                
                if not applicants:
                    st.info("No candidates have applied for this job yet.")
                else:
                    st.write(f"Showing **{len(applicants)}** candidates sorted by ATS Match Score.")
                    for app in applicants:
                        # app tuple: (id, username, ats_score, applied_at, ai_analysis_json)
                        score = app[2]
                        # Color coding the score
                        score_color = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
                        
                        with st.expander(f"{score_color} {app[1]} - Match: {score}%"):
                            st.write(f"**Applied on:** {app[3].split()[0]}")
                            try:
                                analysis = json.loads(app[4])
                                st.write("### AI Analysis Summary")
                                st.write(analysis.get("recommendation", "No summary provided."))
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write("**✅ Matched Skills**")
                                    for skill in analysis.get("matching_skills", []):
                                        st.write(f"- {skill}")
                                with col2:
                                    st.write("**❌ Missing Skills**")
                                    for skill in analysis.get("missing_skills", []):
                                        st.write(f"- {skill}")
                            except Exception:
                                st.error("Failed to parse detailed AI analysis for this candidate.")

# --- Candidate Portal ---
def render_candidate_portal():
    st.title(f"Applicant Portal")
    st.write(f"Welcome back, **{st.session_state.username}**!")
    
    st.subheader("Open Job Postings")
    jobs = get_all_open_jobs()
    
    if not jobs:
        st.info("There are currently no open jobs. Please check back later.")
        return
        
    job_dict = {f"{j[1]} - {j[5]} (ID: {j[0]})": j for j in jobs}
    selected_job_key = st.selectbox("Select a Job to view details and apply:", ["-- Select a Job --"] + list(job_dict.keys()))
    
    if selected_job_key != "-- Select a Job --":
        # j tuple: (id, title, description, required_skills, experience_level, recruiter_name, created_at)
        job = job_dict[selected_job_key]
        
        # Reset the temporary session state if the user clicks on a different job
        job_id = job[0]
        if st.session_state.current_analysis_job_id != job_id:
            st.session_state.current_analysis = None
            st.session_state.current_analysis_job_id = job_id
            st.session_state.current_resume_text = None

        with st.container(border=True):
            st.write(f"### {job[1]}")
            st.write(f"**Posted By:** {job[5]} | **Experience Needed:** {job[4]}")
            st.write(f"**Required Skills:** {job[3]}")
            with st.expander("View Full Job Description"):
                st.write(job[2])
                
            st.markdown("---")
            st.write("#### 1️⃣ Upload and Analyze Your Resume")
            st.write("Find out your ATS compatibility score before deciding to apply.")
            uploaded_file = st.file_uploader("Upload your Resume (PDF only)", type=["pdf"])
            
            if uploaded_file is not None:
                if st.button("Analyze Resume", type="primary"):
                    with st.spinner("Analyzing resume using Gemini AI... This may take a few seconds."):
                        try:
                            # 1. Extract Text
                            resume_text = extract_text_from_pdf(uploaded_file)
                            
                            # 2. Prepare JD context for the AI
                            jd_context = f"Title: {job[1]}\nSkills: {job[3]}\nExperience: {job[4]}\nDescription: {job[2]}"
                            
                            # 3. Get AI Analysis
                            analysis = analyze_resume_ats(resume_text, jd_context)
                            
                            if not analysis:
                                st.error("The AI engine failed to analyze the document. Please try again.")
                                return
                            
                            # 4. Save to temporary Session State + seed the chatbot
                            st.session_state.current_analysis = analysis
                            st.session_state.current_resume_text = resume_text
                            # Reset chat and seed a welcome message from the AI
                            st.session_state.chat_context = analysis
                            st.session_state.chat_messages = [{
                                "role": "assistant",
                                "content": f"Hi! I've finished analyzing your resume. Your ATS Score is **{analysis.get('ats_score', 0)}%**. I'm your personal Career Advisor — ask me anything about your results, how to improve, or what to learn next! 🚀"
                            }]
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"An error occurred while processing your file: {e}")

            # If an analysis exists for this job, Display IT and present the APPLY button
            if st.session_state.current_analysis is not None:
                analysis = st.session_state.current_analysis
                ats_score = analysis.get("ats_score", 0)
                
                # 5. Display the Results Overview
                st.markdown("## 📊 Your ATS Analysis Report")
                
                # Score Ring + Feedback side by side
                col1, col2 = st.columns([1, 2])
                with col1:
                    # Determine ring color based on score
                    if ats_score >= 75:
                        ring_color = "#22c55e"   # green
                        status_label = "Strong Match ✅"
                    elif ats_score >= 50:
                        ring_color = "#f59e0b"   # amber
                        status_label = "Partial Match ⚠️"
                    else:
                        ring_color = "#ef4444"   # red
                        status_label = "Weak Match ❌"
                    
                    # SVG circular ring math
                    radius = 54
                    circumference = 2 * 3.14159 * radius
                    filled = circumference * (ats_score / 100)
                    gap = circumference - filled

                    st.markdown(f"""
                        <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; padding: 10px;">
                            <svg width="140" height="140" viewBox="0 0 140 140">
                                <!-- Background ring -->
                                <circle cx="70" cy="70" r="{radius}" fill="none" stroke="#e2e8f0" stroke-width="12"/>
                                <!-- Score ring -->
                                <circle cx="70" cy="70" r="{radius}" fill="none"
                                    stroke="{ring_color}" stroke-width="12"
                                    stroke-dasharray="{filled:.1f} {gap:.1f}"
                                    stroke-linecap="round"
                                    transform="rotate(-90 70 70)"/>
                                <!-- Score text -->
                                <text x="70" y="65" text-anchor="middle"
                                    font-size="26" font-weight="bold" fill="{ring_color}">{ats_score}%</text>
                                <text x="70" y="85" text-anchor="middle"
                                    font-size="11" fill="#64748b">ATS Score</text>
                            </svg>
                            <p style="margin-top:8px; font-weight:600; color:{ring_color}; font-size:0.95rem;">{status_label}</p>
                        </div>
                    """, unsafe_allow_html=True)
                with col2:
                    st.write("**Feedback Summary**")
                    st.info(analysis.get("recommendation", "No summary provided."))
                
                # Skills Comparison
                st.write("### 🛠️ Skills Comparison")
                s_col1, s_col2 = st.columns(2)
                with s_col1:
                    st.success("**✅ Matched Skills**")
                    for skill in analysis.get("matching_skills", []):
                        st.write(f"- {skill}")
                with s_col2:
                    st.error("**❌ Missing Skills**")
                    for skill in analysis.get("missing_skills", []):
                        st.write(f"- {skill}")
                        
                # Alternative Roles
                st.write("### 🎯 Suggested Alternative Roles")
                st.write("Based on your resume, you might also be a good fit for:")
                for role in analysis.get("suggested_job_roles", []):
                    st.write(f"- **{role}**")
                    
                # Course Recommendations
                courses = analysis.get("course_recommendations", [])
                if courses:
                    st.write("### 📚 How to Improve (Course Recommendations)")
                    st.write("Consider taking these courses to fill the gaps in your resume for this specific role:")
                    for course in courses:
                        with st.container(border=True):
                            st.write(f"**Missing Skill:** {course.get('skill', 'Unknown')}")
                            course_link = course.get('link', '#')
                            st.markdown(f"[{course.get('course_name', 'Course Link')}]({course_link}) on {course.get('platform', 'the web')}")

                st.markdown("---")
                st.write("#### 2️⃣ Submit Application")
                st.write("Are you happy with this match? Submit your application to the recruiter below.")
                
                if st.button("Confirm & Apply for this Job", type="primary", use_container_width=True):
                    # Save to Database
                    json_data = json.dumps(analysis)
                    success = submit_application(job_id, st.session_state.user_id, st.session_state.current_resume_text, ats_score, json_data)
                    
                    if success:
                        st.success("🎉 Application Submitted Successfully! The recruiter can now view your resume.")
                    else:
                        st.warning("You have already applied for this job! You cannot apply twice.")

                # --- 💬 Career Assistant Chatbot ---
                st.markdown("---")
                st.write("### 💬 Career Assistant")
                st.write("Ask me anything about your results, how to improve, or which skills to learn next!")

                # Display existing chat messages
                for msg in st.session_state.chat_messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                
                # Chat input
                user_input = st.chat_input("Ask your Career Advisor...")
                if user_input:
                    # Show user message immediately
                    st.session_state.chat_messages.append({"role": "user", "content": user_input})
                    with st.chat_message("user"):
                        st.markdown(user_input)
                    
                    # Get AI response
                    with st.chat_message("assistant"):
                        with st.spinner("Thinking..."):
                            try:
                                response = career_chat_response(
                                    analysis_context=st.session_state.chat_context or {},
                                    chat_history=st.session_state.chat_messages[:-1],  # All but the message we just added
                                    user_message=user_input
                                )
                                st.markdown(response)
                                st.session_state.chat_messages.append({"role": "assistant", "content": response})
                            except Exception as e:
                                st.error(f"Chatbot error: {e}")


# --- Authentication UI (Login / Signup) ---
def render_auth_page():
    st.title("Welcome to the AI Resume Analyzer & ATS 📄🚀")
    st.write("Log in to upload your resume or post a job description.")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to your account")
        login_username = st.text_input("Username", key="log_user")
        login_password = st.text_input("Password", type="password", key="log_pass")
        
        if st.button("Login"):
            user = authenticate_user(login_username, login_password)
            if user:
                # user tuple: (id, username, password, role)
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.session_state.role = user[3]
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid username or password.")
                
    with tab2:
        st.subheader("Create a new account")
        reg_username = st.text_input("Choose a Username", key="reg_user")
        reg_password = st.text_input("Choose a Password", type="password", key="reg_pass")
        reg_role = st.selectbox("I am a...", ["candidate", "recruiter"])
        
        if st.button("Sign Up", type="primary"):
            if len(reg_username) < 3 or len(reg_password) < 5:
                st.warning("Username must be at least 3 characters and password at least 5.")
            else:
                success = create_user(reg_username, reg_password, reg_role)
                if success:
                    st.success("Account created successfully! Please log in above.")
                else:
                    st.error("Username already exists. Please choose a different one.")

# --- Landing Page (Bento Grid) ---
def render_landing_page():
    # Step 1: Inject the CSS separately so Streamlit renders it properly
    st.markdown("""
    <style>
    .bento-grid {
        display: grid;
        grid-template-columns: 2fr 1fr;
        grid-template-rows: auto auto;
        gap: 18px;
        padding: 10px 0 24px 0;
    }
    .bento-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 20px;
        padding: 28px 32px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06);
        transition: transform 0.25s ease, box-shadow 0.25s ease;
        color: #e8eaf6 !important;
    }
    .bento-card * { color: #e8eaf6 !important; }
    .bento-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 16px 48px rgba(99,70,255,0.22), inset 0 1px 0 rgba(255,255,255,0.09);
    }
    .bento-hero { grid-column: 1; grid-row: 1; }
    .bento-side1 { grid-column: 2; grid-row: 1; }
    .bento-wide {
        grid-column: 1 / -1; grid-row: 2;
        background: linear-gradient(135deg, rgba(99,102,241,0.12), rgba(167,139,250,0.07));
    }
    .bento-tag {
        display: inline-block;
        background: rgba(99,102,241,0.25);
        color: #a5b4fc !important;
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 14px;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        border: 1px solid rgba(99,102,241,0.35);
    }
    .bento-title { font-size: 1.8rem; font-weight: 700; margin: 0 0 10px 0; line-height: 1.25; color: #e8eaf6 !important; }
    .bento-sub { font-size: 0.92rem; color: #94a3b8 !important; line-height: 1.6; margin: 0; }
    .bento-icon { font-size: 2.4rem; margin-bottom: 12px; }
    .bento-stat { font-size: 2.6rem; font-weight: 800; color: #a78bfa !important; display: block;
        text-shadow: 0 0 20px rgba(167,139,250,0.4); }
    .bento-stat-label { font-size: 0.82rem; color: #64748b !important; margin-top: 4px; display: block; }
    </style>
    """, unsafe_allow_html=True)

    # Step 2: Inject the bento grid HTML
    # Theme-aware colors for the isolated iframe
    is_dark = st.session_state.is_dark_theme
    card_bg     = "rgba(255,255,255,0.06)" if is_dark else "rgba(255,255,255,0.75)"
    card_border = "rgba(255,255,255,0.10)" if is_dark else "rgba(139,92,246,0.25)"
    card_shadow = "0 8px 32px rgba(0,0,0,0.35)" if is_dark else "0 4px 20px rgba(139,92,246,0.10)"
    text_main   = "#e8eaf6" if is_dark else "#0f172a"
    text_sub    = "#94a3b8" if is_dark else "#475569"
    tag_bg      = "rgba(99,102,241,0.25)" if is_dark else "rgba(139,92,246,0.12)"
    tag_color   = "#a5b4fc" if is_dark else "#6d28d9"
    tag_border  = "rgba(99,102,241,0.35)" if is_dark else "rgba(139,92,246,0.30)"
    wide_bg     = "linear-gradient(135deg,rgba(99,102,241,0.12),rgba(167,139,250,0.07))" if is_dark else "linear-gradient(135deg,rgba(139,92,246,0.06),rgba(6,182,212,0.05))"
    stat_color  = "#a78bfa" if is_dark else "#7c3aed"
    stat_shadow = "0 0 18px rgba(167,139,250,0.5)" if is_dark else "none"
    stat_label  = "#64748b" if is_dark else "#6b7280"
    hover_shadow= "0 16px 48px rgba(99,70,255,0.22)" if is_dark else "0 12px 32px rgba(139,92,246,0.18)"

    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        body {{ margin: 0; padding: 0; background: transparent; font-family: 'Inter','Segoe UI',sans-serif; }}
        .bento-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
            padding: 8px 0 20px 0;
        }}
        .bento-card {{
            background: {card_bg};
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid {card_border};
            border-radius: 20px;
            padding: 28px 30px;
            box-shadow: {card_shadow};
            transition: transform 0.25s ease, box-shadow 0.25s ease;
            box-sizing: border-box;
        }}
        .bento-card:hover {{
            transform: translateY(-3px);
            box-shadow: {hover_shadow};
        }}
        .bento-wide {{
            grid-column: 1 / -1;
            background: {wide_bg};
        }}
        .bento-tag {{
            display: inline-block;
            background: {tag_bg};
            color: {tag_color};
            border-radius: 20px;
            padding: 4px 14px;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 14px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            border: 1px solid {tag_border};
        }}
        h1.bento-title {{ font-size:1.75rem; font-weight:700; margin:0 0 10px 0; line-height:1.25; color:{text_main}; }}
        h3.bento-title {{ font-size:1.1rem; font-weight:600; margin:8px 0 8px 0; color:{text_main}; }}
        p.bento-sub    {{ font-size:0.9rem; color:{text_sub}; line-height:1.6; margin:0; }}
        .bento-icon    {{ font-size:2.2rem; margin-bottom:10px; }}
        .stat-grid     {{ display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:16px; align-items:start; }}
        .bento-stat    {{ font-size:2.2rem; font-weight:800; color:{stat_color}; display:block; text-shadow:{stat_shadow}; }}
        .bento-stat-label {{ font-size:0.8rem; color:{stat_label}; margin-top:4px; display:block; }}
    </style>
    </head>
    <body>
        <div class="bento-grid">
            <div class="bento-card">
                <span class="bento-tag">&#10022; AI-Powered Platform</span>
                <h1 class="bento-title">The Next-Gen<br>Recruitment Intelligence</h1>
                <p class="bento-sub">Semantic AI that understands context, not just keywords. Connect the world's top talent to the right roles &mdash; instantly.</p>
            </div>
            <div class="bento-card">
                <div class="bento-icon">&#127919;</div>
                <span class="bento-tag">Guest Access</span>
                <h3 class="bento-title">Job Matcher</h3>
                <p class="bento-sub">Upload a resume &mdash; get your Top 5 career match roles with accuracy scores. No login required.</p>
            </div>
            <div class="bento-card bento-wide">
                <div class="stat-grid">
                    <div>
                        <span class="bento-stat">&#129302;</span>
                        <span class="bento-stat-label">Gemini 2.5 Flash AI scores every resume semantically</span>
                    </div>
                    <div>
                        <span class="bento-stat">2-in-1</span>
                        <span class="bento-stat-label">Candidate &amp; Recruiter portals in one platform</span>
                    </div>
                    <div>
                        <span class="bento-stat">&#128218;</span>
                        <span class="bento-stat-label">Coursera &amp; Udemy course links per skill gap</span>
                    </div>
                    <div>
                        <span class="bento-stat">&#128172;</span>
                        <span class="bento-stat-label">Context-aware Career Advisor chatbot included</span>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """, height=420, scrolling=False)

    # Step 3: Action buttons below the grid
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎯 Get Job Recommendations (No Login)", use_container_width=True):
            st.session_state.landing_choice = 'recommend'
            st.rerun()
    with col2:
        if st.button("🏢 Go to Recruitment Portal", type="primary", use_container_width=True):
            st.session_state.landing_choice = 'apply'
            st.rerun()


def render_job_recommendation_tool():
    st.title("🎯 AI Job Recommendation Engine")
    st.write("Upload your resume below. Our AI will analyze your skills and suggest the top 5 roles you should be applying for!")
    
    uploaded_file = st.file_uploader("Upload your Resume (PDF only)", type=["pdf"])
    if uploaded_file is not None:
        if st.button("Generate My Job Matches!", type="primary"):
            with st.spinner("Analyzing your profile..."):
                try:
                    resume_text = extract_text_from_pdf(uploaded_file)
                    analysis = analyze_resume_general(resume_text)
                    
                    if not analysis:
                        st.error("Failed to generate recommendations. Please try again.")
                        return
                    
                    st.session_state.current_general_analysis = analysis
                    st.rerun()
                        
                except Exception as e:
                    st.error(f"Error analyzing your resume: {e}")

    # Display results if they exist in session state
    if st.session_state.current_general_analysis:
        analysis = st.session_state.current_general_analysis
        st.success("Analysis Complete!")
        st.markdown("---")
        
        st.write("### 👤 Candidate Profile Summary")
        st.info(analysis.get("profile_summary", "No summary provided."))
        
        st.write("### 🏆 Top Recommended Roles")
        roles = analysis.get("recommended_roles", [])
        if roles:
            for role_data in roles:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    role_name = role_data.get('role', 'Unknown Role')
                    match_pct = role_data.get('match_percentage', 0)
                    reason = role_data.get('reason', 'Great fit based on experience.')
                    
                    with col1:
                        st.write(f"#### {role_name}")
                        st.write(f"*{reason}*")
                        progress_val = max(0.0, min(1.0, match_pct / 100.0))
                        st.progress(progress_val)
                        
                        # Generate Job Search Links
                        encoded_role = urllib.parse.quote(role_name)
                        naukri_link = f"https://www.naukri.com/{encoded_role.replace('%20', '-')}-jobs"
                        glassdoor_link = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={encoded_role}"
                        
                        st.markdown(f"**🔍 Find Vacancies:** [Search on Naukri]({naukri_link}) | [Search on Glassdoor]({glassdoor_link})")
                        
                    with col2:
                        st.metric("Match Score", f"{match_pct}%")
        else:
            st.warning("No roles were suggested by the AI.")

# --- Glassmorphism Bento Theming Engine ---
def apply_enterprise_theme():
    """Injects glassmorphism + bento grid CSS."""
    if st.session_state.is_dark_theme:
        css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

            /* === DARK GLASSMORPHISM === */
            html, body, .stApp {
                font-family: 'Inter', sans-serif !important;
                background-color: #080812 !important;
                background-image:
                    radial-gradient(ellipse at 15% 30%, rgba(99, 70, 255, 0.25) 0%, transparent 55%),
                    radial-gradient(ellipse at 85% 70%, rgba(20, 160, 230, 0.2) 0%, transparent 55%),
                    radial-gradient(ellipse at 50% 100%, rgba(160, 30, 200, 0.15) 0%, transparent 50%);
            }

            /* All text in off-white */
            .stApp p, .stApp span, .stApp label, .stApp li,
            .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
            [data-testid="stMarkdownContainer"] *,
            [data-testid="stWidgetLabel"] *,
            [data-testid="stMetricLabel"] *,
            [data-testid="stTabsListContainer"] button,
            [data-testid="stExpander"] *,
            .stSelectbox label, .stTextInput label,
            .stTextArea label, .stFileUploader label,
            div[data-baseweb="tab"] span { color: #e8eaf6 !important; }

            /* Glassmorphism sidebar */
            .stSidebar {
                background: rgba(15, 12, 35, 0.75) !important;
                backdrop-filter: blur(20px) !important;
                -webkit-backdrop-filter: blur(20px) !important;
                border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
                box-shadow: 4px 0 40px rgba(0, 0, 0, 0.4);
            }
            .stSidebar * { color: #c5cae9 !important; }

            /* Header bar */
            [data-testid="stHeader"] {
                background: rgba(8, 8, 18, 0.85) !important;
                backdrop-filter: blur(12px) !important;
                border-bottom: 1px solid rgba(255,255,255,0.06);
            }

            /* Frosted glass ALL containers & expanders */
            [data-testid="stExpander"],
            div[data-testid="stVerticalBlockBorderWrapper"] {
                background: rgba(255, 255, 255, 0.04) !important;
                backdrop-filter: blur(16px) !important;
                -webkit-backdrop-filter: blur(16px) !important;
                border: 1px solid rgba(255, 255, 255, 0.1) !important;
                border-radius: 16px !important;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.05);
                transition: box-shadow 0.3s ease, transform 0.2s ease;
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:hover {
                box-shadow: 0 12px 40px rgba(100, 50, 255, 0.2), inset 0 1px 0 rgba(255,255,255,0.08);
                transform: translateY(-2px);
            }

            /* Neon violet metric values */
            div[data-testid="stMetricValue"] {
                color: #a78bfa !important;
                font-size: 2.2rem !important;
                font-weight: 700;
                text-shadow: 0 0 20px rgba(167, 139, 250, 0.5);
            }

            /* Progress bars */
            div[data-testid="stDecoration"] {
                background: linear-gradient(90deg, #6366f1, #a78bfa) !important;
            }

            /* Glowing buttons */
            .stButton > button {
                background: rgba(99, 102, 241, 0.15) !important;
                border: 1px solid rgba(99, 102, 241, 0.4) !important;
                border-radius: 10px !important;
                color: #c4b5fd !important;
                font-weight: 500;
                transition: all 0.25s ease;
                box-shadow: 0 0 0 rgba(99, 102, 241, 0);
            }
            .stButton > button:hover {
                background: rgba(99, 102, 241, 0.3) !important;
                border-color: #818cf8 !important;
                box-shadow: 0 0 20px rgba(99, 102, 241, 0.35) !important;
                color: #e0e7ff !important;
                transform: translateY(-1px);
            }
            .stButton > button[kind="primary"] {
                background: linear-gradient(135deg, rgba(99,102,241,0.6), rgba(167,139,250,0.5)) !important;
                border-color: rgba(167,139,250,0.6) !important;
            }

            /* Tab pills */
            div[data-baseweb="tab"] {
                border-radius: 8px;
                transition: background 0.2s;
            }
        </style>
        """
    else:
        css = """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

            /* === LIGHT: Electric Glassmorphism === */
            html, body, .stApp {
                font-family: 'Inter', sans-serif !important;
                background-color: #f0f4ff !important;
                background-image: radial-gradient(ellipse at 10% 20%, rgba(139, 92, 246, 0.08) 0%, transparent 50%),
                                  radial-gradient(ellipse at 90% 80%, rgba(6, 182, 212, 0.08) 0%, transparent 50%);
            }

            /* All main text: deep navy */
            .stApp p, .stApp span, .stApp label, .stApp li,
            .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
            [data-testid="stMarkdownContainer"] p,
            [data-testid="stMarkdownContainer"] li,
            [data-testid="stMarkdownContainer"] span,
            [data-testid="stWidgetLabel"] p,
            [data-testid="stWidgetLabel"] span,
            [data-testid="stMetricLabel"] p,
            [data-testid="stTabsListContainer"] button,
            [data-testid="stExpander"] p,
            [data-testid="stExpander"] summary,
            .stSelectbox label, .stTextInput label,
            .stTextArea label, .stFileUploader label,
            div[data-baseweb="tab"] span { color: #0f172a !important; }

            /* Sidebar: glossy white with violet left border */
            .stSidebar {
                background: rgba(255, 255, 255, 0.85) !important;
                backdrop-filter: blur(12px);
                border-right: 2px solid rgba(139, 92, 246, 0.3) !important;
                box-shadow: 4px 0 15px rgba(139, 92, 246, 0.08);
            }
            .stSidebar * { color: #1e1b4b !important; }

            [data-testid="stHeader"] {
                background-color: rgba(240, 244, 255, 0.95) !important;
                border-bottom: 1px solid rgba(139, 92, 246, 0.15);
            }

            [data-testid="stExpander"],
            div[data-testid="stVerticalBlockBorderWrapper"] {
                background-color: rgba(255, 255, 255, 0.85) !important;
                border: 1px solid rgba(139, 92, 246, 0.2) !important;
                border-radius: 14px !important;
                box-shadow: 0 2px 12px rgba(139, 92, 246, 0.07);
            }

            div[data-testid="stMetricValue"] {
                color: #7c3aed !important;
                font-size: 2rem !important;
                font-weight: 700;
            }

            .stButton > button {
                border: 1px solid rgba(139, 92, 246, 0.3) !important;
                border-radius: 10px !important;
                transition: all 0.2s ease;
            }
            .stButton > button:hover {
                box-shadow: 0 0 12px rgba(139, 92, 246, 0.2) !important;
                border-color: #7c3aed !important;
            }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)


# --- Main Application Router ---
def main():
    # Ensure database is set up
    init_db()
    
    # 1. Apply Styles
    apply_enterprise_theme()
    
    # 2. Build Top Global Controls
    toggle_col1, toggle_col2 = st.columns([10, 2])
    with toggle_col2:
        label = "🌙 Dark" if st.session_state.is_dark_theme else "☀️ Light"
        new_theme = st.toggle(label, value=st.session_state.is_dark_theme, key="theme_toggle")
        if new_theme != st.session_state.is_dark_theme:
            st.session_state.is_dark_theme = new_theme
            st.rerun()

    # 3. Build Sidebar Navigation
    with st.sidebar:
        st.title("🧭 Navigation")
        if st.button("🏠 Home Dashboard", use_container_width=True):
            st.session_state.landing_choice = 'home'
            st.rerun()
            
        if st.button("🎯 General Job Matcher", use_container_width=True):
            st.session_state.landing_choice = 'recommend'
            st.rerun()
            
        st.markdown("---")
        
        if st.session_state.user_id is None:
            if st.button("🔐 Login / Register", type="primary", use_container_width=True):
                st.session_state.landing_choice = 'apply'
                st.rerun()
        else:
            if st.button("🏢 My ATS Portal", type="primary", use_container_width=True):
                st.session_state.landing_choice = 'apply'
                st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)
            st.button("⚙️ Logout safely", on_click=logout, use_container_width=True)


    # 4. Route views based on Sidebar state
    choice = st.session_state.get('landing_choice')

    if choice == 'apply':
        if st.session_state.user_id is not None:
            if st.session_state.role == 'recruiter':
                render_recruiter_portal()
            elif st.session_state.role == 'candidate':
                render_candidate_portal()
        else:
            render_auth_page()
    elif choice == 'recommend':
        render_job_recommendation_tool()
    else:
        render_landing_page()

if __name__ == "__main__":
    main()

