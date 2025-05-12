"""
Pattern model for DevBridge
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class PatternContext(BaseModel):
    """Context information for a pattern"""
    commit_message: Optional[str] = None
    pull_request_description: Optional[str] = None
    comments: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    created_date: Optional[datetime] = None

class PatternMetadata(BaseModel):
    """Metadata for a pattern"""
    complexity: float = 0.0
    test_coverage: Optional[float] = None
    usage_count: int = 0
    related_files: List[str] = Field(default_factory=list)

class Pattern(BaseModel):
    """
    Represents a code pattern identified in a repository
    """
    id: str
    name: str
    description: str
    repository: str
    path: str
    language: str
    framework: Optional[str] = None
    pattern_type: str
    code_snippet: str
    context: PatternContext = Field(default_factory=PatternContext)
    related_patterns: List[str] = Field(default_factory=list)
    last_modified: datetime = Field(default_factory=datetime.now)
    metadata: PatternMetadata = Field(default_factory=PatternMetadata)
    
    def to_json(self, **kwargs) -> str:
        """Serialize Pattern to JSON string."""
        # Ensure enum values are used for serialization
        return self.model_dump_json(by_alias=True, **kwargs)

    def to_dict(self, **kwargs) -> dict:
        """Serialize Pattern to dictionary."""
        return self.model_dump(by_alias=True, **kwargs)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Pattern':
        """Create from dictionary"""
        return cls(**data)
    
    def get_summary(self) -> str:
        """Get a short summary of the pattern"""
        return f"{self.name} ({self.language}" + \
               (f"/{self.framework}" if self.framework else "") + \
               f") - {self.repository}/{self.path}"