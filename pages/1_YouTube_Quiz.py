"""
YouTube Quiz Generator

Generate quizzes from YouTube video transcripts.
"""

import streamlit as st
import time
from youtube_transcript_api import YouTubeTranscriptApi
import re
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.quiz_utils import generate_questions, create_quiz_pdf, display_quiz

st.set_page_config(page_title="YouTube Quiz - Teaching Pariksha", page_icon="", layout="wide")

# Initial page loader
if 'yt_loaded' not in st.session_state:
    with st.spinner("Loading YouTube Quiz..."):
        time.sleep(0.5)
    st.session_state.yt_loaded = True

# Load custom CSS for mobile responsiveness
css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("YouTube Quiz Generator")
st.markdown("Generate quizzes from YouTube video transcripts.")


# --- TRANSCRIPT FUNCTION ---
def get_transcript(video_url):
    """Extract transcript from YouTube video."""
    try:
        # Extract video ID
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be/)([0-9A-Za-z_-]{11})',
        ]
        
        video_id = None
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                video_id = match.group(1)
                break
        
        if not video_id:
            st.error("Could not extract video ID from URL.")
            return None
        
        # New API for youtube-transcript-api v1.2.x
        ytt_api = YouTubeTranscriptApi()
        
        # Try fetching transcript in different languages
        languages_to_try = ['hi', 'en', 'en-IN', 'hi-IN']
        transcript = None
        
        for lang in languages_to_try:
            try:
                transcript = ytt_api.fetch(video_id, languages=[lang])
                break
            except:
                continue
        
        # If specific languages failed, try to get any available transcript
        if transcript is None:
            try:
                transcript_list = ytt_api.list(video_id)
                if transcript_list:
                    # Get the first available transcript
                    first_transcript = transcript_list[0]
                    transcript = ytt_api.fetch(video_id, languages=[first_transcript.language_code])
            except Exception as e:
                print(f"List transcripts error: {e}")
        
        if transcript is None:
            st.error("No transcripts available for this video.")
            return None
        
        # Extract text from snippets
        full_text = " ".join([snippet.text for snippet in transcript.snippets])
        return full_text
        
    except Exception as e:
        print(f"Transcript error: {e}")
        st.error("Unable to process this video. Please check if it has captions enabled.")
        return None


# --- URL INPUT ---
video_url = st.text_input("Paste YouTube URL:", placeholder="https://www.youtube.com/watch?v=...")

# --- SETTINGS ON MAIN PAGE ---
col1, col2, col3 = st.columns(3)
with col1:
    num_questions = st.number_input("Number of Questions", min_value=5, max_value=50, value=5, step=1)
with col2:
    difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])
with col3:
    question_type = st.radio("Question Type", ["MCQ", "MSQ"], horizontal=True)


# --- OPTIONAL TOPICS SECTION ---
st.markdown("**Topics (Optional)** - Add specific topics to focus the quiz")

# Initialize topics and input key counter in session state
if 'yt_topics' not in st.session_state:
    st.session_state.yt_topics = []
if 'yt_topic_input_key' not in st.session_state:
    st.session_state.yt_topic_input_key = 0

# Input and Add button in columns
topic_col1, topic_col2 = st.columns([4, 1])
with topic_col1:
    new_topic = st.text_input("Enter topic name", key=f"yt_new_topic_{st.session_state.yt_topic_input_key}", label_visibility="collapsed", placeholder="e.g., Child Development, Pedagogy...")
with topic_col2:
    if st.button("Add", key="yt_add_topic", use_container_width=True):
        if new_topic and new_topic.strip() not in st.session_state.yt_topics:
            st.session_state.yt_topics.append(new_topic.strip())
            st.session_state.yt_topic_input_key += 1  # Change key to reset input
            st.rerun()

# Display added topics as chips with remove button
if st.session_state.yt_topics:
    topic_cols = st.columns(len(st.session_state.yt_topics) + 1)
    for i, topic in enumerate(st.session_state.yt_topics):
        with topic_cols[i]:
            if st.button(f"{topic} ✕", key=f"yt_remove_{i}", help="Click to remove"):
                st.session_state.yt_topics.pop(i)
                st.rerun()


# --- SESSION STATE ---
if 'yt_quiz_data' not in st.session_state:
    st.session_state.yt_quiz_data = None
if 'yt_quiz_generated' not in st.session_state:
    st.session_state.yt_quiz_generated = False
if 'yt_model_used' not in st.session_state:
    st.session_state.yt_model_used = ""
if 'yt_quiz_type' not in st.session_state:
    st.session_state.yt_quiz_type = "MCQ"


# --- GENERATE BUTTON ---
if st.button("🚀 Generate Quiz"):
    if not video_url:
        st.warning("Please paste a YouTube URL.")
    else:
        st.session_state.yt_quiz_data = None
        st.session_state.yt_quiz_generated = False
        
        q_type = "MSQ" if "MSQ" in question_type else "MCQ"
        st.session_state.yt_quiz_type = q_type
        
        with st.spinner(f"🎧 Generating {num_questions} {difficulty} {q_type}s..."):
            transcript_text = get_transcript(video_url)
            
            if transcript_text:
                try:
                    # Get topics from session state
                    topics = st.session_state.get('yt_topics', [])
                    raw_response, model_used = generate_questions(transcript_text, num_questions, difficulty, q_type, topics)
                    
                    try:
                        json_start = raw_response.find('[')
                        json_end = raw_response.rfind(']')
                        
                        if json_start != -1 and json_end != -1:
                            clean_json = raw_response[json_start:json_end+1]
                        else:
                            clean_json = raw_response.strip()
                        
                        st.session_state.yt_quiz_data = json.loads(clean_json)
                        st.session_state.yt_quiz_generated = True
                        st.session_state.yt_model_used = model_used
                        
                    except json.JSONDecodeError:
                        st.error("Failed to parse JSON response from AI.")
                        with st.expander("See Raw Response"):
                            st.code(raw_response)
                            
                except Exception as e:
                    st.error(f"AI error: {e}")
            else:
                st.error("Could not retrieve transcript. Does the video have captions?")


# --- DISPLAY QUIZ ---
if st.session_state.yt_quiz_generated and st.session_state.yt_quiz_data:
    st.success("Quiz Generated Successfully!")
    
    # PDF Download
    pdf_bytes = None
    try:
        pdf_bytes = create_quiz_pdf(st.session_state.yt_quiz_data, include_hindi=True)
        pdf_label = "📄 Download Quiz PDF (Hindi + English)"
    except Exception as e:
        try:
            pdf_bytes = create_quiz_pdf(st.session_state.yt_quiz_data, include_hindi=False)
            st.warning("⚠️ Hindi PDF failed. Download English-only PDF.")
            pdf_label = "📄 Download Quiz PDF (English Only)"
        except Exception as e2:
            st.error(f"Failed to generate PDF: {e2}")
    
    if pdf_bytes:
        st.download_button(
            label=pdf_label,
            data=pdf_bytes,
            file_name="youtube_quiz.pdf",
            mime="application/pdf"
        )
    
    # Display Quiz
    display_quiz(st.session_state.yt_quiz_data, st.session_state.yt_quiz_type)
    
    # Reset Button
    if st.button("🔄 Start New Quiz"):
        st.session_state.yt_quiz_data = None
        st.session_state.yt_quiz_generated = False
        st.rerun()
