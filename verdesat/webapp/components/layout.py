from __future__ import annotations

"""Layout and theming helpers for the Streamlit dashboard."""

import streamlit as st

NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Book a Demo", "https://calendly.com/andreydara/meet-verdesat"),
    ("Home", "https://www.verdesat.com"),
)


def apply_theme() -> None:
    """Inject fonts, colors, and base CSS matching VerdeSat branding."""

    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Montserrat:wght@400;600;700&display=swap');
        html, body, [class*="css"] {font-family: 'Inter', sans-serif; color: #14213D;}
        h1, h2, h3, h4, h5 {font-family: 'Montserrat', sans-serif; font-weight: 600; color: #14213D;}
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .vs-navbar {position: fixed; top: 0; left: 0; right: 0; background: rgba(255,255,255,0.8); backdrop-filter: blur(6px); height: 56px; padding: 8px 24px; display: flex; align-items: center; z-index: 1000; box-shadow: 0 1px 2px rgba(0,0,0,0.05);}
        .vs-navbar img {height: 32px; margin-right: 8px;}
        .vs-navbar a {
            color: #14213D;
            margin-left: 24px;
            text-decoration: none;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        .vs-navbar a:hover {color: #2B6E3F;}
        .vs-hero {margin-top: 56px; background: linear-gradient(180deg, rgba(19,78,74,0.5), rgba(19,78,74,0.5) 50%, #134E4A), url('https://www.verdesat.com/images/hero-sat-screen.webp'); background-size: cover; background-position: center; padding: 96px 24px; text-align: center; color: #FFFFFF;}
        div.block-container > div:nth-child(even):not(.vs-hero) {background-color: #FFFFFF;}
        div.block-container > div:nth-child(odd):not(.vs-hero) {background-color: #F8F9FA;}
        div.block-container > div:not(.vs-hero) {padding: 32px 24px;}
        .stButton>button, .stDownloadButton>button {background-color: #2B6E3F; color: #FFFFFF; border-radius: 9999px;}
        .stButton>button:hover, .stDownloadButton>button:hover {color: #6EE7B7;}
        @media (max-width: 600px) {
            .vs-navbar {flex-wrap: wrap; height: auto; padding: 8px 16px; background: rgba(255,255,255,0.9);}
            .vs-navbar a {margin-left: 16px; margin-top: 4px;}
            .vs-hero {padding: 64px 16px;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navbar() -> None:
    """Render the fixed top navigation bar."""

    links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        for label, url in NAV_LINKS
    )
    st.markdown(
        f"""
        <nav class="vs-navbar">
            <img src="https://www.verdesat.com/favicon.svg" alt="VerdeSat logo" />
            {links}
        </nav>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str) -> None:
    """Display a full-width hero banner with ``title``."""

    st.markdown(
        f"""
        <section class="vs-hero">
            <h1>{title}</h1>
        </section>
        """,
        unsafe_allow_html=True,
    )
