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
def get_tripadvisor_images(query: str, limit: int = 3):
    """
    Server-side function that makes API calls and returns only image URLs.
    API key is never exposed to the client.
    """
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

    try:
        # Search locations for the query (attractions category)
        search_url = "https://api.content.tripadvisor.com/api/v1/location/search"
        search_params = {"key": api_key, "searchQuery": query, "language": "en", "category": "attractions"}
        search_resp = requests.get(search_url, headers=headers, params=search_params, timeout=15)
        search_resp.raise_for_status()
        search_data = search_resp.json()
        locations = (search_data.get("data") or [])
        
        if not locations:
            return []

        # Pick ONLY the first location and fetch up to `limit` photos
        first_loc_id = locations[0].get("location_id")
        if not first_loc_id:
            return []

        photos_url = f"https://api.content.tripadvisor.com/api/v1/location/{first_loc_id}/photos"
        photos_params = {"key": api_key, "language": "en", "limit": limit}
        photos_resp = requests.get(photos_url, headers=headers, params=photos_params, timeout=15)
        photos_resp.raise_for_status()
        photos_data = photos_resp.json()
        photos = (photos_data.get("data") or [])[:limit]
        
        # Extract and return only image URLs (no API key exposure)
        image_urls = []
        for photo in photos:
            url = extract_ta_original_url(photo)
            if url:
                image_urls.append(url)
        
        return image_urls
        
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return []

def extract_ta_original_url(photo: dict):
    """Helper function to extract image URLs from TripAdvisor photo data"""
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

st.title("Photo Finder")
st.markdown('<p class="subhead">Type an attraction to view original photos</p>', unsafe_allow_html=True)

with st.form("search_form"):
    query = st.text_input("Search an attraction", value="Eiffel Tower", placeholder="Eiffel Tower")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    with st.spinner("Fetching images…"):
        # Server-side API call - API key never exposed to client
        image_urls = get_tripadvisor_images(q, limit=3)

    # Display images (only URLs are sent to client)
    if not image_urls:
        st.info("No TripAdvisor images found")
    else:
        cols = st.columns(3)
        for i, url in enumerate(image_urls):
            with cols[i % 3]:
                st.image(url, use_column_width=True)

