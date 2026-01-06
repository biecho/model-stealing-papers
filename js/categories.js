/**
 * OWASP ML Security Top 10 Category Definitions
 *
 * Structure:
 * - Each category has a unique color and main data file
 * - Subcategories are optional and have their own data files
 * - Subcategory IDs use format: ML01a, ML01b, etc.
 */

const CATEGORIES = {
    ML01: {
        name: "Input Manipulation Attack",
        color: "#ef4444",
        file: "ml01_papers.json",
        description: "Adversarial examples and evasion attacks on ML models",
        subcategories: {
            ML01a: {
                name: "Prompt Injection",
                file: "ml01a_prompt_injection_papers.json",
                description: "Malicious prompts to manipulate LLM behavior"
            },
            ML01b: {
                name: "Jailbreaking",
                file: "ml01b_jailbreaking_papers.json",
                description: "Bypassing LLM safety guardrails"
            },
            ML01c: {
                name: "Adversarial Examples",
                file: "ml01c_adversarial_examples_papers.json",
                description: "Traditional adversarial perturbations on classifiers"
            }
        }
    },
    ML02: {
        name: "Data Poisoning Attack",
        color: "#f97316",
        file: "ml02_papers.json",
        description: "Poisoning training data to compromise ML models",
        subcategories: {}
    },
    ML03: {
        name: "Model Inversion Attack",
        color: "#eab308",
        file: "ml03_papers.json",
        description: "Reconstructing training data from ML model access",
        subcategories: {}
    },
    ML04: {
        name: "Membership Inference Attack",
        color: "#84cc16",
        file: "ml04_papers.json",
        description: "Detecting if data was used to train an ML model",
        subcategories: {}
    },
    ML05: {
        name: "Model Theft",
        color: "#22c55e",
        file: "ml05_papers.json",
        description: "Techniques to steal or extract ML models",
        subcategories: {
            ML05a: {
                name: "Prompt Stealing",
                file: "ml05a_prompt_stealing_papers.json",
                description: "Extracting system prompts from LLMs"
            }
        }
    },
    ML06: {
        name: "AI Supply Chain Attacks",
        color: "#14b8a6",
        file: "ml06_papers.json",
        description: "Compromising ML through dependencies and third-party components",
        subcategories: {}
    },
    ML07: {
        name: "Transfer Learning Attack",
        color: "#06b6d4",
        file: "ml07_papers.json",
        description: "Exploiting fine-tuning and transfer learning vulnerabilities",
        subcategories: {}
    },
    ML08: {
        name: "Model Skewing",
        color: "#3b82f6",
        file: "ml08_papers.json",
        description: "Inducing bias and unfairness in ML models",
        subcategories: {}
    },
    ML09: {
        name: "Output Integrity Attack",
        color: "#8b5cf6",
        file: "ml09_papers.json",
        description: "Manipulating ML model outputs and predictions",
        subcategories: {}
    },
    ML10: {
        name: "Model Poisoning",
        color: "#ec4899",
        file: "ml10_papers.json",
        description: "Backdoors, trojans, and model-level attacks",
        subcategories: {}
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

/**
 * Get parent category ID from subcategory ID
 * e.g., "ML01a" -> "ML01"
 */
function getParentCategory(categoryId) {
    const match = categoryId.match(/^(ML\d{2})/);
    return match ? match[1] : categoryId;
}

/**
 * Check if a category ID is a subcategory
 */
function isSubcategory(categoryId) {
    return /^ML\d{2}[a-z]$/.test(categoryId);
}

/**
 * Get all subcategories for a category
 */
function getSubcategories(categoryId) {
    const cat = CATEGORIES[categoryId];
    if (!cat || !cat.subcategories) return {};
    return cat.subcategories;
}

/**
 * Check if a category has subcategories
 */
function hasSubcategories(categoryId) {
    return Object.keys(getSubcategories(categoryId)).length > 0;
}

// Export for use in app.js
window.CATEGORIES = CATEGORIES;
window.VENUE_ABBREV = VENUE_ABBREV;
window.getVenueAbbrev = getVenueAbbrev;
window.adjustColor = adjustColor;
window.getParentCategory = getParentCategory;
window.isSubcategory = isSubcategory;
window.getSubcategories = getSubcategories;
window.hasSubcategories = hasSubcategories;
