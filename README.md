# Place Photo Finder (Pexels)

A minimal, beautiful, static web app that searches Pexels for a place (e.g., "Eiffel Tower") and shows 5 photos.

## Features
- Clean, responsive UI (no frameworks)
- 5 results with photographer credits
- Deployable as a plain static site (GitHub Pages / Netlify / Vercel)

## Run locally
- Open `index.html` directly, or
- Serve the folder with any static server, e.g.:

```bash
python3 -m http.server 5173
# open http://localhost:5173
```

The API key is set in `index.html` as `window.PEXELS_API_KEY`.

### Streamlit app (alternative)
```bash
pip3 install -r requirements.txt
export PEXELS_API_KEY="<your_key>"
streamlit run streamlit_app.py
# open http://localhost:8501
```

## Deploy
- Vercel (recommended: includes serverless API):
  1) Install Vercel CLI: `npm i -g vercel`
  2) From this folder, run: `vercel` and follow prompts
  3) For prod: `vercel --prod`
  The API endpoint will be `/api/tripadvisor`.
- Netlify: You can deploy static files easily, but the TripAdvisor API route requires a serverless function rewrite. Consider Vercel for the built-in function here.
- GitHub Pages: Only the static UI will work (Pexels). The TripAdvisor endpoint will not be available on Pages without a custom backend.

### Streamlit Cloud deploy
- Push this folder to a GitHub repo
- On Streamlit Cloud, create a new app pointing to `streamlit_app.py`
- Add a secret `PEXELS_API_KEY` in the app settings

## Note
This demo exposes the Pexels API key in the browser for convenience. For production, proxy calls via a lightweight server to keep the key private.