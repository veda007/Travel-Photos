import os
import urllib.parse
import requests
import streamlit as st


st.set_page_config(page_title="Place Photo Finder", page_icon="📷", layout="wide")


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
def wikipedia_images(query: str, max_images: int = 10):
    # Step 1: get best matching page title
    search = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 1,
            "format": "json",
            "origin": "*",
        },
        timeout=15,
    )
    search.raise_for_status()
    data = search.json()
    hits = (data.get("query") or {}).get("search") or []
    if not hits:
        return []
    title = hits[0]["title"]

    # Step 2: list images and resolve to direct URLs
    imgs = requests.get(
        "https://en.wikipedia.org/w/api.php",
        params={
            "action": "query",
            "titles": title,
            "generator": "images",
            "gimlimit": 50,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "format": "json",
            "origin": "*",
        },
        timeout=15,
    )
    imgs.raise_for_status()
    pages = (imgs.json().get("query") or {}).get("pages") or {}
    urls = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("url")
        if url and url.lower().endswith((".jpg", ".jpeg", ".png")):
            urls.append({"src": url, "alt": f"{title} (Wikipedia)"})
    return urls[:max_images]


def render_photo_card(image_url: str, caption: str = ""):
    st.image(image_url, use_column_width=True, caption=caption)


st.title("Place Photo Finder")
st.markdown("Type a place and view images from Pexels and Wikipedia.")

with st.form("search_form"):
    query = st.text_input("Search a place", value="Eiffel Tower", placeholder="Eiffel Tower")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    with st.spinner("Fetching images…"):
        pexels = []
        wiki = []
        pexels_error = None
        wiki_error = None
        try:
            pexels = pexels_search(q, per_page=5)
        except Exception as e:
            pexels_error = str(e)
        try:
            wiki = wikipedia_images(q, max_images=10)
        except Exception as e:
            wiki_error = str(e)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Pexels (5)")
        if pexels_error:
            st.warning(f"Pexels error: {pexels_error}")
        if not pexels:
            st.info("No Pexels results")
        else:
            grid_cols = st.columns(5)
            for idx, photo in enumerate(pexels[:5]):
                with grid_cols[idx % 5]:
                    src = (
                        photo.get("src", {}).get("large2x")
                        or photo.get("src", {}).get("large")
                        or photo.get("src", {}).get("medium")
                        or photo.get("src", {}).get("original")
                    )
                    cap = photo.get("photographer") or ""
                    if src:
                        render_photo_card(src, caption=cap)

    with col2:
        st.subheader("Wikipedia (10)")
        if wiki_error:
            st.warning(f"Wikipedia error: {wiki_error}")
        if not wiki:
            st.info("No Wikipedia images")
        else:
            grid_cols = st.columns(5)
            for idx, img in enumerate(wiki[:10]):
                with grid_cols[idx % 5]:
                    render_photo_card(img.get("src"), caption=img.get("alt", ""))

