"""
Repository model for DevBridge
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class RepositoryMetadata(BaseModel):
    """Metadata for a repository"""
    commit_count: int = 0
    contributors: int = 0
    last_commit_date: Optional[datetime] = None
    branches: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    last_indexed_at: Optional[datetime] = None
    patterns_count: int = 0

class Repository(BaseModel):
    """
    Represents a code repository indexed by DevBridge
    """
    id: str
    name: str
    path: str
    remote_url: Optional[str] = None
    primary_language: Optional[str] = None
    frameworks: List[str] = Field(default_factory=list)
    last_indexed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    patterns_count: int = 0
    metadata: RepositoryMetadata = Field(default_factory=RepositoryMetadata)
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self, **kwargs) -> dict:
        """Convert to dictionary for storage"""
        return self.model_dump(by_alias=True, **kwargs)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Repository':
        """Create from dictionary"""
        return cls(**data)
    
    def get_summary(self) -> str:
        """Get a short summary of the repository"""
        language_info = f" ({self.primary_language})" if self.primary_language else ""
        return f"{self.name}{language_info} - {self.path}"
        
    def is_local(self) -> bool:
        """Check if repository is local"""
        return self.path is not None and len(self.path) > 0