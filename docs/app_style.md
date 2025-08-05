
# Streamlit App Integration Guidelines

## Objective
Bring the Streamlit NDVI explorer into `app.verdesat.com` with visual consistency to the main VerdeSat landing page.

## Landing Page Design Summary
- **Fonts:** Inter for body text and Montserrat for headings, loaded from Google Fonts.
- **Color palette:**
  - Forest Green `#2B6E3F`
  - Midnight Navy `#14213D`
  - Forest `#134E4A`
  - Mint `#6EE7B7`
  - Sky Blue `#8DC8E8`
  - White `#FFFFFF`
- **Hero imagery:** Uses `hero-sat-screen.webp` with a dark green gradient overlay.

## Recommendations for Streamlit
1. **Configure theme**, e.g., in `.streamlit/config.toml`:
   ```toml
   [theme]
   primaryColor = "#2B6E3F"
   backgroundColor = "#FFFFFF"
   secondaryBackgroundColor = "#14213D"
   textColor = "#14213D"
   font = "sans serif"
   ```
2. **Load fonts** e.g., in `app.py`:
   ```python
   st.markdown(
       """
       <style>
       @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Montserrat:wght@400;600;700&display=swap');
       html, body, [class*='css']  {
           font-family: 'Inter', sans-serif;
       }
       h1, h2, h3, h4, h5 {
           font-family: 'Montserrat', sans-serif;
           font-weight: 600;
       }
       </style>
       """,
       unsafe_allow_html=True,
   )
   ```
3. **Navigation/header**: replicate the fixed navbar with the leaf logo and links to sections. Use `st.markdown` to inject HTML/CSS. Logo URL: `https://www.verdesat.com/favicon.svg`.
4. **Hero section**: create a full-width banner using `https://www.verdesat.com/images/hero-sat-screen.webp` and overlay gradient `linear-gradient(180deg, rgba(19,78,74,0.5), rgba(19,78,74,0.5) 50%, #134E4A)`.
5. **Buttons**: style primary actions with Forest Green background and rounded-full edges; use Mint text accents for highlights. Demo link: `https://calendly.com/andreydara/meet-verdesat`. Sample report: `https://www.verdesat.com/sample-report.pdf`.
6. **Hide Streamlit chrome**:
   ```python
   st.markdown(
       """
       <style>
       #MainMenu {visibility: hidden;}
       footer {visibility: hidden;}
       header {visibility: hidden;}
       </style>
       """,
       unsafe_allow_html=True,
   )
   ```
7. **Section backgrounds**: for content blocks, alternate white and light gray (`#F8F9FA`) backgrounds to mirror landing page sections.

## Image & Asset Links
- Logo: `https://www.verdesat.com/favicon.svg`
- Hero background: `https://www.verdesat.com/images/hero-sat-screen.webp`
or in docs/site_imgs
Make a decision where to store all those (maybe (../verdesat/webapp/themes)?).