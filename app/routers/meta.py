from fastapi import APIRouter

router = APIRouter()

@router.get("/meta/sources")
async def meta_sources():
    # TODO: 替换为真实数据/SQL
    return {"sources": ["UNCTAD", "WB", "Customs"]}