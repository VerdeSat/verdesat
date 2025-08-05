from __future__ import annotations

"""Styling utilities for the Streamlit web application."""

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

LOGO_URL = "https://www.verdesat.com/favicon.svg"
HERO_URL = "https://www.verdesat.com/images/hero-sat-screen.webp"
DEMO_URL = "https://calendly.com/andreydara/meet-verdesat"
REPORT_URL = "https://www.verdesat.com/sample-report.pdf"


def inject_style() -> None:
    """Inject global CSS rules and fonts."""
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Montserrat:wght@400;600;700&display=swap');
        html, body, [class*='css'] {{
            font-family: 'Inter', sans-serif;
        }}
        h1, h2, h3, h4, h5 {{
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }}
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
        .stButton>button {{
            background-color: #2B6E3F;
            color: #FFFFFF;
            border-radius: 9999px;
            border: 1px solid #6EE7B7;
        }}
        .vs-btn {{
            background-color: #2B6E3F;
            color: #6EE7B7;
            padding: 0.5rem 1.5rem;
            border-radius: 9999px;
            text-decoration: none;
        }}
        .vs-btn:hover {{opacity: 0.9;}}
        .vs-navbar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 999;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.5rem 1rem;
            background-color: #FFFFFF;
        }}
        .vs-navbar a {{
            margin-left: 1rem;
            text-decoration: none;
            color: #14213D;
        }}
        .vs-hero {{
            margin-top: 60px;
            position: relative;
            height: 300px;
            background: linear-gradient(180deg, rgba(19,78,74,0.5), rgba(19,78,74,0.5) 50%, #134E4A), url('{HERO_URL}') center/cover no-repeat;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            color: white;
            text-align: center;
        }}
        .vs-section {{
            background-color: #FFFFFF;
            padding: 2rem 1rem;
        }}
        .vs-section-alt {{
            background-color: #F8F9FA;
            padding: 2rem 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navbar() -> None:
    """Render the top navigation bar."""
    st.markdown(
        f"""
        <nav class=\"vs-navbar\">
            <div>
                <a href=\"https://www.verdesat.com\"><img src=\"{LOGO_URL}\" height=\"32\"/></a>
            </div>
            <div>
                <a href=\"{DEMO_URL}\" target=\"_blank\">Demo</a>
                <a href=\"{REPORT_URL}\" target=\"_blank\">Sample Report</a>
            </div>
        </nav>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    """Render the hero section with call to actions."""
    st.markdown(
        f"""
        <section class=\"vs-hero\">
            <h1>VerdeSat Biodiversity Dashboard</h1>
            <div style=\"margin-top:1rem;\">
                <a class=\"vs-btn\" href=\"{DEMO_URL}\" target=\"_blank\">Book a Demo</a>
                <a class=\"vs-btn\" href=\"{REPORT_URL}\" target=\"_blank\" style=\"margin-left:0.5rem;\">Sample Report</a>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def section(alt: bool = False) -> Iterator[None]:
    """Context manager for content sections with alternating backgrounds."""
    cls = "vs-section-alt" if alt else "vs-section"
    st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)
    try:
        yield
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


__all__ = ["inject_style", "render_navbar", "render_hero", "section"]
