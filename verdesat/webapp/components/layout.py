from __future__ import annotations

"""Layout and theming helpers for the Streamlit dashboard."""

import streamlit as st
import streamlit.components.v1 as components

# (label, url) pairs used to build the navbar. The "Book a Demo" link is
# styled separately from the main site link.
NAV_LINKS: tuple[tuple[str, str], ...] = (
    ("Book a Demo", "https://calendly.com/andreydara/meet-verdesat"),
    ("VerdeSat", "https://www.verdesat.com"),
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
        .vs-navbar {position: fixed; top: 0; left: 0; right: 0; background: rgba(255,255,255,0.8); backdrop-filter: blur(6px); height: 56px; padding: 8px 24px; display: flex; align-items: center; z-index: 40000; box-shadow: 0 1px 2px rgba(0,0,0,0.05);}
        /* Make navbar transparent to clicks so the collapsed sidebar toggle remains accessible */
        .vs-navbar {pointer-events:none;}
        .vs-navbar a,
        .vs-navbar img {pointer-events:auto;}
        .vs-nav-links {margin-left: auto; display: flex; align-items: center;}
        .vs-nav-links img {height: 24px; margin: 0 8px;}
        /* Hide Streamlit’s default collapsed sidebar chevron; we provide our own */
        /* === Slide-out sidebar gimmick ===================================== */
        section[data-testid="stSidebar"] {transition: transform .3s ease-in-out;}
        body.vs-sidebar-hidden section[data-testid="stSidebar"] {transform: translateX(-100%);}
        body.vs-sidebar-hidden div[data-testid="collapsedControl"] {display:none!important;}
        /* Hide the stub Streamlit button we click from JS */
        button[title="Sidebar"] {
            position: absolute !important;
            top: -1000px !important;
            left: -1000px !important;
            width: 1px !important;
            height: 1px !important;
            padding: 0 !important;
            border: none !important;
            opacity: 0 !important;
        }
        .vs-nav-links a {
            color: #14213D;
            margin-left: 24px;
            text-decoration: none;
            font-family: 'Montserrat', sans-serif;
            font-weight: 600;
        }
        .vs-nav-links a.book-demo {color: #111827; font-weight: 400;}
        .vs-nav-links a.verdesat-link {color: #254D4A; font-size: 1.3rem; font-weight: 650;}
        .vs-nav-links a:hover {color: #2B6E3F;}
        .vs-hero {background: linear-gradient(180deg, rgba(19,78,74,0.5), rgba(19,78,74,0.5) 50%, #134E4A), url('https://www.verdesat.com/images/hero-sat-screen.webp'); background-size: cover; background-position: center; padding: 48px 24px; text-align: center; color: #FFFFFF; margin-top: -56px;}
        .vs-hero h1 { margin-bottom: 8px; }
        .vs-hero .subtitle { font-family: 'Inter', sans-serif; font-weight: 400; font-size: 1.1rem; color: #F0FDF4; opacity: 0.95; margin-top: 0; }
        div.block-container {padding-top: 0;}
        div.block-container > div:nth-child(even):not(.vs-hero) {background-color: #FFFFFF;}
        div.block-container > div:nth-child(odd):not(.vs-hero) {background-color: #F8F9FA;}
        div.block-container > div:not(.vs-hero) {padding: 32px 24px;}
        .stButton>button, .stDownloadButton>button {background-color: #2B6E3F; color: #FFFFFF; border-radius: 9999px;}

        .stButton>button:hover,
        .stDownloadButton>button:hover {
            color: #6EE7B7
        }
        .stDownloadButton>button:focus {
            color: #6EE7B7
        }
        .stButton>button:focus,
        .stButton>button:active,
        .stDownloadButton>button:focus,
        .stDownloadButton>button:active {
            color: #FFFFFF
        }
        @media (max-width: 600px) {
            .vs-navbar {flex-wrap: wrap; height: auto; padding: 8px 16px; background: rgba(255,255,255,0.9);}
            .vs-navbar a {margin-left: 16px; margin-top: 4px;}
            .vs-hero {padding: 32px 16px;}
        }
        div[data-testid="collapsedControl"] {display:none !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navbar() -> None:
    """Render the fixed top navigation bar and sidebar-toggle stub inside it."""

    links_html = "".join(
        f'<a class="{ "book-demo" if lbl=="Book a Demo" else "verdesat-link" }" '
        f'href="{url}" target="_blank">{lbl}</a>'
        + ('<img src="https://www.verdesat.com/favicon.svg"/>' if i == 0 else "")
        for i, (lbl, url) in enumerate(NAV_LINKS)
    )
    navbar_html = f"""
    <nav class="vs-navbar">
      <div class="vs-nav-links">{links_html}</div>
    </nav>
    """
    st.markdown(navbar_html, unsafe_allow_html=True)


def render_hero(title: str, subtitle: str | None = None) -> None:
    """Display a full-width hero banner with ``title`` and optional ``subtitle``."""

    subtitle_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <section class="vs-hero">
            <h1>{title}</h1>
            {subtitle_html}
        </section>
        """,
        unsafe_allow_html=True,
    )
