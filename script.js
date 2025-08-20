(() => {
  const API_KEY = (typeof window !== 'undefined' && window.PEXELS_API_KEY) || '';

  const elements = {
    form: document.getElementById('search-form'),
    input: document.getElementById('search-input'),
    status: document.getElementById('status'),
    results: document.getElementById('results'),
    taResults: document.getElementById('ta-results'),
  };

  function setStatus(message, tone = 'info') {
    if (!elements.status) return;
    elements.status.textContent = message || '';
    elements.status.dataset.tone = tone;
  }

  function clearResults() {
    if (!elements.results) return;
    elements.results.innerHTML = '';
    if (elements.taResults) elements.taResults.innerHTML = '';
  }

  function renderSkeleton(count) {
    clearResults();
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < count; i += 1) {
      const card = document.createElement('div');
      card.className = 'photo-card';

      const thumb = document.createElement('div');
      thumb.className = 'thumb skeleton';
      thumb.style.aspectRatio = '4 / 3';

      const meta = document.createElement('div');
      meta.className = 'photo-meta';
      meta.innerHTML = '<div class="byline skeleton" style="height: 14px; width: 60%; border-radius: 6px;"></div>';

      card.appendChild(thumb);
      card.appendChild(meta);
      fragment.appendChild(card);
    }
    elements.results.appendChild(fragment);
  }

  function createPhotoCard(photo) {
    const card = document.createElement('article');
    card.className = 'photo-card';

    const link = document.createElement('a');
    link.href = photo.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'thumb';

    const img = document.createElement('img');
    img.src = photo.src.large2x || photo.src.large || photo.src.medium || photo.src.original;
    img.loading = 'lazy';
    img.alt = `Photo of ${photo.alt || 'place'} by ${photo.photographer}`;

    link.appendChild(img);

    const meta = document.createElement('div');
    meta.className = 'photo-meta';

    const byline = document.createElement('div');
    byline.className = 'byline';
    const photographerLink = document.createElement('a');
    photographerLink.href = photo.photographer_url;
    photographerLink.target = '_blank';
    photographerLink.rel = 'noopener noreferrer';
    photographerLink.textContent = `By ${photo.photographer}`;
    byline.appendChild(photographerLink);

    const actions = document.createElement('div');
    actions.className = 'photo-actions';

    const download = document.createElement('a');
    download.href = photo.src.original;
    download.target = '_blank';
    download.rel = 'noopener noreferrer';
    download.className = 'icon-btn';
    download.textContent = 'Open';

    actions.appendChild(download);
    meta.appendChild(byline);
    meta.appendChild(actions);

    card.appendChild(link);
    card.appendChild(meta);
    return card;
  }

  function enhanceQueryForCinematic(baseQuery) {
    // No longer altering the user's query to avoid irrelevant results.
    return baseQuery;
  }

  async function searchPhotos(query) {
    if (!API_KEY) {
      throw new Error('Missing Pexels API key. Define window.PEXELS_API_KEY.');
    }
    const url = new URL('https://api.pexels.com/v1/search');
    const cinematicQuery = enhanceQueryForCinematic(query);
    url.searchParams.set('query', cinematicQuery);
    url.searchParams.set('per_page', '50');

    const response = await fetch(url.toString(), {
      headers: { Authorization: API_KEY },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Request failed (${response.status}): ${text || 'Unknown error'}`);
    }

    const data = await response.json();
    const photos = Array.isArray(data.photos) ? data.photos : [];
    // Prefer high-resolution photos without forcing orientation
    const filtered = photos
      .filter((p) => {
        const isLarge = p.width >= 2000 && p.height >= 1200;
        return isLarge;
      })
      .sort((a, b) => b.width * b.height - a.width * a.height);

    // Fallback if too few after filtering
    if (filtered.length >= 5) return filtered.slice(0, 5);
    const fallback = photos
      .filter((p) => true)
      .sort((a, b) => b.width * b.height - a.width * a.height)
      .slice(0, Math.max(5, filtered.length));
    return (filtered.concat(fallback).slice(0, 5));
  }

  async function searchTripAdvisorImages(query) {
    const url = new URL('/api/tripadvisor', window.location.origin);
    url.searchParams.set('q', query);
    const res = await fetch(url.toString());
    if (!res.ok) {
      throw new Error('TripAdvisor fetch failed');
    }
    const data = await res.json();
    return Array.isArray(data.images) ? data.images : [];
  }

  async function handleSearch(query) {
    const trimmed = String(query || '').trim();
    if (!trimmed) return;

    setStatus('Searching photos…');
    renderSkeleton(5);

    try {
      const [photos, taPhotos] = await Promise.all([
        searchPhotos(trimmed),
        searchTripAdvisorImages(trimmed).catch(() => []),
      ]);
      clearResults();
      if (!photos.length) {
        elements.results.innerHTML = '<div class="empty">No results. Try a different place.</div>';
        setStatus('');
        // continue to show TA if available
      }

      const fragment = document.createDocumentFragment();
      photos.forEach((p) => fragment.appendChild(createPhotoCard(p)));
      elements.results.appendChild(fragment);
      setStatus(`Showing ${photos.length} photo${photos.length === 1 ? '' : 's'} for “${trimmed}”.`);

      if (elements.taResults) {
        if (!taPhotos.length) {
          elements.taResults.innerHTML = '<div class="empty">No TripAdvisor images found.</div>';
        } else {
          const frag2 = document.createDocumentFragment();
          taPhotos.slice(0, 10).forEach((img) => {
            const card = document.createElement('article');
            card.className = 'photo-card';
            const a = document.createElement('a');
            a.href = img.src;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.className = 'thumb';
            const im = document.createElement('img');
            im.src = img.src;
            im.alt = img.alt || 'TripAdvisor image';
            im.loading = 'lazy';
            a.appendChild(im);
            card.appendChild(a);
            frag2.appendChild(card);
          });
          elements.taResults.appendChild(frag2);
        }
      }
    } catch (err) {
      clearResults();
      elements.results.innerHTML = `<div class="empty">${(err && err.message) || 'Something went wrong.'}</div>`;
      setStatus('');
    }
  }

  // suggestions removed

  function wireEvents() {
    elements.form.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSearch(elements.input.value);
    });

    // suggestions removed

    // On first load: show Eiffel Tower as a friendly default
    const defaultQuery = 'Eiffel Tower';
    elements.input.value = defaultQuery;
    handleSearch(defaultQuery);
  }

  // Init
  document.addEventListener('DOMContentLoaded', wireEvents);
})();

