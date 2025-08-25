from typing import Optional
from pydantic import BaseModel

class ErrorModel(BaseModel):
    code: str
    message: str
    request_id: str
    hint: Optional[str] = None
