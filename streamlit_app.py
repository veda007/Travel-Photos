import os
import io
import requests
import streamlit as st
from PIL import Image
import numpy as np
import torch
from torchvision import transforms
from transformers import CLIPProcessor, CLIPModel

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

# --- Image understanding with CLIP ---
_device = "cuda" if torch.cuda.is_available() else "cpu"
@st.cache_resource(show_spinner=False)
def load_clip():
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(_device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return model, processor

@st.cache_data(ttl=3600)
def score_images_with_clip(query: str, image_urls: list[str], threshold: float = 0.18) -> list[str]:
    if not image_urls:
        return []
    model, processor = load_clip()
    kept = []
    batch = []
    mapping = []
    # Process in small batches to save memory
    for idx, url in enumerate(image_urls):
        try:
            img = Image.open(io.BytesIO(requests.get(url, timeout=12).content)).convert("RGB")
            batch.append(img)
            mapping.append(url)
        except Exception:
            continue
        if len(batch) == 8 or idx == len(image_urls) - 1:
            inputs = processor(text=[query]*len(batch), images=batch, return_tensors="pt", padding=True).to(_device)
            with torch.no_grad():
                outputs = model(**inputs)
                # CLIP logits_per_image are similarity scores scaled; convert to probabilities
                probs = outputs.logits_per_image.softmax(dim=1)[:, 0].detach().cpu().numpy()
            for u, p in zip(mapping, probs):
                if float(p) >= threshold:
                    kept.append(u)
            batch, mapping = [], []
    return kept

@st.cache_data(ttl=3600)
def pexels_search(query: str, per_page: int = 5):
    api_key = st.secrets.get("PEXELS_API_KEY") or os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("Missing PEXELS_API_KEY (Streamlit secret or env var)")
    url = "https://api.pexels.com/v1/search"
    params = {"query": query, "per_page": per_page}
    resp = requests.get(url, headers={"Authorization": api_key}, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return data.get("photos", [])

@st.cache_data(ttl=3600)
def tripadvisor_search(query: str, max_results: int = 18):
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

    # Search locations for the query
    search_url = "https://api.content.tripadvisor.com/api/v1/location/search"
    search_params = {"key": api_key, "searchQuery": query, "language": "en"}
    search_resp = requests.get(search_url, headers=headers, params=search_params, timeout=15)
    search_resp.raise_for_status()
    search_data = search_resp.json()
    locations = (search_data.get("data") or [])
    if not locations:
        return []

    max_locations = min(len(locations), max_results, 10)
    locations = locations[:max_locations]

    def fetch_photos_for_location(loc_id: str, limit: int) -> list:
        photos_url = f"https://api.content.tripadvisor.com/api/v1/location/{loc_id}/photos"
        photos_params = {"key": api_key, "language": "en", "limit": limit}
        try:
            resp = requests.get(photos_url, headers=headers, params=photos_params, timeout=15)
            resp.raise_for_status()
        except requests.HTTPError:
            return []
        data = resp.json()
        return data.get("data", [])

    photos: list = []
    num_locations = len(locations)

    if num_locations >= max_results:
        for loc in locations[:max_results]:
            loc_id = loc.get("location_id")
            if not loc_id:
                continue
            imgs = fetch_photos_for_location(loc_id, limit=1)
            if imgs:
                photos.append(imgs[0])
        return photos

    base = max_results // num_locations
    rem = max_results % num_locations
    per_loc_counts = [base] * num_locations
    for i in range(rem):
        per_loc_counts[i] += 1

    for loc, count in zip(locations, per_loc_counts):
        loc_id = loc.get("location_id")
        if not loc_id or count <= 0:
            continue
        imgs = fetch_photos_for_location(loc_id, limit=count)
        if imgs:
            photos.extend(imgs[:count])
        if len(photos) >= max_results:
            break

    return photos[:max_results]

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
        sorted_imgs = sorted(images, key=lambda x: (x.get("width", 0) or 0) * (x.get("height", 0) or 0), reverse=True)
        for item in sorted_imgs:
            url = item.get("url") or (item.get("source") or {}).get("url")
            if url:
                return url
    return None

st.title("Place Photo Finder")
st.markdown('<p class="subhead">Search a place to view images from Pexels and TripAdvisor.</p>', unsafe_allow_html=True)

with st.form("search_form"):
    query = st.text_input("Search a place", value="Eiffel Tower", placeholder="Eiffel Tower")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    with st.spinner("Fetching images…"):
        pexels = []
        tripadvisor = []
        pexels_error = None
        ta_error = None
        try:
            pexels = pexels_search(q, per_page=10)
        except Exception as e:
            pexels_error = str(e)
        try:
            tripadvisor = tripadvisor_search(q, max_results=18)
        except Exception as e:
            ta_error = str(e)

    # Build URL lists
    pexels_urls = []
    for photo in pexels:
        src = (
            photo.get("src", {}).get("large2x")
            or photo.get("src", {}).get("large")
            or photo.get("src", {}).get("medium")
            or photo.get("src", {}).get("original")
        )
        if src:
            pexels_urls.append(src)

    ta_urls = []
    for p in tripadvisor:
        u = extract_ta_original_url(p)
        if u:
            ta_urls.append(u)

    # CLIP-based filtering against the text query
    kept_pexels = score_images_with_clip(q, pexels_urls, threshold=0.18)
    kept_ta = score_images_with_clip(q, ta_urls, threshold=0.18)

    # Pexels section
    st.markdown("### Pexels")
    if pexels_error:
        st.warning(f"Pexels error: {pexels_error}")
    if not kept_pexels:
        st.info("No Pexels results after AI matching")
    else:
        cols = st.columns(5)
        for i, url in enumerate(kept_pexels[:5]):
            with cols[i % 5]:
                st.image(url, use_column_width=True)

    st.markdown('<hr class="section-divider"/>', unsafe_allow_html=True)

    # TripAdvisor section
    st.markdown("### TripAdvisor")
    if ta_error:
        st.warning(f"TripAdvisor error: {ta_error}")
    if not kept_ta:
        st.info("No TripAdvisor images after AI matching")
    else:
        cols = st.columns(6)
        for i, url in enumerate(kept_ta):
            with cols[i % 6]:
                st.image(url, use_column_width=True)

