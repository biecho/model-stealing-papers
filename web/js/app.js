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
        const response = await fetch('../data/manifest.json');
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
        const response = await fetch(`../data/${cat.file}`);
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

    for (const [id, cat] of Object.entries(CATEGORIES)) {
        const count = categoryData[id]?.length || 0;

        const card = document.createElement('div');
        card.className = 'hub-card';
        card.style.borderLeftColor = cat.color;
        card.innerHTML = `
            <h3><span class="owasp-id">${id}</span>${cat.name}</h3>
            <p>${cat.description}</p>
            <div class="paper-count">${count} papers</div>
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
    populateYearFilter();
    populateVenueFilter();
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
}

/**
 * Render charts
 */
function renderCharts() {
    if (papers.length === 0) {
        document.getElementById('chart-papers-per-year').innerHTML = '';
        document.getElementById('chart-cumulative').innerHTML = '';
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

    let cumulative = 0;
    const cumulativeCounts = years.map(y => {
        cumulative += yearCounts[y];
        return cumulative;
    });

    Plotly.newPlot('chart-cumulative', [{
        x: years,
        y: cumulativeCounts,
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: color, width: 2 },
        marker: { size: 6 }
    }], {
        ...layoutDefaults,
        title: { text: 'Cumulative Papers', font: { size: 14 } },
        xaxis: { title: 'Year' },
        yaxis: { title: 'Total Papers' }
    }, chartConfig);
}

/**
 * Populate year filter
 */
function populateYearFilter() {
    const years = [...new Set(papers.map(p => p.year).filter(Boolean))].sort((a, b) => b - a);
    const select = document.getElementById('year-filter');
    years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        select.appendChild(option);
    });
}

/**
 * Populate venue filter
 */
function populateVenueFilter() {
    const venueCounts = {};
    papers.forEach(p => {
        if (p.venue) {
            venueCounts[p.venue] = (venueCounts[p.venue] || 0) + 1;
        }
    });

    const sortedVenues = Object.entries(venueCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([venue, count]) => ({ venue, count, abbrev: getVenueAbbrev(venue) }));

    const select = document.getElementById('venue-filter');
    sortedVenues.forEach(({ venue, count, abbrev }) => {
        const option = document.createElement('option');
        option.value = venue;
        option.textContent = `${abbrev} (${count})`;
        select.appendChild(option);
    });
}

/**
 * Get filtered papers based on current filters
 */
function getFilteredPapers() {
    const search = document.getElementById('search').value.toLowerCase();
    const yearFilter = document.getElementById('year-filter').value;
    const venueFilter = document.getElementById('venue-filter').value;
    const sortBy = document.getElementById('sort-by').value;

    let filtered = papers.filter(p => {
        const matchesSearch = !search ||
            p.title?.toLowerCase().includes(search) ||
            p.abstract?.toLowerCase().includes(search) ||
            p.authors?.some(a => a.toLowerCase().includes(search));
        const matchesYear = !yearFilter || p.year == yearFilter;
        const matchesVenue = !venueFilter || p.venue === venueFilter;
        return matchesSearch && matchesYear && matchesVenue;
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

    stats.textContent = `Showing ${filtered.length} of ${papers.length} papers`;

    if (filtered.length === 0) {
        container.innerHTML = '<div class="no-results">No papers found matching your criteria.</div>';
        return;
    }

    container.innerHTML = filtered.map(paper => `
        <div class="paper" onclick="this.classList.toggle('expanded')">
            <div class="paper-header">
                <div class="paper-title">${escapeHtml(paper.title)}</div>
                <div class="paper-meta">
                    ${paper.publication_date ? `<span class="paper-year">${formatDate(paper.publication_date)}</span>` :
                      (paper.year ? `<span class="paper-year">${paper.year}</span>` : '')}
                    <span class="paper-citations" style="${getCitationStyle(paper.citation_count || 0)}">${paper.citation_count || 0} citations</span>
                </div>
            </div>
            <div class="paper-authors">${escapeHtml(paper.authors?.join(', ') || 'Unknown authors')}</div>
            ${paper.venue ? `<div class="paper-venue">${escapeHtml(paper.venue)}</div>` : ''}
            ${paper.abstract ? `<div class="paper-abstract">${escapeHtml(paper.abstract)}</div>` : ''}
            <div class="paper-links">
                ${paper.url ? `<a href="${paper.url}" target="_blank" onclick="event.stopPropagation()">Semantic Scholar</a>` : ''}
                ${paper.pdf_url ? `<a href="${paper.pdf_url}" target="_blank" onclick="event.stopPropagation()">PDF</a>` : ''}
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
    document.getElementById('sort-by').addEventListener('change', renderPapers);
    document.querySelector('.category-tab[data-category="all"]').addEventListener('click', showHubOverview);

    // Initialize
    initialize();
});
