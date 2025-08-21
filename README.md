# Place Photo Finder

A web app that searches Pexels for a place (e.g., "Eiffel Tower") and shows 5 photos.

## Features
- Clean, responsive UI (no frameworks)
- 5 results with photographer credits
- Streamlit version with Pexels + Wikipedia images

## Run locally

### Static version
- Open `index.html` directly, or
- Serve the folder with any static server, e.g.:

```bash
python3 -m http.server 5173
# open http://localhost:5173
```

The API key is set in `index.html` as `window.PEXELS_API_KEY`.

### Streamlit app
```bash
pip3 install -r requirements.txt
export PEXELS_API_KEY="<your_key>"
streamlit run streamlit_app.py
# open http://localhost:8501
```

## Deploy

### Streamlit Cloud (recommended)
- Push this folder to a GitHub repo
- On Streamlit Cloud, create a new app pointing to `streamlit_app.py`
- Add a secret `PEXELS_API_KEY` in the app settings

### Static hosting
- GitHub Pages: Push to a repo and enable Pages
- Netlify: Drag and drop the folder

## Note
The static version exposes the Pexels API key in the browser. For production, use the Streamlit version with server-side secrets.