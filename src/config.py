"""Configuration loader for paper filtering."""

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML is required. Install it with: pip install pyyaml"
    )


class Config:
    """Configuration for paper filtering loaded from YAML."""

    def __init__(self, config_path: str | Path = "config.yaml"):
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to configuration YAML file
        """
        self.config_path = Path(config_path)
        self._data = self._load_config()

        # Domain information
        self.domain_name = self._data["domain"]["name"]
        self.domain_description = self._data["domain"]["description"]
        self.owasp_id = self._data["domain"].get("owasp_id", "")
        self.owasp_name = self._data["domain"].get("owasp_name", "")
        self.short_description = self._data["domain"].get("short_description", "")
        self.parent_id = self._data["domain"].get("parent_id", "")

        # Keywords
        self.high_quality_keywords = self._data["high_quality_keywords"]
        self.core_keywords = self._data["core_keywords"]
        self.defense_keywords = self._data["defense_keywords"]
        self.problematic_keywords = self._data["problematic_keywords"]
        self.required_abstract_terms = self._data["required_abstract_terms"]

        # Exclusion signals
        self.exclusion_signals = self._data["exclusion_signals"]
        self.other_topics = self._data["other_topics"]

        # Filtering rules
        rules = self._data["filtering_rules"]
        self.min_term_mentions = rules["min_term_mentions"]
        self.watermark_dominance_threshold = rules["watermark_dominance_threshold"]
        self.topic_dominance_ratio = rules["topic_dominance_ratio"]
        self.context_window = rules["context_window"]
        self.first_paragraph_length = rules["first_paragraph_length"]

    def _load_config(self) -> dict[str, Any]:
        """Load and validate configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please create a config.yaml file or specify a valid path."
            )

        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)

        # Validate required sections
        required_sections = [
            "domain",
            "high_quality_keywords",
            "core_keywords",
            "defense_keywords",
            "problematic_keywords",
            "required_abstract_terms",
            "exclusion_signals",
            "other_topics",
            "filtering_rules",
        ]

        missing = [s for s in required_sections if s not in data]
        if missing:
            raise ValueError(
                f"Configuration file missing required sections: {', '.join(missing)}"
            )

        return data

    @classmethod
    def for_domain(cls, domain: str) -> "Config":
        """
        Load configuration for a specific domain.

        Args:
            domain: Domain name (e.g., "model_theft", "membership_inference")

        Returns:
            Config instance for the domain

        Example:
            config = Config.for_domain("model_theft")
        """
        # Try configs/ directory first (new structure)
        configs_dir = Path("configs")
        if configs_dir.exists():
            for config_file in configs_dir.glob("*.yaml"):
                if domain in config_file.stem:
                    return cls(config_file)

        # Fall back to old structure
        config_path = Path(f"config_{domain}.yaml")
        if not config_path.exists():
            config_path = Path("config.yaml")
        return cls(config_path)

    @classmethod
    def list_configs(cls, configs_dir: str | Path = "configs") -> list["Config"]:
        """
        List all available configurations.

        Args:
            configs_dir: Directory containing config files

        Returns:
            List of Config instances sorted by OWASP ID
        """
        configs_path = Path(configs_dir)
        if not configs_path.exists():
            return []

        configs = []
        for config_file in sorted(configs_path.glob("ml*.yaml")):
            try:
                configs.append(cls(config_file))
            except Exception:
                continue

        return sorted(configs, key=lambda c: c.owasp_id or "ZZ")

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"Config(domain={self.domain_name}, config_path={self.config_path})"

    @property
    def is_subcategory(self) -> bool:
        """Check if this config is a subcategory."""
        return bool(self.parent_id)

    @classmethod
    def list_main_configs(cls, configs_dir: str | Path = "configs") -> list["Config"]:
        """List only main category configurations (not subcategories)."""
        return [c for c in cls.list_configs(configs_dir) if not c.is_subcategory]

    @classmethod
    def list_subcategories(cls, parent_id: str, configs_dir: str | Path = "configs") -> list["Config"]:
        """List subcategories for a given parent category."""
        return [c for c in cls.list_configs(configs_dir) if c.parent_id == parent_id]


# Global config instance (can be overridden)
_config: Config | None = None


def get_config(config_path: str | Path | None = None) -> Config:
    """
    Get the global configuration instance.

    Args:
        config_path: Optional path to config file. If None, uses default.

    Returns:
        Config instance
    """
    global _config

    if _config is None or config_path is not None:
        path = config_path if config_path else "config.yaml"
        _config = Config(path)

    return _config


def set_config(config: Config) -> None:
    """
    Set the global configuration instance.

    Args:
        config: Config instance to use globally
    """
    global _config
    _config = config


# For backward compatibility, export commonly used values
def _get_or_default(attr: str, default: Any) -> Any:
    """Get config attribute or return default."""
    try:
        config = get_config()
        return getattr(config, attr)
    except (FileNotFoundError, ImportError):
        return default


# Backward compatibility exports
HIGH_QUALITY_KEYWORDS = []
CORE_KEYWORDS = []
DEFENSE_KEYWORDS = []
PROBLEMATIC_KEYWORDS = []
REQUIRED_ABSTRACT_TERMS = []
EXCLUSION_SIGNALS = {}
OTHER_TOPICS = {}
