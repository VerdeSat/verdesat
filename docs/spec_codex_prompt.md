<file name=verdesat/webapp/themes/spec_codex_prompt.md># VerdeSat Streamlit UI/UX Implementation Prompt for Codex

You are a senior frontend developer integrating a Streamlit app into the visual identity of the VerdeSat platform. The goal is to match the look and feel of https://www.verdesat.com while delivering a clean, responsive, and visually coherent user experience under https://app.verdesat.com.

---

## 🎯 Objectives

- Integrate design tokens from `docs/app_style.md` into the Streamlit UI.
- Apply a consistent visual language: whitespace, layout, color, and typography.
- Ensure the Streamlit UI feels native to the existing website’s branding.

---

## 🎨 Visual Style Guide

- **Fonts**
  - Inter for all body text.
  - Montserrat for all headings.
  - Load from Google Fonts (include preconnect).

- **Colors**
  - Forest Green: `#2B6E3F` (primary)
  - Midnight Navy: `#14213D` (header/footer bg, text)
  - Forest: `#134E4A` (banner overlay)
  - Mint: `#6EE7B7` (accent, hover states)
  - Sky Blue: `#8DC8E8` (secondary highlight)
  - White: `#FFFFFF`
  - Light Gray: `#F8F9FA` (section alt backgrounds)

- **Hero Banner**
  - Full-width image: `https://www.verdesat.com/images/hero-sat-screen.webp`
  - Overlay: `linear-gradient(180deg, rgba(19,78,74,0.5), rgba(19,78,74,0.5) 50%, #134E4A)`

- **Buttons**
  - Forest Green background
  - Rounded full (border-radius: 9999px)
  - Mint text on hover

---

## ✅ Functional Checklist

- [ ] Hide Streamlit chrome (header, footer, hamburger).
- [ ] Add fixed top navbar with logo (`https://www.verdesat.com/favicon.svg`) and 3 links: Home, Demo, Docs.
- [ ] Add hero banner as a top section under navbar.
- [ ] Apply theme colors to all UI elements.
- [ ] Set consistent margins, padding, and spacing (e.g., 1.5–2rem).
- [ ] Alternate content section backgrounds (#FFFFFF / #F8F9FA).
- [ ] All injected HTML/CSS must be `unsafe_allow_html=True`.
- [ ] Ensure responsiveness on mobile and desktop.

---