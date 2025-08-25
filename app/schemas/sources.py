from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SourceItem(BaseModel):
    id: str
    name: str
    license: Optional[str] = None

class SourcesResponse(BaseModel):
    as_of: datetime
    sources: List[SourceItem] = []
