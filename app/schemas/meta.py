from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

class SourceItem(BaseModel):
    name: str
    description: Optional[str] = None
    license: Optional[str] = None
    source_type: Optional[str] = None
    last_loaded_at: Optional[datetime] = None  # UTC

class SourcesResponse(BaseModel):
    sources: List[SourceItem]
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
