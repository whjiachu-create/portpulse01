from fastapi.openapi.utils import get_openapi

def add_api_key_security(app):
    def custom_openapi():
        # 允许 FastAPI 先缓存 schema，避免重复生成
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title="PortPulse API",
            version="0.1.1",
            routes=app.routes,
        )
        comps = schema.setdefault("components", {})
        sec = comps.setdefault("securitySchemes", {})
        sec["ApiKeyAuth"] = {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        schema["security"] = [{"ApiKeyAuth": []}]
        app.openapi_schema = schema
        return app.openapi_schema
    # 用我们的函数替换 openapi 生成器（仅影响文档，不影响路由执行）
    app.openapi = custom_openapi
