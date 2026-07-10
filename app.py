# -*- coding: utf-8 -*-
import streamlit as st
import datetime
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from auth import get_iam_token
from agent import chat_with_agent

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="AI Interview Coach",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────
st.markdown(
    """
    <style>
    .stApp { background-color: #f7f8fa; }

    .thread-badge {
        font-size: 11px; color: #57606a; font-family: monospace;
    }
    .profile-badge {
        display: inline-block;
        background: #dcfce7; color: #166534;
        border: 1px solid #bbf7d0; border-radius: 20px;
        padding: 3px 12px; font-size: 12px; font-weight: 600; margin-top: 4px;
    }
    .star-card {
        background: #ffffff; border: 1px solid #e5e7eb;
        border-left: 4px solid #3b82d4; border-radius: 0 8px 8px 0;
        padding: 16px 20px; margin-top: 12px;
    }
    .empty-state {
        text-align: center; padding: 48px 24px 32px; color: #57606a;
    }
    .empty-state h3 { font-size: 18px; color: #1f2328; margin-bottom: 8px; }
    .empty-state p  { font-size: 13px; margin-bottom: 24px; }

    /* Readiness score */
    .readiness-wrap {
        background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px;
        padding: 20px 24px; margin-bottom: 8px; text-align: center;
    }
    .readiness-score {
        font-size: 52px; font-weight: 800; line-height: 1;
        color: #3b82d4;
    }
    .readiness-label { font-size: 13px; color: #57606a; margin-top: 4px; }

    /* Next steps card */
    .next-card {
        background: #eff6ff; border: 1px solid #bfdbfe;
        border-left: 4px solid #3b82d4; border-radius: 0 8px 8px 0;
        padding: 14px 18px; margin-top: 8px;
    }
    .next-card h4 { font-size: 14px; margin-bottom: 6px; color: #1e40af; }
    .next-card ul { margin: 0; padding-left: 18px; font-size: 13px; color: #1f2328; }
    .next-card li { margin-bottom: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# Constants – topic detection keywords
# ─────────────────────────────────────────
TOPIC_KEYWORDS = {
    "Data Structures & Algorithms": ["array", "linked list", "tree", "graph", "dsa", "algorithm",
                                      "sorting", "binary search", "stack", "queue", "heap", "dynamic programming"],
    "System Design":                ["system design", "hld", "lld", "scalability", "microservice",
                                      "load balancer", "cache", "database design", "api design"],
    "Behavioural / HR":             ["tell me about", "strength", "weakness", "conflict", "teamwork",
                                      "leadership", "challenge", "hr", "behavioural", "star method",
                                      "situation", "action", "result"],
    "SQL & Databases":              ["sql", "join", "query", "database", "rdbms", "nosql",
                                      "aggregation", "index", "transaction"],
    "Python / Programming":         ["python", "java", "c++", "oop", "class", "function",
                                      "recursion", "lambda", "coding"],
    "Cloud & DevOps":               ["docker", "kubernetes", "cloud", "aws", "azure", "gcp",
                                      "ci/cd", "devops", "container", "deployment"],
}

ALL_TOPICS = list(TOPIC_KEYWORDS.keys())

SESSIONS_FILE = os.path.join(os.path.dirname(__file__), "sessions.json")

# ─────────────────────────────────────────
# Session persistence helpers
# ─────────────────────────────────────────
def load_sessions() -> list:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return []


def save_session_record(record: dict):
    sessions = load_sessions()
    sessions.append(record)
    # Keep last 50 sessions only
    sessions = sessions[-50:]
    try:
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(sessions, f, indent=2, default=str)
    except OSError:
        pass


# ─────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────
def init_session():
    defaults = {
        "thread_id":             None,
        "messages":              [],
        "feedback_response":     "",
        "token_cache":           None,
        "token_expiry":          None,
        "starter_prompt":        None,
        "session_start":         datetime.datetime.utcnow(),
        "session_saved":         False,
        # profile
        "profile_name":          "",
        "profile_job_title":     "Software Engineer",
        "profile_experience":    "Fresher",
        "profile_target_company":"",
        "profile_saved_at":      None,
        # topic checkboxes – keyed by topic name
        "topics_done":           {t: False for t in ALL_TOPICS},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()


# ─────────────────────────────────────────
# Helper: expire profile after 30 minutes
# ─────────────────────────────────────────
def _maybe_expire_profile():
    saved = st.session_state.profile_saved_at
    if saved and (datetime.datetime.utcnow() - saved).total_seconds() > 1800:
        st.session_state.profile_name           = ""
        st.session_state.profile_job_title      = "Software Engineer"
        st.session_state.profile_experience     = "Fresher"
        st.session_state.profile_target_company = ""
        st.session_state.profile_saved_at       = None

_maybe_expire_profile()


# ─────────────────────────────────────────
# Helper: detect covered topics from chat
# ─────────────────────────────────────────
def detect_covered_topics() -> dict[str, bool]:
    all_text = " ".join(
        m["content"].lower() for m in st.session_state.messages
    )
    covered = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        covered[topic] = any(kw in all_text for kw in keywords)
    return covered


# ─────────────────────────────────────────
# Helper: compute readiness score (0–100)
# ─────────────────────────────────────────
def compute_readiness() -> int:
    msgs        = st.session_state.messages
    user_msgs   = [m for m in msgs if m["role"] == "user"]
    agent_msgs  = [m for m in msgs if m["role"] == "assistant"]
    covered     = detect_covered_topics()

    topic_score   = int((sum(covered.values()) / len(ALL_TOPICS)) * 40)   # 40 pts
    volume_score  = min(len(user_msgs) * 3, 30)                            # 30 pts (10 msgs = full)
    depth_score   = min(
        int(sum(len(m["content"]) for m in agent_msgs) / 500) * 5, 30
    )                                                                       # 30 pts

    return min(topic_score + volume_score + depth_score, 100)


# ─────────────────────────────────────────
# Helper: save session on end / new chat
# ─────────────────────────────────────────
def _save_current_session():
    msgs = st.session_state.messages
    if msgs and not st.session_state.session_saved:
        record = {
            "timestamp":  datetime.datetime.utcnow().isoformat(),
            "profile":    st.session_state.profile_name or "Anonymous",
            "job_title":  st.session_state.profile_job_title,
            "messages":   len(msgs),
            "readiness":  compute_readiness(),
            "topics":     [t for t, v in detect_covered_topics().items() if v],
        }
        save_session_record(record)
        st.session_state.session_saved = True


# ─────────────────────────────────────────
# Sidebar – Candidate Profile
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<h1 style='font-size:22px;margin-bottom:0'>🤖 AI Interview Coach</h1>"
        "<p style='font-size:12px;color:#57606a;margin-top:2px'>Powered by watsonx Orchestrate</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    st.subheader("Candidate Profile")

    job_titles        = ["Software Engineer", "Data Scientist", "Project Manager", "HR Executive"]
    experience_levels = ["Fresher", "Mid-level", "Senior"]

    name = st.text_input(
        "Your Name", value=st.session_state.profile_name, placeholder="e.g. Alex Johnson"
    )
    job_title = st.selectbox(
        "Job Title", job_titles,
        index=job_titles.index(st.session_state.profile_job_title),
    )
    experience = st.selectbox(
        "Experience Level", experience_levels,
        index=experience_levels.index(st.session_state.profile_experience),
    )
    target_company = st.text_input(
        "Target Company", value=st.session_state.profile_target_company,
        placeholder="e.g. Google"
    )

    if (
        name != st.session_state.profile_name
        or job_title != st.session_state.profile_job_title
        or experience != st.session_state.profile_experience
        or target_company != st.session_state.profile_target_company
    ):
        st.session_state.profile_name           = name
        st.session_state.profile_job_title      = job_title
        st.session_state.profile_experience     = experience
        st.session_state.profile_target_company = target_company
        st.session_state.profile_saved_at       = datetime.datetime.utcnow()

    if name and target_company:
        st.markdown(
            f'<span class="profile-badge">✓ {name} · {job_title} · {target_company}</span>',
            unsafe_allow_html=True,
        )
    elif st.session_state.profile_saved_at:
        remaining = 1800 - int(
            (datetime.datetime.utcnow() - st.session_state.profile_saved_at).total_seconds()
        )
        st.caption(f"⏱ Profile saved — expires in ~{remaining // 60} min")

    st.markdown("---")

    if st.button("🔄 New Conversation", use_container_width=True):
        _save_current_session()
        st.session_state.thread_id      = None
        st.session_state.messages       = []
        st.session_state.starter_prompt = None
        st.session_state.session_saved  = False
        st.session_state.session_start  = datetime.datetime.utcnow()
        st.rerun()

    st.markdown("---")
    st.caption("Thread ID")
    if st.session_state.thread_id:
        st.markdown(
            f'<span class="thread-badge">{st.session_state.thread_id[:24]}…</span>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("No active conversation")


# ─────────────────────────────────────────
# Helper: build system context prefix
# ─────────────────────────────────────────
def build_context_prefix() -> str:
    parts = []
    if name:           parts.append(f"My name is {name}.")
    if job_title:      parts.append(f"I am targeting a {job_title} role.")
    if experience:     parts.append(f"I am a {experience} candidate.")
    if target_company: parts.append(f"My target company is {target_company}.")
    return " ".join(parts)


# ─────────────────────────────────────────
# Helper: get (cached) IAM token
# ─────────────────────────────────────────
def get_token() -> str:
    now = datetime.datetime.utcnow()
    if (
        st.session_state.token_cache
        and st.session_state.token_expiry
        and now < st.session_state.token_expiry
    ):
        return st.session_state.token_cache
    token = get_iam_token()
    st.session_state.token_cache  = token
    st.session_state.token_expiry = now + datetime.timedelta(minutes=50)
    return token


# ─────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────
tab_chat, tab_feedback, tab_dashboard = st.tabs(
    ["💬 Chat", "📝 Feedback", "📊 Dashboard"]
)

# ══════════════════════════════════════════
# TAB 1 – CHAT
# ══════════════════════════════════════════
with tab_chat:
    st.header("🤖 AI Interview Coach")
    st.caption("Practice interviews, get real-time feedback, and build confidence — powered by AI.")

    if not st.session_state.messages:
        st.markdown(
            """
            <div class="empty-state">
                <h3>👋 Welcome to your AI Interview Coach</h3>
                <p>Fill in your profile on the left, then pick a topic below to start practising:</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        starters = [
            "Give me 5 common HR interview questions for my role",
            "Start a mock interview with technical questions",
            "What is system design and how do I prepare for it?",
            "Evaluate a sample answer using the STAR method",
        ]
        cols = st.columns(2)
        for i, prompt in enumerate(starters):
            if cols[i % 2].button(prompt, key=f"starter_{i}", use_container_width=True):
                st.session_state.starter_prompt = prompt
                st.rerun()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.starter_prompt and not st.session_state.messages:
        user_input = st.session_state.starter_prompt
        st.session_state.starter_prompt = None
        ctx          = build_context_prefix()
        full_message = f"{ctx} {user_input}".strip() if ctx else user_input
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("Agent is thinking…"):
            try:
                token = get_token()
                response, thread_id = chat_with_agent(
                    user_message=full_message, token=token,
                    thread_id=st.session_state.thread_id,
                )
                st.session_state.thread_id = thread_id
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as exc:
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Error: {exc}"})
        st.rerun()

    user_input = st.chat_input("Ask a question or request mock interview questions…")
    if user_input:
        if not st.session_state.messages:
            ctx          = build_context_prefix()
            full_message = f"{ctx} {user_input}".strip() if ctx else user_input
        else:
            full_message = user_input

        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.spinner("Agent is thinking…"):
            try:
                token = get_token()
                response, thread_id = chat_with_agent(
                    user_message=full_message, token=token,
                    thread_id=st.session_state.thread_id,
                )
                st.session_state.thread_id = thread_id
                st.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as exc:
                st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Error: {exc}"})
        st.rerun()

# ══════════════════════════════════════════
# TAB 2 – FEEDBACK
# ══════════════════════════════════════════
with tab_feedback:
    st.header("📝 AI Answer Evaluator")
    st.markdown(
        "Paste your answer below and your **AI Interview Coach** will give structured "
        "feedback using the **S**ituation · **T**ask · **A**ction · **R**esult framework."
    )

    question_ctx = st.text_input(
        "Interview Question (optional)",
        placeholder="e.g. Tell me about a time you handled a conflict at work.",
    )
    answer_text = st.text_area("Your Answer", height=200, placeholder="Paste your full answer here…")

    if st.button("📤 Get STAR Feedback", type="primary"):
        if not answer_text.strip():
            st.warning("Please paste an answer before requesting feedback.")
        else:
            prompt = (
                f"Please evaluate the following interview answer using the STAR method "
                f"(Situation, Task, Action, Result). "
                f"{'The question was: ' + question_ctx + '. ' if question_ctx else ''}"
                f"Identify what is missing, score each dimension out of 10, and give "
                f"a concise improvement suggestion.\n\nAnswer:\n{answer_text}"
            )
            with st.spinner("Evaluating your answer…"):
                try:
                    token = get_token()
                    fb_response, thread_id = chat_with_agent(
                        user_message=prompt, token=token,
                        thread_id=st.session_state.thread_id,
                    )
                    st.session_state.thread_id       = thread_id
                    st.session_state.feedback_response = fb_response
                except Exception as exc:
                    st.session_state.feedback_response = f"⚠️ Error: {exc}"

    if st.session_state.feedback_response:
        st.markdown("### 🗒️ STAR Evaluation")
        st.markdown(
            f'<div class="star-card">{st.session_state.feedback_response}</div>',
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════
# TAB 3 – DASHBOARD
# ══════════════════════════════════════════
with tab_dashboard:
    st.header("📊 Interview Readiness Dashboard")
    st.caption("Track your progress, spot skill gaps, and see how your confidence is growing.")

    msgs       = st.session_state.messages
    user_msgs  = [m for m in msgs if m["role"] == "user"]
    agent_msgs = [m for m in msgs if m["role"] == "assistant"]
    covered    = detect_covered_topics()
    readiness  = compute_readiness()
    sessions   = load_sessions()

    # ── Readiness score ───────────────────────────────────────────────────────
    r_col, kpi_col = st.columns([1, 3])

    with r_col:
        level = "Beginner" if readiness < 30 else "Developing" if readiness < 60 else "Confident" if readiness < 85 else "Interview Ready"
        color = "#ef4444" if readiness < 30 else "#f97316" if readiness < 60 else "#3b82d4" if readiness < 85 else "#16a34a"
        st.markdown(
            f"""
            <div class="readiness-wrap">
                <div class="readiness-score" style="color:{color}">{readiness}</div>
                <div class="readiness-label">/ 100 · <strong>{level}</strong></div>
                <div class="readiness-label" style="margin-top:6px">Readiness Score</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with kpi_col:
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Questions Asked",     len(user_msgs))
        k2.metric("Agent Replies",       len(agent_msgs))
        k3.metric("Topics Covered",      f"{sum(covered.values())}/{len(ALL_TOPICS)}")
        k4.metric("Sessions Saved",      len(sessions))

    st.markdown("---")

    # ── Two-column layout ─────────────────────────────────────────────────────
    left_col, right_col = st.columns([3, 2])

    # ── LEFT: Radar chart + Topic donut ──────────────────────────────────────
    with left_col:

        # Radar chart
        st.subheader("Skill Radar")
        radar_categories = list(covered.keys())
        radar_values     = [1 if covered[t] else 0 for t in radar_categories]
        # Add first point again to close the polygon
        radar_categories_plot = radar_categories + [radar_categories[0]]
        radar_values_plot     = radar_values     + [radar_values[0]]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_values_plot,
            theta=radar_categories_plot,
            fill="toself",
            fillcolor="rgba(59,130,212,0.15)",
            line=dict(color="#3b82d4", width=2),
            name="Covered",
        ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=False, range=[0, 1]),
                angularaxis=dict(tickfont=dict(size=11)),
            ),
            showlegend=False,
            margin=dict(l=30, r=30, t=30, b=30),
            paper_bgcolor="#f7f8fa",
            height=320,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # Topic coverage donut
        st.subheader("Topic Coverage")
        covered_count   = sum(covered.values())
        remaining_count = len(ALL_TOPICS) - covered_count
        fig_donut = go.Figure(go.Pie(
            labels=["Covered", "Not yet covered"],
            values=[max(covered_count, 0.01), remaining_count],
            hole=0.6,
            marker_colors=["#3b82d4", "#e5e7eb"],
            textinfo="none",
        ))
        fig_donut.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            margin=dict(l=0, r=0, t=10, b=40),
            paper_bgcolor="#f7f8fa",
            height=220,
            annotations=[dict(
                text=f"<b>{covered_count}/{len(ALL_TOPICS)}</b>",
                x=0.5, y=0.5, font_size=20, showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # ── RIGHT: Checklist + Next steps ────────────────────────────────────────
    with right_col:

        st.subheader("Topics Checklist")
        st.caption("Auto-detected from your chat. Tick manually to mark done.")

        for topic in ALL_TOPICS:
            auto = covered.get(topic, False)
            # Pre-tick if auto-detected; allow manual override
            current = st.session_state.topics_done.get(topic, False) or auto
            checked = st.checkbox(topic, value=current, key=f"topic_{topic}")
            st.session_state.topics_done[topic] = checked

        st.markdown("---")

        # Next steps recommendation
        pending_topics = [t for t in ALL_TOPICS if not st.session_state.topics_done.get(t)]
        st.subheader("What to Practise Next")
        if not pending_topics:
            st.success("You've covered all topics! You're ready for your interview.")
        else:
            suggestions = pending_topics[:2]
            items_html  = "".join(f"<li>{s}</li>" for s in suggestions)
            st.markdown(
                f"""
                <div class="next-card">
                    <h4>Suggested next topics</h4>
                    <ul>{items_html}</ul>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.caption("Click a starter prompt in the Chat tab to begin.")

    st.markdown("---")

    # ── Confidence trend from saved sessions ─────────────────────────────────
    st.subheader("Readiness Trend")

    if sessions:
        df_trend = pd.DataFrame([
            {"Session": f"S{i+1}", "Readiness": s.get("readiness", 0)}
            for i, s in enumerate(sessions[-10:])
        ])
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=df_trend["Session"],
            y=df_trend["Readiness"],
            mode="lines+markers",
            line=dict(color="#3b82d4", width=2),
            marker=dict(size=7),
            fill="tozeroy",
            fillcolor="rgba(59,130,212,0.1)",
            name="Readiness",
        ))
        fig_trend.update_layout(
            yaxis=dict(range=[0, 100], title="Readiness Score"),
            xaxis_title="Session",
            paper_bgcolor="#f7f8fa",
            plot_bgcolor="#f7f8fa",
            margin=dict(l=0, r=0, t=10, b=0),
            height=250,
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Complete a conversation and start a **New Conversation** to save your first session and see your progress trend here.")
