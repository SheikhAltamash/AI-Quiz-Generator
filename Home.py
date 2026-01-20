"""
Teaching Pariksha - AI Quiz Generator

A multi-source quiz generator powered by Groq Llama 3 AI.
"""

import streamlit as st
import os
from PIL import Image

st.set_page_config(
    page_title="Home - Teaching Pariksha",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load custom CSS for mobile responsiveness
css_path = os.path.join(os.path.dirname(__file__), ".streamlit", "style.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Display logo and title
logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
col_logo, col_title = st.columns([1, 5])
with col_logo:
    if os.path.exists(logo_path):
        st.image(logo_path, width=80)
with col_title:
    st.title("Teaching Pariksha")
    st.caption("AI-Powered Quiz Generator")

st.markdown("---")

st.markdown("Generate **bilingual MCQ/MSQ quizzes** from various content sources using **Groq Ultra-Fast AI (Llama 3)**.")

st.markdown("---")

# Navigation Buttons
st.markdown("### Choose Your Content Source:")

col1, col2 = st.columns(2)

with col1:
    if st.button("YouTube Quiz", use_container_width=True, type="primary"):
        with st.spinner("Loading YouTube Quiz..."):
            st.switch_page("pages/1_YouTube_Quiz.py")
    st.caption("Generate quizzes from YouTube video transcripts")

with col2:
    if st.button("Website Quiz", use_container_width=True, type="primary"):
        with st.spinner("Loading Website Quiz..."):
            st.switch_page("pages/2_Website_Quiz.py")
    st.caption("Scrape text from up to 5 websites and create quizzes")

st.markdown("""
---

### Features:

- **Bilingual**: Questions, options, and explanations in English + Hindi
- **MCQ/MSQ**: Single answer or multiple answer questions
- **PDF Export**: Download your quiz with answer key
- **Customizable**: Set difficulty level and question count

---

*Powered by Groq Ultra-Fast AI | Built with Streamlit*
""")