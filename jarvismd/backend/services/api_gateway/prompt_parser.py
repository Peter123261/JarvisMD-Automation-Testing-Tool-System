"""
Prompt Parser Module

Parses prompt files to extract criterion metadata (IDs, text, max scores).
This makes the system maintainable and scalable - changing the prompt file
automatically updates the UI without code changes.
"""
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from jarvismd.backend.services.api_gateway.paths import PROMPTS_DIR

logger = logging.getLogger(__name__)


class CriterionMetadata:
    """Metadata for a single criterion"""
    def __init__(self, criterion_id: int, text: str, max_score: int, is_safety: bool = False):
        self.criterion_id = criterion_id
        self.text = text
        self.max_score = max_score
        self.is_safety = is_safety

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.criterion_id,
            "text": self.text,
            "max_score": self.max_score,
            "is_safety": self.is_safety
        }


class PromptParser:
    """Parser for extracting criterion metadata from prompt files"""
    
    def __init__(self, prompt_path: Optional[Path] = None):
        """
        Initialize prompt parser
        
        Args:
            prompt_path: Path to prompt file. If None, must be provided when calling load().
        """
        if prompt_path is None:
            raise ValueError("prompt_path must be provided to PromptParser")
        self.prompt_path = prompt_path
        self._criterion_metadata: Dict[int, CriterionMetadata] = {}
        self._criterion_text_map: Dict[str, int] = {}  # Maps criterion text to ID
        self._loaded = False
        
    def load(self) -> None:
        """Load and parse the prompt file"""
        if self._loaded:
            return
            
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.prompt_path}")
        
        with open(self.prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract max scores from "SPECIFIC SCORING MAXIMUMS" section
        max_scores = self._extract_max_scores(content)
        
        # Extract criterion text from JSON template section
        criterion_texts = self._extract_criterion_texts(content)
        
        # Extract safety criteria from prompt file (dynamic, not hardcoded)
        safety_criteria = self._extract_safety_criteria(content)
        
        # Combine into metadata
        for criterion_id, max_score in max_scores.items():
            text = criterion_texts.get(criterion_id, f"Criterion {criterion_id}")
            is_safety = criterion_id in safety_criteria
            
            self._criterion_metadata[criterion_id] = CriterionMetadata(
                criterion_id=criterion_id,
                text=text,
                max_score=max_score,
                is_safety=is_safety
            )
            
            # Build text-to-ID mapping (normalized for matching)
            normalized_text = self._normalize_text(text)
            self._criterion_text_map[normalized_text] = criterion_id
        
        self._loaded = True
    
    def _extract_max_scores(self, content: str) -> Dict[int, int]:
        """Extract max scores from 'SPECIFIC SCORING MAXIMUMS' section"""
        max_scores = {}
        
        # Pattern: "Criterion X: Maximum Y points"
        pattern = r'Criterion\s+(\d+):\s+Maximum\s+(\d+)\s+points'
        matches = re.findall(pattern, content)
        
        for criterion_id_str, max_score_str in matches:
            criterion_id = int(criterion_id_str)
            max_score = int(max_score_str)
            max_scores[criterion_id] = max_score
        
        return max_scores
    
    def _extract_criterion_texts(self, content: str) -> Dict[int, str]:
        """Extract criterion text from JSON template section"""
        criterion_texts = {}
        
        # Pattern: "id": X, ... "criterion": "TEXT"
        # Handle both {{ and { formats, match across lines
        # Look for id first, then find criterion field after it
        # Use a pattern that captures everything between quotes, including apostrophes
        # Match until we find ", (quote followed by comma) or " at end of line
        pattern = r'["\']id["\']:\s*(\d+).*?["\']criterion["\']:\s*["\'](.*?)["\']\s*[,}]'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for criterion_id_str, text in matches:
            criterion_id = int(criterion_id_str)
            # Clean up text (remove newlines, extra spaces, but preserve apostrophes)
            text = re.sub(r'\s+', ' ', text.strip())
            criterion_texts[criterion_id] = text
        
        return criterion_texts
    
    def _extract_safety_criteria(self, content: str) -> Set[int]:
        """
        Extract safety criteria IDs from prompt file dynamically.
        Looks for criteria marked with "(safety criterion)" in the scoring section.
        
        Args:
            content: Full content of the prompt file
            
        Returns:
            Set of criterion IDs that are marked as safety criteria
        """
        safety_criteria = set()
        
        # Pattern 1: "Criterion X: Maximum Y points (safety criterion)"
        # This is the primary pattern used in the prompt file
        pattern1 = r'Criterion\s+(\d+):\s+Maximum\s+\d+\s+points\s*\(safety\s+criterion\)'
        matches1 = re.findall(pattern1, content, re.IGNORECASE)
        
        for criterion_id_str in matches1:
            try:
                criterion_id = int(criterion_id_str)
                safety_criteria.add(criterion_id)
            except ValueError:
                # Skip invalid IDs
                continue
        
        # Pattern 2: "SAFETY CRITERIA SCORING (Criteria X, Y, Z ONLY):"
        # Fallback pattern to catch explicit safety criteria lists
        pattern2 = r'SAFETY\s+CRITERIA\s+SCORING.*?Criteria\s+([\d,\s]+)\s+ONLY'
        matches2 = re.findall(pattern2, content, re.IGNORECASE | re.DOTALL)
        
        for criteria_list_str in matches2:
            # Extract individual criterion IDs from comma/space-separated list
            criterion_ids = re.findall(r'\d+', criteria_list_str)
            for criterion_id_str in criterion_ids:
                try:
                    criterion_id = int(criterion_id_str)
                    safety_criteria.add(criterion_id)
                except ValueError:
                    continue
        
        # Log if no safety criteria found (for debugging)
        if not safety_criteria:
            logger.warning(f"⚠️ No safety criteria found in prompt file: {self.prompt_path.name}. "
                         f"Safety criteria should be marked with '(safety criterion)' in the scoring section.")
        else:
            logger.debug(f"✅ Extracted {len(safety_criteria)} safety criteria from prompt: {sorted(safety_criteria)}")
        
        return safety_criteria
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching (lowercase, remove punctuation)"""
        # Remove common prefixes and normalize
        text = text.lower()
        # Remove leading "criterion X:" if present
        text = re.sub(r'^criterion\s+\d+:\s*', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def get_max_score(self, criterion_id: Optional[int] = None, criterion_text: Optional[str] = None) -> int:
        """Get max score for a criterion by ID or text"""
        if not self._loaded:
            self.load()
        
        if criterion_id:
            metadata = self._criterion_metadata.get(criterion_id)
            if metadata:
                return metadata.max_score
        
        if criterion_text:
            normalized = self._normalize_text(criterion_text)
            # Try exact match first
            criterion_id = self._criterion_text_map.get(normalized)
            if criterion_id:
                return self._criterion_metadata[criterion_id].max_score
            
            # Try partial match (contains)
            for text, cid in self._criterion_text_map.items():
                if normalized in text or text in normalized:
                    return self._criterion_metadata[cid].max_score
        
        # Default fallback
        return 8
    
    def get_criterion_metadata(self, criterion_id: int) -> Optional[CriterionMetadata]:
        """Get full metadata for a criterion by ID"""
        if not self._loaded:
            self.load()
        return self._criterion_metadata.get(criterion_id)
    
    def get_all_metadata(self) -> List[Dict]:
        """Get all criterion metadata as a list of dictionaries"""
        if not self._loaded:
            self.load()
        return [meta.to_dict() for meta in sorted(self._criterion_metadata.values(), key=lambda x: x.criterion_id)]
    
    def get_max_scores_map(self) -> Dict[int, int]:
        """Get a map of criterion_id -> max_score"""
        if not self._loaded:
            self.load()
        return {cid: meta.max_score for cid, meta in self._criterion_metadata.items()}
    
    def get_criterion_name_to_max_score_map(self) -> Dict[str, int]:
        """
        Get a map of criterion_name (text) -> max_score
        This allows frontend to look up max scores directly by criterion name
        without needing to extract IDs.
        """
        if not self._loaded:
            self.load()
        
        name_to_max_score = {}
        for cid, metadata in self._criterion_metadata.items():
            # Use the original text as stored
            name_to_max_score[metadata.text] = metadata.max_score
            # Also add normalized version for flexible matching
            normalized = self._normalize_text(metadata.text)
            if normalized != metadata.text:
                name_to_max_score[normalized] = metadata.max_score
        
        return name_to_max_score
    
    def get_criteria_schema(self) -> List[Dict]:
        """
        Get the full criteria schema as a list of dictionaries.
        This is the canonical source of truth for all criteria properties.
        Returns a list sorted by criterion ID.
        """
        if not self._loaded:
            self.load()
        
        schema = []
        for criterion_id in sorted(self._criterion_metadata.keys()):
            metadata = self._criterion_metadata[criterion_id]
            schema.append({
                'id': metadata.criterion_id,
                'name': metadata.text,
                'description': metadata.text,  # Using text as description for now
                'max_score': metadata.max_score,
                'is_safety': metadata.is_safety
            })
        
        return schema


# Global parser instance cache (keyed by prompt path)
_parser_instances: Dict[Path, PromptParser] = {}


def get_parser(prompt_path: Optional[Path] = None) -> PromptParser:
    """
    Get a parser instance for the specified prompt path
    
    Args:
        prompt_path: Path to prompt file. If None, raises ValueError.
        
    Returns:
        PromptParser instance for the specified prompt path
    """
    if prompt_path is None:
        raise ValueError("prompt_path must be provided to get_parser()")
    
    # Normalize path for caching
    prompt_path = Path(prompt_path).resolve()
    
    # Return cached instance if available
    if prompt_path in _parser_instances:
        return _parser_instances[prompt_path]
    
    # Create new instance
    parser = PromptParser(prompt_path=prompt_path)
    parser.load()
    _parser_instances[prompt_path] = parser
    return parser

