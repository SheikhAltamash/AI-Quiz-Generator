"""
Website Quiz Generator

Generate quizzes from website content. Supports up to 5 URLs at once.
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.quiz_utils import generate_questions, create_quiz_pdf, display_quiz

st.set_page_config(page_title="Website Quiz - Teaching Pariksha", page_icon="", layout="wide")

# Load custom CSS for mobile responsiveness
css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".streamlit", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("Website Quiz Generator")
st.markdown("Generate quizzes from any website content. Enter up to **5 URLs** below.")


# --- WEB SCRAPER FUNCTION ---
def scrape_website(url):
    """Extract visible text from a website."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url.strip(), headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form', 'noscript']):
            tag.decompose()
        
        # Get visible text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up extra whitespace
        text = ' '.join(text.split())
        
        return text, None
        
    except requests.exceptions.RequestException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


# --- URL INPUT ---
st.subheader("Enter Website URLs (one per line, max 5)")
urls_input = st.text_area(
    "Website URLs",
    placeholder="https://example.com/article1\nhttps://example.com/article2\nhttps://another-site.com/page",
    height=150,
    label_visibility="collapsed"
)

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
if 'web_topics' not in st.session_state:
    st.session_state.web_topics = []
if 'web_topic_input_key' not in st.session_state:
    st.session_state.web_topic_input_key = 0

# Input and Add button in columns
topic_col1, topic_col2 = st.columns([4, 1])
with topic_col1:
    new_topic = st.text_input("Enter topic name", key=f"web_new_topic_{st.session_state.web_topic_input_key}", label_visibility="collapsed", placeholder="e.g., Machine Learning, History...")
with topic_col2:
    if st.button("Add", key="web_add_topic", use_container_width=True):
        if new_topic and new_topic.strip() not in st.session_state.web_topics:
            st.session_state.web_topics.append(new_topic.strip())
            st.session_state.web_topic_input_key += 1  # Change key to reset input
            st.rerun()

# Display added topics as chips with remove button
if st.session_state.web_topics:
    topic_cols = st.columns(len(st.session_state.web_topics) + 1)
    for i, topic in enumerate(st.session_state.web_topics):
        with topic_cols[i]:
            if st.button(f"{topic} ✕", key=f"web_remove_{i}", help="Click to remove"):
                st.session_state.web_topics.pop(i)
                st.rerun()


# --- SESSION STATE ---
if 'web_quiz_data' not in st.session_state:
    st.session_state.web_quiz_data = None
if 'web_quiz_generated' not in st.session_state:
    st.session_state.web_quiz_generated = False
if 'web_model_used' not in st.session_state:
    st.session_state.web_model_used = ""
if 'web_quiz_type' not in st.session_state:
    st.session_state.web_quiz_type = "MCQ"


# --- GENERATE BUTTON ---
if st.button("🚀 Generate Quiz from Websites"):
    if not urls_input.strip():
        st.warning("Please enter at least one website URL.")
    else:
        # Extract URLs using regex - handles URLs without newlines between them
        import re
        url_pattern = r'https?://[^\s<>"\']+'
        urls = re.findall(url_pattern, urls_input)
        urls = list(dict.fromkeys(urls))  # Remove duplicates while preserving order
        
        if not urls:
            st.warning("No valid URLs found. Please enter URLs starting with http:// or https://")
        elif len(urls) > 5:
            st.warning("Maximum 5 URLs allowed. Only the first 5 will be used.")
            urls = urls[:5]
        
        # Only proceed if we have valid URLs
        if urls:
            # Clear old data and force UI refresh
            st.session_state.web_quiz_data = None
            st.session_state.web_quiz_generated = False
            
            q_type = "MSQ" if "MSQ" in question_type else "MCQ"
            st.session_state.web_quiz_type = q_type
            
            with st.spinner(f"🌐 Fetching data from {len(urls)} website(s)..."):
                all_text = []
                url_results = []  # Collect results first
                
                for url in urls:
                    text, error = scrape_website(url)
                    short_url = url[:30] + "..." if len(url) > 30 else url
                    url_results.append((short_url, text is not None, text))
                    if text:
                        all_text.append(f"--- Content from {url} ---\n{text}")
                
                # Show status after fetching (simplified - only checkmarks)
                success_count = sum(1 for r in url_results if r[1])
                if success_count > 0:
                    st.success(f"✅ Loaded content from {success_count} of {len(url_results)} source(s)")
            
            if not all_text:
                st.error("⚠️ Unable to fetch content from the provided URLs.")
            else:
                combined_text = "\n\n".join(all_text)
                
                with st.spinner(f"Generating {num_questions} {difficulty} {q_type}s..."):
                    try:
                        # Get topics from session state
                        topics = st.session_state.get('web_topics', [])
                        raw_response, model_used = generate_questions(combined_text, num_questions, difficulty, q_type, topics)
                        
                        # JSON extraction
                        json_start = raw_response.find('[')
                        json_end = raw_response.rfind(']')
                        
                        if json_start != -1 and json_end != -1:
                            clean_json = raw_response[json_start:json_end+1]
                        else:
                            clean_json = raw_response.strip()
                        
                        quiz_data = json.loads(clean_json)
                        
                        # ENFORCE QUESTION COUNT - truncate if AI returns more
                        if len(quiz_data) > num_questions:
                            quiz_data = quiz_data[:num_questions]
                        
                        st.session_state.web_quiz_data = quiz_data
                        st.session_state.web_quiz_generated = True
                        st.session_state.web_model_used = model_used
                        st.rerun()  # Force refresh to clear old UI elements
                        
                    except json.JSONDecodeError:
                        st.error("⚠️ Unable to process AI response. Please try again.")
                    except Exception as e:
                        st.error(f"⚠️ Unable to generate quiz. Please try again.")


# --- DISPLAY QUIZ ---
if st.session_state.web_quiz_generated and st.session_state.web_quiz_data:
    st.success("Quiz Generated Successfully!")
    
    # PDF Download
    pdf_bytes = None
    try:
        pdf_bytes = create_quiz_pdf(st.session_state.web_quiz_data, include_hindi=True)
        pdf_label = "📄 Download Quiz PDF (Hindi + English)"
    except Exception as e:
        try:
            pdf_bytes = create_quiz_pdf(st.session_state.web_quiz_data, include_hindi=False)
            st.warning("⚠️ Hindi PDF failed. Download English-only PDF.")
            pdf_label = "📄 Download Quiz PDF (English Only)"
        except Exception as e2:
            st.error(f"Failed to generate PDF: {e2}")
    
    if pdf_bytes:
        st.download_button(
            label=pdf_label,
            data=pdf_bytes,
            file_name="website_quiz.pdf",
            mime="application/pdf"
        )
    
    # Display Quiz
    display_quiz(st.session_state.web_quiz_data, st.session_state.web_quiz_type)
    
    # Reset Button
    if st.button("🔄 Start New Quiz"):
        st.session_state.web_quiz_data = None
        st.session_state.web_quiz_generated = False
        st.rerun()
