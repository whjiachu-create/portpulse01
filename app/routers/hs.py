from fastapi import APIRouter, Path

router = APIRouter()

@router.get("/hs/{code}/imports")
async def hs_imports(code: str = Path(..., min_length=2, max_length=10)):
    # TODO: 替换为真实数据/SQL
    return {"hs_code": code, "imports": []}