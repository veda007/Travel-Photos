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
def tripadvisor_search(query: str, max_results: int = 10):
    api_key = st.secrets.get("TRIPADVISOR_API_KEY") or os.environ.get("TRIPADVISOR_API_KEY")
    if not api_key:
        raise RuntimeError("Missing TRIPADVISOR_API_KEY (Streamlit secret or env var)")

    headers = {
        "accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    # Step 1: Search for locations
    search_url = "https://api.content.tripadvisor.com/api/v1/location/search"
    search_params = {
        "key": api_key,
        "searchQuery": query,
        "language": "en"
    }
    search_resp = requests.get(search_url, headers=headers, params=search_params, timeout=15)
    search_resp.raise_for_status()
    search_data = search_resp.json()

    if not search_data.get("data"):
        return []

    # Step 2: Get photos for the first location
    location_id = search_data["data"][0]["location_id"]
    photos_url = f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/photos"
    photos_params = {
        "key": api_key,
        "language": "en"
    }
    photos_resp = requests.get(photos_url, headers=headers, params=photos_params, timeout=15)
    photos_resp.raise_for_status()
    photos_data = photos_resp.json()

    return photos_data.get("data", [])[:max_results]


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


def extract_ta_original_url(photo: dict) -> str | None:
    images = photo.get("images")
    if not images:
        return None
    # If API returns dict of sizes
    if isinstance(images, dict):
        original = images.get("original") or images.get("large") or images.get("medium") or images.get("small")
        if isinstance(original, dict):
            return original.get("url")
        if isinstance(original, str):
            return original
        # Fallback: any dict value with url
        for v in images.values():
            if isinstance(v, dict) and v.get("url"):
                return v.get("url")
    # If API returns a list of image objects
    if isinstance(images, list):
        # Prefer the largest resolution if width/height available
        sorted_imgs = sorted(
            images,
            key=lambda x: (x.get("width", 0) or 0) * (x.get("height", 0) or 0),
            reverse=True,
        )
        for item in sorted_imgs:
            url = item.get("url") or (item.get("source") or {}).get("url")
            if url:
                return url
    return None


def extract_ta_all_urls(photo: dict) -> list[str]:
    urls: list[str] = []
    images = photo.get("images")
    if not images:
        return urls
    if isinstance(images, dict):
        for v in images.values():
            if isinstance(v, dict) and v.get("url"):
                urls.append(v["url"])
            elif isinstance(v, str):
                urls.append(v)
    elif isinstance(images, list):
        for item in images:
            url = item.get("url") or (item.get("source") or {}).get("url")
            if url:
                urls.append(url)
    # Dedupe preserving order
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
    return unique_urls


st.title("Place Photo Finder")
st.markdown("Type a place and view images from Pexels, Wikipedia, and TripAdvisor.")

with st.form("search_form"):
    query = st.text_input("Search a place", value="Eiffel Tower", placeholder="Eiffel Tower")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    with st.spinner("Fetching images…"):
        pexels = []
        wiki = []
        tripadvisor = []
        pexels_error = None
        wiki_error = None
        ta_error = None
        try:
            pexels = pexels_search(q, per_page=5)
        except Exception as e:
            pexels_error = str(e)
        try:
            wiki = wikipedia_images(q, max_images=10)
        except Exception as e:
            wiki_error = str(e)
        try:
            tripadvisor = tripadvisor_search(q, max_results=10)
        except Exception as e:
            ta_error = str(e)

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

    st.markdown("---")
    st.subheader("TripAdvisor (10)")
    if ta_error:
        st.warning(f"TripAdvisor error: {ta_error}")
    if not tripadvisor:
        st.info("No TripAdvisor images")
    else:
        for idx, photo in enumerate(tripadvisor[:10]):
            with st.expander(f"Photo {idx+1} - {photo.get('caption', 'No caption')}"):
                # Original image (best available)
                original_url = extract_ta_original_url(photo)
                if original_url:
                    st.image(original_url, use_column_width=True, caption="Original")
                # All variants under images[]
                all_urls = extract_ta_all_urls(photo)
                if all_urls:
                    st.write("Variants:")
                    cols = st.columns(5)
                    for n, u in enumerate(all_urls[:10]):
                        with cols[n % 5]:
                            st.image(u, use_column_width=True)

