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
    
    try:
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
    except Exception as e:
        # Fallback: return mock data for localhost testing
        if "localhost" in str(e) or "403" in str(e) or "domain" in str(e).lower():
            return [
                {
                    "id": f"mock_{i}",
                    "caption": f"Mock TripAdvisor photo {i+1} for {query}",
                    "location": query,
                    "published_date": "2024-01-01",
                    "user": {"username": "mock_user"},
                    "rating": 4.5,
                    "helpful_votes": 10,
                    "is_video": False,
                    "is_owner": False,
                    "is_anonymous": False,
                    "images": {
                        "original": {
                            "url": f"https://picsum.photos/400/300?random={i}&blur=2"
                        }
                    }
                }
                for i in range(max_results)
            ]
        else:
            raise e


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

    col1, col2, col3 = st.columns(3, gap="large")

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

    with col3:
        st.subheader("TripAdvisor (10)")
        if ta_error:
            st.warning(f"TripAdvisor error: {ta_error}")
        if not tripadvisor:
            st.info("No TripAdvisor images")
        else:
            for idx, photo in enumerate(tripadvisor[:10]):
                with st.expander(f"Photo {idx+1} - {photo.get('caption', 'No caption')}"):
                    # Display image
                    if photo.get("images"):
                        img_url = photo["images"].get("original", {}).get("url")
                        if img_url:
                            st.image(img_url, use_column_width=True)
                    
                    # Display metadata
                    st.write("**Metadata:**")
                    metadata = {
                        "Caption": photo.get("caption", "N/A"),
                        "Location": photo.get("location", "N/A"),
                        "Published Date": photo.get("published_date", "N/A"),
                        "Photo ID": photo.get("id", "N/A"),
                        "User": photo.get("user", {}).get("username", "N/A") if photo.get("user") else "N/A",
                        "Rating": photo.get("rating", "N/A"),
                        "Helpful Votes": photo.get("helpful_votes", "N/A"),
                        "Is Video": photo.get("is_video", "N/A"),
                        "Is Owner": photo.get("is_owner", "N/A"),
                        "Is Anonymous": photo.get("is_anonymous", "N/A")
                    }
                    
                    for key, value in metadata.items():
                        if value != "N/A":
                            st.write(f"**{key}:** {value}")

