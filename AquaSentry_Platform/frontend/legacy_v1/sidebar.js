/**
 * AquaSentry — Primary Navigation Rail & Drawer Controller (Items 314, 318, 326–329, 353)
 *
 * Implements:
 * - 8 Stable Primary Destinations: Overview, Readings, Map, Devices, Contaminants, Analytics, Reports, Methods.
 * - Consistent 20x20 monochromatic SVG line icons (no emojis).
 * - Active state with pale teal surface and teal left indicator.
 * - Escape key dismissal and full keyboard accessibility.
 */

(function () {
  'use strict';

  const SIDEBAR_HTML = `
    <!-- Sidebar Backdrop -->
    <div id="sidebarBackdrop" class="sidebar-backdrop" onclick="toggleSidebar(false)" aria-hidden="true"></div>

    <!-- Primary Navigation Drawer -->
    <aside id="appSidebar" class="app-sidebar" aria-label="Main Navigation">
      <div class="sidebar-header">
        <a href="index.html" class="sidebar-brand">
          <div class="sidebar-logo-icon">
            <svg viewBox="0 0 32 32" width="28" height="28" fill="none">
              <path d="M 5 21 A 13 13 0 1 1 27 21" stroke="#087E8B" stroke-width="1.75" stroke-linecap="round" stroke-opacity="0.4"/>
              <path d="M 8.5 21 A 9.5 9.5 0 1 1 23.5 21" stroke="#087E8B" stroke-width="1.75" stroke-linecap="round" stroke-opacity="0.75"/>
              <circle cx="23.5" cy="8.5" r="1.5" fill="#18AEB0"/>
              <path d="M 16 7 C 16 7 11.5 13.5 11.5 17.5 A 4.5 4.5 0 0 0 20.5 17.5 C 20.5 13.5 16 7 16 7 Z" fill="#087E8B"/>
              <path d="M 10 24.5 L 22 24.5" stroke="#087E8B" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <div class="sidebar-brand-text">
            <span class="sidebar-brand-name">Aqua<span class="brand-teal">Sentry</span></span>
            <span class="sidebar-station-tag">Field Monitor</span>
          </div>
        </a>
        <button class="sidebar-close-btn" onclick="toggleSidebar(false)" aria-label="Close navigation menu">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>

      <nav class="sidebar-scroll" aria-label="Primary destinations">
        <div class="sidebar-group">
          <div class="sidebar-group-title">MONITORING DESTINATIONS</div>

          <a href="index.html#section-overview" class="sidebar-link active" data-dest="overview">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            <span class="sidebar-link-title">Overview</span>
          </a>

          <a href="index.html#section-readings" class="sidebar-link" data-dest="readings">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            <span class="sidebar-link-title">Readings &amp; Samples</span>
          </a>

          <a href="index.html#section-map" class="sidebar-link" data-dest="map">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon><line x1="8" y1="2" x2="8" y2="18"></line><line x1="16" y1="6" x2="16" y2="22"></line></svg>
            <span class="sidebar-link-title">Geospatial Map</span>
          </a>

          <a href="index.html#section-devices" class="sidebar-link" data-dest="devices">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>
            <span class="sidebar-link-title">Devices &amp; Fleet</span>
          </a>

          <a href="index.html#section-contaminants" class="sidebar-link" data-dest="contaminants">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path><line x1="2" y1="12" x2="22" y2="12"></line></svg>
            <span class="sidebar-link-title">Contaminants &amp; Matrix</span>
          </a>

          <a href="index.html#section-analytics" class="sidebar-link" data-dest="analytics">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
            <span class="sidebar-link-title">Analytics &amp; AquaNet Model</span>
          </a>

          <a href="index.html#section-reports" class="sidebar-link" data-dest="reports">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
            <span class="sidebar-link-title">Reports &amp; Export</span>
          </a>

          <a href="index.html#section-methods" class="sidebar-link" data-dest="methods">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            <span class="sidebar-link-title">Methods &amp; Limitations</span>
          </a>

          <a href="index.html#section-roi" class="sidebar-link" data-dest="roi">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"></rect><line x1="6" y1="8" x2="10" y2="8"></line><line x1="6" y1="12" x2="18" y2="12"></line><line x1="6" y1="16" x2="14" y2="16"></line></svg>
            <span class="sidebar-link-title">District ROI Calculator</span>
          </a>

          <a href="index.html#section-sales" class="sidebar-link" data-dest="commercial">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
            <span class="sidebar-link-title">Commercial &amp; Procurement</span>
          </a>

          <a href="index.html#section-competition" class="sidebar-link" data-dest="competition">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
            <span class="sidebar-link-title">Benchmark Matrix</span>
          </a>

          <a href="index.html#section-market" class="sidebar-link" data-dest="market-tam">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
            <span class="sidebar-link-title">Market TAM &amp; Hotspots</span>
          </a>
        </div>

        <div class="sidebar-group">
          <div class="sidebar-group-title">RESEARCH &amp; COMMERCIAL</div>

          <a href="sales-expansion.html" class="sidebar-link external-link" data-dest="sales">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
            <span class="sidebar-link-title">Commercial &amp; Jal Jeevan</span>
            <span class="sidebar-badge">B2B</span>
          </a>

          <a href="market-research.html" class="sidebar-link external-link" data-dest="market">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>
            <span class="sidebar-link-title">Global Hotspots &amp; Benchmarks</span>
            <span class="sidebar-badge">Data</span>
          </a>

          <a href="styleguide.html" class="sidebar-link external-link" data-dest="styleguide">
            <svg class="sidebar-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>
            <span class="sidebar-link-title">UI Component Gallery</span>
            <span class="sidebar-badge">Docs</span>
          </a>
        </div>
      </nav>

      <div class="sidebar-footer">
        <div class="theme-switch-row">
          <span class="theme-label">Theme:</span>
          <button id="themeToggleBtn" class="theme-toggle-btn" onclick="toggleTheme()" aria-label="Toggle Light and Dark Theme">
            <span id="themeToggleLabel">Light Mode</span>
          </button>
        </div>
        <div class="prototype-notice-foot">
          <span>Field Screening Prototype · Non-Certified</span>
        </div>
      </div>
    </aside>
  `;

  // Inject sidebar into page
  function initSidebar() {
    if (!document.getElementById('appSidebar')) {
      const container = document.createElement('div');
      container.id = 'sidebarContainer';
      container.innerHTML = SIDEBAR_HTML;
      document.body.appendChild(container);
    }
    highlightCurrentDestination();
    initTheme();
  }

  window.toggleSidebar = function (open) {
    const sidebar = document.getElementById('appSidebar');
    const backdrop = document.getElementById('sidebarBackdrop');
    if (!sidebar || !backdrop) return;

    const isOpen = open !== undefined ? open : !sidebar.classList.contains('open');
    sidebar.classList.toggle('open', isOpen);
    backdrop.classList.toggle('visible', isOpen);
    document.body.classList.toggle('sidebar-locked', isOpen);

    if (isOpen) {
      window.AquaAudio && window.AquaAudio.playConfirmation && window.AquaAudio.playConfirmation();
      const firstLink = sidebar.querySelector('.sidebar-link');
      if (firstLink) firstLink.focus();
    }
  };

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      window.toggleSidebar(false);
    }
  });

  // Highlight navigation item based on current page / hash
  function highlightCurrentDestination() {
    const currentHash = window.location.hash || '#section-overview';
    const currentPath = window.location.pathname;

    document.querySelectorAll('.sidebar-link').forEach((link) => {
      link.classList.remove('active');
      const href = link.getAttribute('href') || '';
      if (href.startsWith('#') && href === currentHash) {
        link.classList.add('active');
      } else if (href.includes(currentPath.split('/').pop() || 'index.html') && !href.includes('#')) {
        link.classList.add('active');
      }
    });
  }

  window.addEventListener('hashchange', highlightCurrentDestination);

  // Theme Management: Cyber-Ocean Dark default
  window.toggleTheme = function () {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('aquaSentryTheme', next);
    updateThemeLabel();
  };

  function initTheme() {
    const saved = localStorage.getItem('aquaSentryTheme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeLabel();
  }

  function updateThemeLabel() {
    const theme = document.documentElement.getAttribute('data-theme') || 'dark';
    const label = document.getElementById('themeToggleLabel');
    if (label) {
      label.textContent = theme === 'dark' ? 'Cyber Ocean' : 'Light Theme';
    }
  }

  document.addEventListener('DOMContentLoaded', initSidebar);
})();
