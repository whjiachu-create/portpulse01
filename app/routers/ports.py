from fastapi import APIRouter, Path

router = APIRouter()

@router.get("/ports/{unlocode}/snapshot")
async def port_snapshot(unlocode: str = Path(..., min_length=3, max_length=5)):
    # TODO: 替换为真实数据/SQL
    return {"unlocode": unlocode.upper(), "snapshot": {}}

@router.get("/ports/{unlocode}/dwell")
async def port_dwell(unlocode: str = Path(..., min_length=3, max_length=5)):
    # TODO: 替换为真实数据/SQL
    return {"unlocode": unlocode.upper(), "dwell": {}}