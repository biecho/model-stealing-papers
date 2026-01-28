/**
 * ML Security Papers - Main Application
 */

// State
let currentCategory = 'all';
let papers = [];
let categoryData = {};
let manifest = null;

/**
 * Load manifest file
 */
async function loadManifest() {
    try {
        const response = await fetch('data/manifest.json');
        manifest = await response.json();
        return manifest;
    } catch (error) {
        console.log('No manifest found');
        return null;
    }
}

/**
 * Load papers for a category
 */
async function loadCategoryPapers(categoryId) {
    const cat = CATEGORIES[categoryId];
    if (!cat) return [];

    try {
        const response = await fetch(`data/${cat.file}`);
        const data = await response.json();
        return data.papers || [];
    } catch (error) {
        console.log(`Could not load ${cat.file}`);
        return [];
    }
}

/**
 * Initialize the application
 */
async function initialize() {
    manifest = await loadManifest();

    if (manifest) {
        buildCategoryTabs();
        await loadAllCategories();
        showHubOverview();
    } else {
        document.getElementById('paper-list').innerHTML =
            '<div class="no-results">No papers found. Run classification first.</div>';
    }
}

/**
 * Build category navigation tabs
 */
function buildCategoryTabs() {
    const container = document.getElementById('category-tabs');

    for (const [id, cat] of Object.entries(CATEGORIES)) {
        const tab = document.createElement('div');
        tab.className = 'category-tab';
        tab.dataset.category = id;
        tab.innerHTML = `<span class="id">${id}</span><span class="count"></span>`;
        tab.style.borderColor = cat.color;
        tab.addEventListener('click', () => selectCategory(id));
        container.appendChild(tab);
    }
}

/**
 * Load all category data
 */
async function loadAllCategories() {
    for (const [id, cat] of Object.entries(CATEGORIES)) {
        const papers = await loadCategoryPapers(id);
        categoryData[id] = papers;

        // Update tab count
        const tab = document.querySelector(`.category-tab[data-category="${id}"]`);
        if (tab) {
            const countSpan = tab.querySelector('.count');
            countSpan.textContent = ` (${papers.length})`;
        }
    }
}

/**
 * Calculate global statistics
 */
function getGlobalStats() {
    const allPapers = new Map();
    let totalCitations = 0;
    let totalInfluential = 0;
    const yearCounts = {};
    const typeCounts = {};
    const domainCounts = {};

    for (const [catId, papers] of Object.entries(categoryData)) {
        for (const paper of papers) {
            if (!allPapers.has(paper.paper_id)) {
                allPapers.set(paper.paper_id, paper);
                totalCitations += paper.citation_count || 0;
                totalInfluential += paper.influential_citation_count || 0;

                if (paper.year) {
                    yearCounts[paper.year] = (yearCounts[paper.year] || 0) + 1;
                }

                if (paper.paper_type) {
                    typeCounts[paper.paper_type] = (typeCounts[paper.paper_type] || 0) + 1;
                }

                (paper.domains || []).forEach(d => {
                    domainCounts[d] = (domainCounts[d] || 0) + 1;
                });
            }
        }
    }

    return {
        totalPapers: allPapers.size,
        totalCitations,
        totalInfluential,
        yearCounts,
        typeCounts,
        domainCounts
    };
}

/**
 * Show hub overview (all categories)
 */
function showHubOverview() {
    const container = document.getElementById('hub-overview');
    container.innerHTML = '';
    container.style.display = 'grid';

    document.getElementById('charts-section').style.display = 'none';
    document.getElementById('controls').style.display = 'none';
    document.getElementById('paper-list').innerHTML = '';
    document.getElementById('category-info').classList.remove('visible');

    // Global stats
    const stats = getGlobalStats();

    // Stats banner
    const statsBanner = document.createElement('div');
    statsBanner.className = 'stats-banner';
    statsBanner.innerHTML = `
        <div class="stat-item">
            <span class="stat-value">${stats.totalPapers}</span>
            <span class="stat-label">Papers</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${formatNumber(stats.totalCitations)}</span>
            <span class="stat-label">Total Citations</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${formatNumber(stats.totalInfluential)}</span>
            <span class="stat-label">Influential Citations</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${Object.keys(stats.typeCounts).length}</span>
            <span class="stat-label">Paper Types</span>
        </div>
    `;
    container.parentElement.insertBefore(statsBanner, container);

    for (const [id, cat] of Object.entries(CATEGORIES)) {
        const count = categoryData[id]?.length || 0;
        if (count === 0) continue; // Skip empty categories

        // Calculate category stats
        const catPapers = categoryData[id] || [];
        const catCitations = catPapers.reduce((sum, p) => sum + (p.citation_count || 0), 0);
        const attackCount = catPapers.filter(p => p.paper_type === 'attack').length;
        const defenseCount = catPapers.filter(p => p.paper_type === 'defense').length;

        const card = document.createElement('div');
        card.className = 'hub-card';
        card.style.borderLeftColor = cat.color;
        card.innerHTML = `
            <h3><span class="owasp-id">${id}</span>${cat.name}</h3>
            <p>${cat.description}</p>
            <div class="card-stats">
                <span class="paper-count">${count} papers</span>
                <span class="citation-count">${formatNumber(catCitations)} citations</span>
            </div>
            <div class="card-breakdown">
                ${attackCount > 0 ? `<span class="type-badge attack">${attackCount} attacks</span>` : ''}
                ${defenseCount > 0 ? `<span class="type-badge defense">${defenseCount} defenses</span>` : ''}
            </div>
        `;
        card.addEventListener('click', () => selectCategory(id));
        container.appendChild(card);
    }

    // Update active tab
    document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
    document.querySelector('.category-tab[data-category="all"]').classList.add('active');
}

/**
 * Select a category
 */
function selectCategory(categoryId) {
    // Remove stats banner if exists
    const existingBanner = document.querySelector('.stats-banner');
    if (existingBanner) existingBanner.remove();

    if (categoryId === 'all') {
        showHubOverview();
        return;
    }

    currentCategory = categoryId;
    papers = categoryData[categoryId] || [];

    // Hide hub overview
    document.getElementById('hub-overview').style.display = 'none';

    // Show category info
    const cat = CATEGORIES[categoryId];
    document.getElementById('category-title').textContent = `${categoryId}: ${cat.name}`;
    document.getElementById('category-description').textContent = cat.description;
    document.getElementById('category-info').classList.add('visible');
    document.getElementById('category-info').style.background =
        `linear-gradient(135deg, ${cat.color} 0%, ${adjustColor(cat.color, -30)} 100%)`;

    // Show controls and charts
    document.getElementById('charts-section').style.display = 'block';
    document.getElementById('controls').style.display = 'flex';

    // Update active tab
    document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.category-tab[data-category="${categoryId}"]`)?.classList.add('active');

    // Reset filters
    resetFilters();

    // Render
    populateFilters();
    renderCharts();
    renderPapers();
}

/**
 * Reset filter controls
 */
function resetFilters() {
    document.getElementById('search').value = '';
    document.getElementById('year-filter').innerHTML = '<option value="">All Years</option>';
    document.getElementById('venue-filter').innerHTML = '<option value="">All Venues</option>';
    document.getElementById('type-filter').innerHTML = '<option value="">All Types</option>';
}

/**
 * Populate all filters
 */
function populateFilters() {
    // Years
    const years = [...new Set(papers.map(p => p.year).filter(Boolean))].sort((a, b) => b - a);
    const yearSelect = document.getElementById('year-filter');
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        yearSelect.appendChild(option);
    });

    // Venues
    const venueCounts = {};
    papers.forEach(p => {
        if (p.venue) {
            venueCounts[p.venue] = (venueCounts[p.venue] || 0) + 1;
        }
    });
    const sortedVenues = Object.entries(venueCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([venue, count]) => ({ venue, count, abbrev: getVenueAbbrev(venue) }));

    const venueSelect = document.getElementById('venue-filter');
    sortedVenues.forEach(({ venue, count, abbrev }) => {
        const option = document.createElement('option');
        option.value = venue;
        option.textContent = `${abbrev} (${count})`;
        venueSelect.appendChild(option);
    });

    // Paper types
    const types = [...new Set(papers.map(p => p.paper_type).filter(Boolean))];
    const typeSelect = document.getElementById('type-filter');
    types.forEach(type => {
        const option = document.createElement('option');
        option.value = type;
        option.textContent = type.charAt(0).toUpperCase() + type.slice(1);
        typeSelect.appendChild(option);
    });
}

/**
 * Render charts
 */
function renderCharts() {
    if (papers.length === 0) {
        document.getElementById('chart-papers-per-year').innerHTML = '';
        document.getElementById('chart-type-dist').innerHTML = '';
        return;
    }

    const cat = CATEGORIES[currentCategory];
    const color = cat?.color || '#3b82f6';

    const chartConfig = { responsive: true, displayModeBar: false };
    const layoutDefaults = {
        margin: { t: 40, r: 20, b: 40, l: 50 },
        font: { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif' },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)'
    };

    // Papers per year
    const yearCounts = {};
    papers.forEach(p => {
        if (p.year && p.year >= 2016) {
            yearCounts[p.year] = (yearCounts[p.year] || 0) + 1;
        }
    });
    const years = Object.keys(yearCounts).sort();
    const counts = years.map(y => yearCounts[y]);

    Plotly.newPlot('chart-papers-per-year', [{
        x: years,
        y: counts,
        type: 'bar',
        marker: { color: color }
    }], {
        ...layoutDefaults,
        title: { text: 'Papers per Year', font: { size: 14 } },
        xaxis: { title: 'Year' },
        yaxis: { title: 'Papers' }
    }, chartConfig);

    // Paper type distribution
    const typeCounts = {};
    papers.forEach(p => {
        if (p.paper_type) {
            typeCounts[p.paper_type] = (typeCounts[p.paper_type] || 0) + 1;
        }
    });

    const typeColors = {
        'attack': '#ef4444',
        'defense': '#22c55e',
        'survey': '#3b82f6',
        'benchmark': '#f59e0b',
        'empirical': '#8b5cf6',
        'theoretical': '#6366f1',
        'tool': '#14b8a6'
    };

    Plotly.newPlot('chart-type-dist', [{
        values: Object.values(typeCounts),
        labels: Object.keys(typeCounts).map(t => t.charAt(0).toUpperCase() + t.slice(1)),
        type: 'pie',
        marker: {
            colors: Object.keys(typeCounts).map(t => typeColors[t] || '#94a3b8')
        },
        textinfo: 'label+percent',
        hole: 0.4
    }], {
        ...layoutDefaults,
        title: { text: 'Paper Types', font: { size: 14 } },
        showlegend: false
    }, chartConfig);
}

/**
 * Get filtered papers based on current filters
 */
function getFilteredPapers() {
    const search = document.getElementById('search').value.toLowerCase();
    const yearFilter = document.getElementById('year-filter').value;
    const venueFilter = document.getElementById('venue-filter').value;
    const typeFilter = document.getElementById('type-filter').value;
    const sortBy = document.getElementById('sort-by').value;

    let filtered = papers.filter(p => {
        const matchesSearch = !search ||
            p.title?.toLowerCase().includes(search) ||
            p.abstract?.toLowerCase().includes(search) ||
            p.tldr?.toLowerCase().includes(search) ||
            p.authors?.some(a => a.toLowerCase().includes(search)) ||
            p.tags?.some(t => t.toLowerCase().includes(search));
        const matchesYear = !yearFilter || p.year == yearFilter;
        const matchesVenue = !venueFilter || p.venue === venueFilter;
        const matchesType = !typeFilter || p.paper_type === typeFilter;
        return matchesSearch && matchesYear && matchesVenue && matchesType;
    });

    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'year-desc':
                const dateA = a.publication_date || (a.year ? `${a.year}-01-01` : '');
                const dateB = b.publication_date || (b.year ? `${b.year}-01-01` : '');
                return dateB.localeCompare(dateA);
            case 'year-asc':
                const dateA2 = a.publication_date || (a.year ? `${a.year}-01-01` : '');
                const dateB2 = b.publication_date || (b.year ? `${b.year}-01-01` : '');
                return dateA2.localeCompare(dateB2);
            case 'citations-desc':
                return (b.citation_count || 0) - (a.citation_count || 0);
            case 'citations-asc':
                return (a.citation_count || 0) - (b.citation_count || 0);
            case 'influential-desc':
                return (b.influential_citation_count || 0) - (a.influential_citation_count || 0);
            case 'title':
                return (a.title || '').localeCompare(b.title || '');
            default:
                return 0;
        }
    });

    return filtered;
}

/**
 * Render papers list
 */
function renderPapers() {
    const filtered = getFilteredPapers();
    const container = document.getElementById('paper-list');
    const stats = document.getElementById('stats');

    const totalCitations = filtered.reduce((sum, p) => sum + (p.citation_count || 0), 0);
    stats.textContent = `${filtered.length} papers | ${formatNumber(totalCitations)} citations`;

    if (filtered.length === 0) {
        container.innerHTML = '<div class="no-results">No papers found matching your criteria.</div>';
        return;
    }

    container.innerHTML = filtered.map(paper => `
        <div class="paper" onclick="this.classList.toggle('expanded')">
            <div class="paper-header">
                <div class="paper-title">${escapeHtml(paper.title)}</div>
                <div class="paper-meta">
                    ${paper.paper_type ? `<span class="type-badge ${paper.paper_type}">${paper.paper_type}</span>` : ''}
                    ${paper.publication_date ? `<span class="paper-year">${formatDate(paper.publication_date)}</span>` :
                      (paper.year ? `<span class="paper-year">${paper.year}</span>` : '')}
                </div>
            </div>
            <div class="paper-authors">${escapeHtml(paper.authors?.join(', ') || 'Unknown authors')}${paper.max_h_index > 20 ? ` <span class="h-index-badge" title="Max author h-index">h:${paper.max_h_index}</span>` : ''}</div>
            ${paper.venue ? `<div class="paper-venue">${escapeHtml(paper.venue)}${paper.is_open_access ? ' <span class="oa-badge">Open Access</span>' : ''}</div>` : ''}

            <div class="paper-citations">
                <span class="citation-badge" style="${getCitationStyle(paper.citation_count || 0)}">${formatNumber(paper.citation_count || 0)} citations</span>
                ${paper.influential_citation_count > 0 ? `<span class="influential-badge">${paper.influential_citation_count} influential</span>` : ''}
            </div>

            ${paper.tldr ? `<div class="paper-tldr"><strong>TL;DR:</strong> ${escapeHtml(paper.tldr)}</div>` : ''}

            ${paper.domains?.length || paper.model_types?.length ? `
            <div class="paper-tags">
                ${(paper.domains || []).map(d => `<span class="tag domain-tag">${d}</span>`).join('')}
                ${(paper.model_types || []).map(m => `<span class="tag model-tag">${m}</span>`).join('')}
            </div>
            ` : ''}

            <div class="paper-abstract">${escapeHtml(paper.abstract || 'No abstract available.')}</div>

            ${paper.tags?.length ? `
            <div class="paper-detail-tags">
                ${paper.tags.map(t => `<span class="detail-tag">${t}</span>`).join('')}
            </div>
            ` : ''}

            <div class="paper-links">
                ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" onclick="event.stopPropagation()">PDF</a>` : ''}
                ${paper.open_access_pdf ? `<a href="${paper.open_access_pdf}" target="_blank" onclick="event.stopPropagation()">Open PDF</a>` : ''}
                ${paper.doi ? `<a href="${paper.doi}" target="_blank" onclick="event.stopPropagation()">DOI</a>` : ''}
                ${paper.url ? `<a href="${paper.url}" target="_blank" onclick="event.stopPropagation()">Source</a>` : ''}
            </div>
        </div>
    `).join('');
}

/**
 * Escape HTML for safe rendering
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format large numbers
 */
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
}

/**
 * Get citation count styling
 */
function getCitationStyle(count) {
    if (count <= 0) return 'background: #f3f4f6; color: #6b7280;';
    if (count < 10) return 'background: #fef9c3; color: #854d0e;';
    if (count < 50) return 'background: #fed7aa; color: #9a3412;';
    if (count < 100) return 'background: #fdba74; color: #9a3412;';
    if (count < 200) return 'background: #fb923c; color: #7c2d12;';
    if (count < 500) return 'background: #f97316; color: white;';
    return 'background: #dc2626; color: white;';
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date)) return dateStr;
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[date.getMonth()]} ${date.getFullYear()}`;
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('search').addEventListener('input', renderPapers);
    document.getElementById('year-filter').addEventListener('change', renderPapers);
    document.getElementById('venue-filter').addEventListener('change', renderPapers);
    document.getElementById('type-filter').addEventListener('change', renderPapers);
    document.getElementById('sort-by').addEventListener('change', renderPapers);
    document.querySelector('.category-tab[data-category="all"]').addEventListener('click', showHubOverview);

    // Initialize
    initialize();
});
