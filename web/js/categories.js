/**
 * OWASP ML Security Top 10 Category Definitions
 */

const CATEGORIES = {
    ML01: {
        name: "Input Manipulation Attack",
        color: "#ef4444",
        file: "ml01_papers.json",
        description: "Adversarial examples and evasion attacks on ML models"
    },
    ML02: {
        name: "Data Poisoning Attack",
        color: "#f97316",
        file: "ml02_papers.json",
        description: "Poisoning training data to compromise ML models"
    },
    ML03: {
        name: "Model Inversion Attack",
        color: "#eab308",
        file: "ml03_papers.json",
        description: "Reconstructing training data from ML model access"
    },
    ML04: {
        name: "Membership Inference Attack",
        color: "#84cc16",
        file: "ml04_papers.json",
        description: "Detecting if data was used to train an ML model"
    },
    ML05: {
        name: "Model Theft",
        color: "#22c55e",
        file: "ml05_papers.json",
        description: "Techniques to steal or extract ML models"
    },
    ML06: {
        name: "AI Supply Chain Attacks",
        color: "#14b8a6",
        file: "ml06_papers.json",
        description: "Compromising ML through dependencies and third-party components"
    },
    ML07: {
        name: "Transfer Learning Attack",
        color: "#06b6d4",
        file: "ml07_papers.json",
        description: "Exploiting fine-tuning and transfer learning vulnerabilities"
    },
    ML08: {
        name: "Model Skewing",
        color: "#3b82f6",
        file: "ml08_papers.json",
        description: "Inducing bias and unfairness in ML models"
    },
    ML09: {
        name: "Output Integrity Attack",
        color: "#8b5cf6",
        file: "ml09_papers.json",
        description: "Manipulating ML model outputs and predictions"
    },
    ML10: {
        name: "Model Poisoning",
        color: "#ec4899",
        file: "ml10_papers.json",
        description: "Backdoors, trojans, and model-level attacks"
    }
};

// Venue abbreviations for display
const VENUE_ABBREV = {
    'arXiv.org': 'arXiv',
    'AAAI Conference on Artificial Intelligence': 'AAAI',
    'Neural Information Processing Systems': 'NeurIPS',
    'Computer Vision and Pattern Recognition': 'CVPR',
    'USENIX Security Symposium': 'USENIX',
    'IEEE Transactions on Information Forensics and Security': 'TIFS',
    'IEEE International Joint Conference on Neural Network': 'IJCNN',
    'IEEE Transactions on Dependable and Secure Computing': 'TDSC',
    'ACM Asia Conference on Computer and Communications Security': 'AsiaCCS',
    'IEEE Symposium on Security and Privacy': 'S&P',
    'International Joint Conference on Artificial Intelligence': 'IJCAI',
    'International Conference on Machine Learning': 'ICML',
    'International Conference on Software Engineering': 'ICSE',
    'IEEE International Conference on Acoustics, Speech, and Signal Processing': 'ICASSP',
    'ACM Multimedia': 'ACM MM',
    'International Conference on Learning Representations': 'ICLR',
    'European Conference on Computer Vision': 'ECCV',
    'Network and Distributed System Security Symposium': 'NDSS',
    'ACM Conference on Computer and Communications Security': 'CCS',
    'Conference on Computer and Communications Security': 'CCS',
    'The Web Conference': 'WWW',
    'IEEE Access': 'IEEE Access',
    'Conference on Empirical Methods in Natural Language Processing': 'EMNLP',
    'European Symposium on Research in Computer Security': 'ESORICS',
    'Knowledge Discovery and Data Mining': 'KDD',
    'Annual Meeting of the Association for Computational Linguistics': 'ACL',
    'North American Chapter of the Association for Computational Linguistics': 'NAACL',
    'ACM Computing Surveys': 'CSUR',
    'IEEE Transactions on Neural Networks and Learning Systems': 'TNNLS',
    'European Symposium on Security and Privacy': 'EuroS&P',
    'ACM Transactions on Privacy and Security': 'TOPS'
};

/**
 * Get abbreviated venue name for display
 */
function getVenueAbbrev(venue) {
    if (!venue) return '';
    if (VENUE_ABBREV[venue]) return VENUE_ABBREV[venue];
    const cleaned = venue.replace(/^\d{4}\s+/, '');
    if (VENUE_ABBREV[cleaned]) return VENUE_ABBREV[cleaned];
    const parenMatch = cleaned.match(/\(([A-Z]{2,10})\)/);
    if (parenMatch) return parenMatch[1];
    return cleaned.length > 25 ? cleaned.substring(0, 25) + '...' : cleaned;
}

/**
 * Adjust color brightness
 */
function adjustColor(color, amount) {
    const num = parseInt(color.replace('#', ''), 16);
    const r = Math.min(255, Math.max(0, (num >> 16) + amount));
    const g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) + amount));
    const b = Math.min(255, Math.max(0, (num & 0x0000FF) + amount));
    return `#${(1 << 24 | r << 16 | g << 8 | b).toString(16).slice(1)}`;
}

// Export for use in app.js
window.CATEGORIES = CATEGORIES;
window.VENUE_ABBREV = VENUE_ABBREV;
window.getVenueAbbrev = getVenueAbbrev;
window.adjustColor = adjustColor;
