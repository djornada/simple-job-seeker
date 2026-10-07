// Content script for linkedin.com/jobs/*. Reads whatever job cards/detail
// pane are currently rendered — no navigation, no clicks, nothing sent to
// LinkedIn. Selectors are LinkedIn's unofficial DOM/class names and WILL
// drift; if a scan comes back empty, open devtools on a jobs page and
// update the selectors below.
(() => {
  const SELECTORS = {
    listCard: 'div.job-card-container, li[data-occludable-job-id]',
    cardTitle: '.job-card-list__title, .job-card-container__link, a[href*="/jobs/view/"]',
    cardCompany: '.job-card-container__primary-description, .artdeco-entity-lockup__subtitle',
    cardLocation: '.job-card-container__metadata-item, .artdeco-entity-lockup__caption',
    detailTitle: '.job-details-jobs-unified-top-card__job-title, h1.t-24',
    detailCompany: '.job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name',
    detailLocation: '.job-details-jobs-unified-top-card__primary-description-container, .jobs-unified-top-card__bullet',
    detailDescription: '.jobs-description__content, .jobs-box__html-content',
  };

  function cleanText(el) {
    return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  }

  function absoluteUrl(href) {
    try {
      const u = new URL(href, location.href);
      return u.origin + u.pathname; // drop tracking query params
    } catch {
      return '';
    }
  }

  function extractListCards() {
    const items = [];
    for (const card of document.querySelectorAll(SELECTORS.listCard)) {
      const titleEl = card.querySelector(SELECTORS.cardTitle);
      const title = cleanText(titleEl);
      const href = titleEl ? titleEl.closest('a')?.href || titleEl.href : '';
      const url = absoluteUrl(href || '');
      const company = cleanText(card.querySelector(SELECTORS.cardCompany));
      const location_ = cleanText(card.querySelector(SELECTORS.cardLocation));
      if (!title || !url || !company) continue;
      items.push({
        source: 'linkedin_jobs', title, company, url,
        location: location_, description: '',
      });
    }
    return items;
  }

  function extractDetailPane() {
    const titleEl = document.querySelector(SELECTORS.detailTitle);
    const companyEl = document.querySelector(SELECTORS.detailCompany);
    if (!titleEl || !companyEl) return null;
    const title = cleanText(titleEl);
    const company = cleanText(companyEl);
    if (!title || !company) return null;
    return {
      source: 'linkedin_jobs',
      title, company,
      url: absoluteUrl(location.href),
      location: cleanText(document.querySelector(SELECTORS.detailLocation)),
      description: cleanText(document.querySelector(SELECTORS.detailDescription)).slice(0, 20000),
    };
  }

  function extractItems() {
    const items = extractListCards();
    const detail = extractDetailPane();
    if (detail) items.push(detail);
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
