from pydantic import BaseModel

class Source(BaseModel):
    id: int
    name: str
    url: str
    last_updated: str  # 已在路由中 .isoformat() 输出