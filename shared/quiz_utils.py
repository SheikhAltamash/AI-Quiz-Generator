"""
Shared Quiz Generation and Display Functions

This module contains:
- generate_questions(): AI-powered quiz generation
- create_quiz_pdf(): PDF export functionality
- display_quiz(): Frontend quiz display with MCQ/MSQ support
"""

import os
import json
import streamlit as st
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from dotenv import load_dotenv

# Get the project root directory (parent of 'shared' folder)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env from project root
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Import the API manager
import sys
sys.path.insert(0, PROJECT_ROOT)
# from gemini_api_manager import GeminiAPIManager
from groq_api_manager import GroqAPIManager

# Initialize API manager (Groq)
api_manager = GroqAPIManager()

# --- Logging Configuration ---
# Suppress noisy library logs to keep terminal clean
import logging
logging.getLogger("fontTools").setLevel(logging.WARNING)

# --- Font Configuration ---
SYSTEM_FONTS = [
    ("Nirmala", "C:/Windows/Fonts/Nirmala.ttf"),
    ("ArialUnicode", "C:/Windows/Fonts/arialuni.ttf"),
    ("Arial", "C:/Windows/Fonts/arial.ttf")
]
LOCAL_HINDI_FONT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "NotoSansDevanagari-Regular.ttf")


class QuizPDF(FPDF):
    def __init__(self):
        super().__init__(orientation='L')
        self.set_margins(8, 8, 8)
        self.set_auto_page_break(True, 10)
        
        self.main_font = None
        self.hindi_font = None
        
        for name, path in SYSTEM_FONTS:
            if os.path.exists(path):
                try:
                    self.add_font(name, "", path)
                    self.main_font = name
                    break
                except:
                    pass
        
        if os.path.exists(LOCAL_HINDI_FONT):
            try:
                self.add_font("NotoSans", "", LOCAL_HINDI_FONT)
                self.hindi_font = "NotoSans"
            except:
                pass

        if not self.main_font:
            self.main_font = 'helvetica'

    def header(self):
        self.set_font(self.main_font, 'B', 16)
        self.cell(0, 10, 'Teaching Pariksha: AI Generated Quiz', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.main_font, 'I', 10)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')


def safe_text(text, max_len=300):
    if not text: return ""
    clean = str(text).replace('\n', ' ').replace('\r', ' ')
    return clean[:max_len] + "..." if len(clean) > max_len else clean


def clean_latin(text):
    """Remove non-latin characters to prevent font crashes"""
    return "".join([c for c in text if ord(c) < 256])


def generate_questions(text, num=5, diff="Medium", q_type="MCQ", topics=None):
    """Generate questions using the API manager."""
    
    if q_type == "MSQ":
        question_format = "MSQs (Multiple Select Questions - questions with 2 or more correct answers)"
        correct_field = '"correct_options": ["A", "C"]'
        msq_rule = "- For MSQ, each question MUST have 2-3 correct answers (NOT just 1)"
    else:
        question_format = "MCQs (Multiple Choice Questions - single correct answer)"
        correct_field = '"correct_option": "A"'
        msq_rule = "- For MCQ, each question has exactly 1 correct answer"
    
    # Topics instruction
    if topics and len(topics) > 0:
        topics_instruction = f"- Focus questions on these specific topics: {', '.join(topics)}"
    else:
        topics_instruction = "- Generate questions from the entire content"
    
    prompt = f"""
    You are a Senior Faculty at Teaching Pariksha. 
    
    CRITICAL: Generate EXACTLY {num} {question_format}. Not more, not less.
    
    Difficulty Level: {diff}
    
    Output ONLY a valid JSON array, no other text. Strictly follow this structure:
    [{{
        "question_en": "Question in English",
        "question_hi": "Question in Hindi",
        "options_en": {{"A": "Option A in English", "B": "Option B", "C": "Option C", "D": "Option D"}},
        "options_hi": {{"A": "Option A in Hindi", "B": "Option B", "C": "Option C", "D": "Option D"}},
        {correct_field},
        "explanation_en": "Explanation in English",
        "explanation_hi": "Explanation in Hindi"
    }}, ...]
    
    Rules:
    - Exactly {num} questions
    {msq_rule}
    {topics_instruction}
    - Keep options concise (max 40 characters each)
    - Provide both English AND Hindi for questions, options, and explanations
    - CTET/BPSC exam style
    
    CONTENT: {text[:12000]}
    """
    
    response_text, model_used = api_manager.generate_content(prompt)
    return response_text, model_used


def create_quiz_pdf(quiz_data, include_hindi=True):
    """Generate PDF from quiz data."""
    pdf = QuizPDF()
    pdf.add_page()
    
    universal_mode = (pdf.main_font in ["Nirmala", "ArialUnicode"])
    english_font = pdf.main_font
    hindi_font = pdf.hindi_font if pdf.hindi_font else pdf.main_font
    use_hindi_content = include_hindi and (universal_mode or pdf.hindi_font)

    # Questions Section
    for i, q in enumerate(quiz_data, 1):
        try:
            q_en_raw = f"Q{i}: {q.get('question_en', 'Question not available')}"
            
            if universal_mode:
                pdf.set_font(english_font, '', 12)
                pdf.multi_cell(0, 6, safe_text(q_en_raw), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                pdf.set_font(english_font, '', 12)
                pdf.multi_cell(0, 6, safe_text(clean_latin(q_en_raw)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            if use_hindi_content and 'question_hi' in q and q['question_hi'].strip():
                font_to_use = english_font if universal_mode else hindi_font
                pdf.set_font(font_to_use, '', 11)
                pdf.multi_cell(0, 6, safe_text(f"({q['question_hi']})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.ln(3)
            
            if 'options_en' in q:
                opts_en = q['options_en']
                opts_hi = q.get('options_hi', {})
            else:
                opts_en = q.get('options', {})
                opts_hi = {}

            for letter in ['A', 'B', 'C', 'D']:
                en_text = opts_en.get(letter, '')
                hi_text = opts_hi.get(letter, '')
                
                if universal_mode:
                    pdf.set_font(english_font, '', 11)
                    pdf.multi_cell(0, 6, f"{letter}) {safe_text(en_text)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.set_font(english_font, '', 11)
                    pdf.multi_cell(0, 6, f"{letter}) {safe_text(clean_latin(en_text))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                if use_hindi_content and hi_text:
                    font_to_use = english_font if universal_mode else hindi_font
                    pdf.set_font(font_to_use, '', 10)
                    pdf.set_x(pdf.get_x() + 5)
                    pdf.multi_cell(0, 6, safe_text(hi_text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.ln(4)
            
        except Exception as e:
            pdf.set_font('helvetica', '', 10)
            pdf.cell(0, 5, f"Q{i}: [Error]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Answer Key
    pdf.add_page()
    pdf.set_font(english_font, 'B', 14)
    pdf.cell(0, 10, "Answer Key", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    for i, q in enumerate(quiz_data, 1):
        pdf.set_font(english_font, 'B', 11)
        
        if 'correct_options' in q and isinstance(q['correct_options'], list):
            answer_text = ", ".join(sorted(q['correct_options']))
        else:
            answer_text = q.get('correct_option', '?')
        
        pdf.cell(0, 6, f"Q{i}: {answer_text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        exp_en = q.get('explanation_en', q.get('explanation', ''))
        if exp_en:
            pdf.set_font(english_font, '', 10)
            if universal_mode:
                 pdf.multi_cell(0, 5, safe_text(f"EN: {exp_en}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                 pdf.multi_cell(0, 5, safe_text(clean_latin(f"EN: {exp_en}")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        exp_hi = q.get('explanation_hi', '')
        if use_hindi_content and exp_hi:
            font_to_use = english_font if universal_mode else hindi_font
            pdf.set_font(font_to_use, '', 10)
            prefix = "HI: " if universal_mode else ""
            pdf.multi_cell(0, 5, safe_text(f"{prefix}{exp_hi}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.ln(3)

    return bytes(pdf.output())


def display_quiz(quiz_data, quiz_type="MCQ"):
    """Display quiz with MCQ (radio) or MSQ (checkbox) mode."""
    
    for i, q in enumerate(quiz_data, 1):
        st.markdown(f"### Q{i}: {q['question_en']}")
        st.markdown(f"**Hindi:** {q['question_hi']}")
        
        if 'options_en' in q and 'options_hi' in q:
            opts_en = q['options_en']
            opts_hi = q['options_hi']
            options_dict = {
                letter: f"{opts_en.get(letter, '')} ({opts_hi.get(letter, '')})"
                for letter in ['A', 'B', 'C', 'D']
            }
        else:
            opts = q.get('options', {})
            options_dict = {letter: opts.get(letter, '') for letter in ['A', 'B', 'C', 'D']}
        
        is_msq = quiz_type == "MSQ"
        
        if is_msq:
            st.write("**Select all correct answers:**")
            selected_options = []
            
            cols = st.columns(2)
            for idx, letter in enumerate(['A', 'B', 'C', 'D']):
                with cols[idx % 2]:
                    if st.checkbox(f"{letter}) {options_dict[letter]}", key=f"q{i}_{letter}"):
                        selected_options.append(letter)
            
            if st.button(f"✅ Check Answer for Q{i}", key=f"check_{i}"):
                correct_options = q.get('correct_options', [])
                if not correct_options and 'correct_option' in q:
                    correct_options = [q['correct_option']]
                
                if set(selected_options) == set(correct_options):
                    st.success(f"✅ Correct! The answers are **{', '.join(sorted(correct_options))}**")
                else:
                    st.error(f"❌ Wrong. You selected **{', '.join(sorted(selected_options)) if selected_options else 'nothing'}**. Correct answers: **{', '.join(sorted(correct_options))}**")
                
                with st.expander(f"View Explanation for Q{i}"):
                    if 'explanation_en' in q:
                        st.info(f"**English:** {q['explanation_en']}")
                    if 'explanation_hi' in q:
                        st.info(f"**Hindi:** {q['explanation_hi']}")
        else:
            options_list = [f"{letter}) {options_dict[letter]}" for letter in ['A', 'B', 'C', 'D']]
            
            user_answer = st.radio(
                f"Select your answer for Q{i}:", 
                options_list, 
                key=f"q_{i}", 
                index=None
            )
            
            if user_answer:
                selected_option = user_answer.split(")")[0]
                correct_option = q.get('correct_option', q.get('correct_options', ['?'])[0] if isinstance(q.get('correct_options'), list) else '?')
                
                if selected_option == correct_option:
                    st.success(f"✅ Correct! The answer is **{correct_option}**")
                else:
                    st.error(f"❌ Wrong. You selected **{selected_option}**, but the correct answer is **{correct_option}**.")
                
                with st.expander(f"View Explanation for Q{i}"):
                    if 'explanation_en' in q:
                        st.info(f"**English:** {q['explanation_en']}")
                    if 'explanation_hi' in q:
                        st.info(f"**Hindi:** {q['explanation_hi']}")
        
        st.divider()
