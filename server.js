'use strict';

const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 5173;

app.use(express.static(__dirname));

function buildTripAdvisorSearchUrl(query) {
  const q = encodeURIComponent(query);
  // Use TripAdvisor search endpoint; results structure can change over time.
  return `https://www.tripadvisor.com/Search?q=${q}`;
}

async function fetchTripAdvisorImages(query, max = 10) {
  const url = buildTripAdvisorSearchUrl(query);
  const res = await axios.get(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Upgrade-Insecure-Requests': '1',
    },
    timeout: 15000,
  });

  const $ = cheerio.load(res.data);

  // Step 1: find the first attraction/place link from search results
  let placeHref = null;
  // Try multiple selectors as TA may change DOM structure
  const candidateLinks = new Set();
  $('a').each((_, a) => {
    const href = $(a).attr('href') || '';
    const text = ($(a).text() || '').toLowerCase();
    if (!href) return;
    // Heuristics: attraction pages contain 'Attraction_Review' or 'Attraction-g'
    if (/Attraction/.test(href) || /Attraction_Review/.test(href) || /-Activities-/.test(href)) {
      candidateLinks.add(href);
    }
    // Also allow links containing the query words
    if (text.includes(String(query).toLowerCase())) {
      candidateLinks.add(href);
    }
  });

  if (candidateLinks.size > 0) {
    placeHref = Array.from(candidateLinks)[0];
  }

  if (!placeHref) {
    // Fallback: return nothing
    return [];
  }

  const placeUrl = placeHref.startsWith('http') ? placeHref : `https://www.tripadvisor.com${placeHref}`;

  // Step 2: fetch the place page and extract image sources from TA media CDNs
  const res2 = await axios.get(placeUrl, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': url,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Upgrade-Insecure-Requests': '1',
    },
    timeout: 15000,
  });

  const $2 = cheerio.load(res2.data);
  const images = new Set();

  const accept = (src) => /media-cdn\.tripadvisor\.com|dynamic-media-cdn\.tripadvisor\.com/.test(src);

  $2('img').each((_, img) => {
    let src = $2(img).attr('src') || $2(img).attr('data-src') || '';
    const alt = $2(img).attr('alt') || '';
    if (!src) return;
    if (/data:image/.test(src)) return;
    if (!accept(src)) return;
    src = src.replace(/photo-s\//, 'photo-l/').replace(/\/-w\d+-h\d+\//, '/');
    images.add(JSON.stringify({ src, alt }));
  });

  const list = Array.from(images).slice(0, max).map((s) => JSON.parse(s));
  return list;
}

async function fetchWikipediaImages(query, max = 10) {
  // Step 1: find the top page title
  const search = await axios.get('https://en.wikipedia.org/w/api.php', {
    params: {
      action: 'query',
      list: 'search',
      srsearch: query,
      srlimit: 1,
      format: 'json',
      origin: '*',
    },
    timeout: 10000,
  });
  const top = search.data && search.data.query && search.data.query.search && search.data.query.search[0];
  if (!top) return [];

  // Step 2: list images on the page and get direct URLs
  const imgs = await axios.get('https://en.wikipedia.org/w/api.php', {
    params: {
      action: 'query',
      titles: top.title,
      generator: 'images',
      gimlimit: 50,
      prop: 'imageinfo',
      iiprop: 'url|mime',
      format: 'json',
      origin: '*',
    },
    timeout: 10000,
  });
  const pages = (imgs.data && imgs.data.query && imgs.data.query.pages) || {};
  const urls = Object.values(pages)
    .map((p) => (p.imageinfo && p.imageinfo[0] && p.imageinfo[0].url) || null)
    .filter(Boolean)
    .filter((u) => /\.(jpg|jpeg|png)$/i.test(u));
  return urls.slice(0, max).map((u) => ({ src: u, alt: `${top.title} (Wikipedia)` }));
}

app.get('/api/tripadvisor', async (req, res) => {
  const query = String(req.query.q || '').trim();
  if (!query) return res.status(400).json({ error: 'Missing q' });
  try {
    let imgs = [];
    try {
      imgs = await fetchTripAdvisorImages(query, 10);
    } catch (err) {
      console.error('TripAdvisor error:', err.response && err.response.status);
    }
    if (!imgs || imgs.length === 0) {
      const wiki = await fetchWikipediaImages(query, 10);
      return res.json({ images: wiki, fallback: 'wikipedia' });
    }
    res.json({ images: imgs });
  } catch (err) {
    console.error('Unhandled /api/tripadvisor error', err);
    res.status(500).json({ error: 'Failed to fetch TripAdvisor images' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});

