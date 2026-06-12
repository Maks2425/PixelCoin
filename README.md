# PixelCoin

Premium crypto banking landing page built with **Python (Flask)**, HTML, CSS, and vanilla JavaScript.

## Features

- Full-screen hero with pixel-art bank building, floating coin, and dashboard cards
- Glassmorphism feature and product cards with hover animations
- Live-style crypto market ticker (BTC, ETH, SOL, USDC, PXL)
- Dark theme (#050816) with neon purple and gold accents
- Fully responsive (desktop-first)
- Pixel-art inspired branding mixed with modern Web3 UI

## Getting Started

```bash
# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## Project Structure

```
app.py                      # Flask server
requirements.txt            # Python dependencies
templates/
  index.html                # Homepage
  partials/
    icons.html              # Pixel-art SVG macros
static/
  css/styles.css            # Styles & animations
  js/main.js                # Mobile menu & scroll reveal
```

## Tech Stack

- [Flask 3](https://flask.palletsprojects.com/)
- [Jinja2](https://jinja.palletsprojects.com/) templates
- Custom CSS (glassmorphism, gradients, animations)
- Google Fonts — Press Start 2P & Inter
