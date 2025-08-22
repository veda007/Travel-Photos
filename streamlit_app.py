import os
import requests
import streamlit as st
import json
from google import genai
from google.genai import types

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
      .attraction-title { color: #e6edf3; font-size: 1.2em; margin-bottom: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

@st.cache_data(ttl=3600)
def get_attractions_from_gemini(place_name: str):
    """
    Use Gemini 2.5 Flash Lite to generate top 10 attractions for a place.
    """
    try:
        # For Streamlit Cloud deployment, use service account credentials
        import json
        import tempfile
        
        # Get service account key from Streamlit secrets
        service_account_info = st.secrets.get("GOOGLE_APPLICATION_CREDENTIALS")
        
        if service_account_info:
            # Create temporary file with service account key
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(service_account_info, f)
                temp_key_file = f.name
            
            # Set environment variable
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = temp_key_file
            
            client = genai.Client(
                vertexai=True,
                project="glance-non-prod-af4d",
                location="global",
            )
        else:
            # Fallback to local development
            client = genai.Client(
                vertexai=True,
                project="glance-non-prod-af4d",
                location="global",
            )

        model = "gemini-2.5-flash-lite"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"""What are the top 10 attractions in {place_name}. Output only the list with attraction names with no other text or number added""")
                ]
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=65535,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="OFF"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="OFF"
                )
            ],
            response_mime_type="application/json",
            response_schema={"type": "OBJECT", "properties": {"response": {"type": "STRING"}}},
            thinking_config=types.ThinkingConfig(
                thinking_budget=0,
            ),
        )

        # Collect the full response
        full_response = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            full_response += chunk.text

        # Parse the JSON response
        try:
            import json
            response_data = json.loads(full_response)
            attractions_text = response_data.get("response", "")
        except json.JSONDecodeError:
            # If JSON parsing fails, use the raw response
            attractions_text = full_response

        # Extract attractions from the response
        attractions = extract_attractions_from_gemini_response(attractions_text)
        
        return attractions[:10]  # Return max 10 attractions
        
    except Exception as e:
        st.error(f"Error generating attractions with Gemini: {str(e)}")
        return None

def extract_attractions_from_gemini_response(text: str):
    """
    Extract attraction names from Gemini's response.
    """
    import re
    
    # Clean the text - remove quotes if present
    text = text.strip().strip('"').strip("'")
    
    # Try to extract numbered list with newlines (like "1. Blue Lagoon\n2. Golden Circle")
    numbered_pattern = r'\d+\.\s*([^\n]+)'
    numbered_matches = re.findall(numbered_pattern, text)
    
    if numbered_matches:
        attractions = [match.strip() for match in numbered_matches]
        # Filter out non-attraction items
        filtered = []
        for attraction in attractions:
            if len(attraction) > 3 and not attraction.lower().startswith(('the', 'a ', 'an ')):
                filtered.append(attraction)
        return filtered[:10]
    
    # Try to extract numbered list with commas (like "1. Eiffel Tower, 2. Louvre Museum")
    numbered_comma_pattern = r'\d+\.\s*([^,]+?)(?=,\s*\d+\.|$)'
    numbered_comma_matches = re.findall(numbered_comma_pattern, text)
    
    if numbered_comma_matches:
        attractions = [match.strip() for match in numbered_comma_matches]
        # Filter out non-attraction items
        filtered = []
        for attraction in attractions:
            if len(attraction) > 3 and not attraction.lower().startswith(('the', 'a ', 'an ')):
                filtered.append(attraction)
        return filtered[:10]
    
    # Try to extract bullet points
    bullet_pattern = r'[-*]\s*([^\n]+)'
    bullet_matches = re.findall(bullet_pattern, text)
    
    if bullet_matches:
        attractions = [match.strip() for match in bullet_matches]
        return attractions[:10]
    
    # Try to extract quoted items
    quoted_pattern = r'"([^"]+)"'
    quoted_matches = re.findall(quoted_pattern, text)
    
    if quoted_matches:
        return [match.strip() for match in quoted_matches][:10]
    
    # Fallback: split by common separators
    separators = ['\n', ',', ';', '-']
    for sep in separators:
        if sep in text:
            parts = text.split(sep)
            attractions = [part.strip() for part in parts if len(part.strip()) > 3]
            if attractions:
                return attractions[:10]
    
    return []

@st.cache_data(ttl=3600)
def search_attraction_on_tripadvisor(attraction_name: str):
    """
    Search for an attraction on TripAdvisor to get its location ID.
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
        search_url = "https://api.content.tripadvisor.com/api/v1/location/search"
        search_params = {
            "key": api_key, 
            "searchQuery": attraction_name, 
            "language": "en", 
            "category": "attractions",
            "limit": 1
        }
        search_resp = requests.get(search_url, headers=headers, params=search_params, timeout=15)
        search_resp.raise_for_status()
        search_data = search_resp.json()
        locations = (search_data.get("data") or [])
        
        if locations:
            return locations[0].get("location_id")
        return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"TripAdvisor search failed for {attraction_name}: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Unexpected error searching {attraction_name}: {str(e)}")
        return None

@st.cache_data(ttl=3600)
def get_images_for_attraction(location_id: str, limit: int = 3):
    """
    Get images for a specific attraction by location ID.
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
        photos_url = f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/photos"
        photos_params = {"key": api_key, "language": "en", "limit": limit}
        photos_resp = requests.get(photos_url, headers=headers, params=photos_params, timeout=15)
        photos_resp.raise_for_status()
        photos_data = photos_resp.json()
        photos = (photos_data.get("data") or [])[:limit]
        
        # Extract and return only image URLs
        image_urls = []
        for photo in photos:
            url = extract_ta_original_url(photo)
            if url:
                image_urls.append(url)
        
        return image_urls
        
    except requests.exceptions.RequestException as e:
        st.error(f"API request failed for location {location_id}: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Unexpected error for location {location_id}: {str(e)}")
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
st.markdown('<p class="subhead">Type a place to view top attractions and their photos</p>', unsafe_allow_html=True)

with st.form("search_form"):
    query = st.text_input("Search a place", value="Iceland", placeholder="Iceland")
    submitted = st.form_submit_button("Search")

if submitted and query.strip():
    q = query.strip()
    
    with st.spinner("Getting top attractions from Gemini AI..."):
        attractions = get_attractions_from_gemini(q)
    
    if attractions is None:
        st.error("Fetching attractions failed")
    elif not attractions:
        st.info(f"No attractions found for '{q}'")
    else:
        st.success(f"Found {len(attractions)} top attractions for '{q}'")
        
        # Display each attraction with its images
        for i, attraction_name in enumerate(attractions):
            st.markdown(f"### {i+1}. {attraction_name}")
            
            # Search for this attraction on TripAdvisor
            with st.spinner(f"Searching for {attraction_name}..."):
                location_id = search_attraction_on_tripadvisor(attraction_name)
            
            if location_id:
                # Get images for this attraction
                with st.spinner(f"Loading images for {attraction_name}..."):
                    image_urls = get_images_for_attraction(location_id, limit=3)
                
                if image_urls:
                    # Display images in 3 columns
                    cols = st.columns(3)
                    for j, url in enumerate(image_urls):
                        with cols[j % 3]:
                            st.image(url, use_column_width=True)
                else:
                    st.info(f"No images available for {attraction_name}")
            else:
                st.warning(f"Could not find {attraction_name} on TripAdvisor")
            
            # Add separator between attractions
            if i < len(attractions) - 1:
                st.markdown('<hr class="section-divider"/>', unsafe_allow_html=True)

