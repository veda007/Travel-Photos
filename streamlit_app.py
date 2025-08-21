import os
import requests
import streamlit as st

st.set_page_config(page_title="Place Photo Finder", page_icon="📷", layout="wide")

# Dark theme + UI polish
st.markdown(
    """
    <style>
      .stApp { background: #0b0f17; color: #e6edf3; }
      .block-container { padding-top: 2rem; padding-bottom: 4rem; }
      h1, h2, h3 { color: #e6edf3; }
      .subhead { color: #a4b1c4; margin-top: -6px; }
      .image-card img { border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.35); }
      .section-divider { margin: 18px 0 8px; border: 0; height: 1px; background: rgba(255,255,255,0.08); }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(ttl=3600)
def tripadvisor_search(query: str, max_results: int = 5):
    api_key = st.secrets.get("TRIPADVISOR_API_KEY") or os.environ.get("TRIPADVISOR_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TRIPADVISOR_API_KEY (Streamlit secret or env var)")

    app_origin = st.secrets.get("TA_REFERER") or os.environ.get("TA_REFERER")
    headers = {
        "accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if app_origin:
        headers["Referer"] = app_origin
        headers["Origin"] = app_origin

    # Search locations for the query (restrict to attractions)
    search_url = "https://api.content.tripadvisor.com/api/v1/location/search"
    search_params = {"key": api_key, "searchQuery": query, "language": "en", "category": "attractions"}
    search_resp = requests.get(search_url, headers=headers, params=search_params, timeout=15)
    search_resp.raise_for_status()
    search_data = search_resp.json()
    locations = (search_data.get("data") or [])
    if not locations:
        return []

    # Pick ONLY the first location and fetch up to 5 photos
    first_loc_id = locations[0].get("location_id")
    if not first_loc_id:
        return []

    photos_url = f"https://api.content.tripadvisor.com/api/v1/location/{first_loc_id}/photos"
    photos_params = {"key": api_key, "language": "en", "limit": 5}
    photos_resp = requests.get(photos_url, headers=headers, params=photos_params, timeout=15)
    photos_resp.raise_for_status()
    photos_data = photos_resp.json()
    return (photos_data.get("data") or [])[:5]

# Helpers to extract TripAdvisor image URLs

def extract_ta_original_url(photo: dict):
    images = photo.get("images")
    if not images:
        return None
    if isinstance(images, dict):
        original = images.get("original") or images.get("large") or images.get("medium") or images.get("small")
        if isinstance(original, dict):
            return original.get("url")
        if isinstance(original, str):
            return original
        for v in images.values():
            if isinstance(v, dict) and v.get("url"):
                return v.get("url")
    if isinstance(images, list):
        # Prefer largest resolution if available
        sorted_imgs = sorted(images, key=lambda x: (x.get("width", 0) or 0) * (x.get("height", 0) or 0), reverse=True)
        for item in sorted_imgs:
            url = item.get("url") or (item.get("source") or {}).get("url")
            if url:
                return url
    return None

st.title("TripAdvisor Photo Finder")
st.markdown('<p class="subhead">Type a place to view original photos from TripAdvisor.</p>', unsafe_allow_html=True)

with st.form("search_form"):
    query = st.text_input("Search a place", value="Eiffel Tower", placeholder="Eiffel Tower")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    with st.spinner("Fetching images…"):
        ta_error = None
        try:
            tripadvisor = tripadvisor_search(q, max_results=5)
        except Exception as e:
            ta_error = str(e)
            tripadvisor = []

    st.markdown("### TripAdvisor")
    if ta_error:
        st.warning(f"TripAdvisor error: {ta_error}")
    if not tripadvisor:
        st.info("No TripAdvisor images")
    else:
        original_urls = []
        for p in tripadvisor:
            u = extract_ta_original_url(p)
            if u:
                original_urls.append(u)
        if not original_urls:
            st.info("No original images found from TripAdvisor")
        else:
            cols = st.columns(5)
            for i, url in enumerate(original_urls):
                with cols[i % 5]:
                    st.image(url, use_column_width=True)

