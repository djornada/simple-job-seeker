// Content script for linkedin.com/feed/*. Reads whatever posts are
// currently rendered on screen — no scrolling, no navigation, nothing
// sent to LinkedIn. Selectors are LinkedIn's unofficial DOM/class names
// and WILL drift; if a scan comes back empty, open devtools on the feed
// and update the selectors below.
//
// Feed posts don't carry a clean job title/company the way job cards do,
// so this is a best-effort extraction: the post author becomes `company`,
// the post text becomes `description`, and the first ~80 characters of
// that text become `title`. The server's résumé-fit judge (when a résumé
// is imported) is what actually makes sense of this; the plain keyword
// gate will reject most of it, same as it would for a board post with no
// clean title.
(() => {
  const SELECTORS = {
    post: 'div.feed-shared-update-v2[data-urn]',
    actorName: '.update-components-actor__name',
    text: '.update-components-text',
    permalink: 'a.app-aware-link[href*="/feed/update/"]',
  };

  function cleanText(el) {
    return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  }

  function permalinkFor(post) {
    const link = post.querySelector(SELECTORS.permalink);
    if (link && link.href) return link.href.split('?')[0];
    const urn = post.getAttribute('data-urn');
    return urn ? `https://www.linkedin.com/feed/update/${urn}/` : '';
  }

  function extractItems() {
    const items = [];
    for (const post of document.querySelectorAll(SELECTORS.post)) {
      const url = permalinkFor(post);
      const description = cleanText(post.querySelector(SELECTORS.text)).slice(0, 2000);
      const company = cleanText(post.querySelector(SELECTORS.actorName)).split('\n')[0].trim();
      if (!url || !description || !company) continue;
      items.push({
        source: 'linkedin_feed',
        title: description.slice(0, 80),
        company,
        url,
        location: '',
        description,
      });
    }
    const seen = new Set();
    return items.filter((it) => {
      if (seen.has(it.url)) return false;
      seen.add(it.url);
      return true;
    });
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg && msg.type === 'EXTRACT_ITEMS') {
      sendResponse({ items: extractItems() });
    }
  });
})();
