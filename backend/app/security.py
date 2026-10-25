"""Optional local bearer auth; production mode refuses insecure startup settings."""
import hmac
from urllib.parse import urlsplit
from fastapi import HTTPException, Request
from starlette.responses import JSONResponse


class SecurityMiddleware:
    def __init__(self,app,settings):self.app,self.settings=app,settings

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope['path'].startswith('/api/'):
            return await self.app(scope,receive,send)
        headers={k.lower():v.decode('latin1') for k,v in scope['headers']}
        if scope['method']=='OPTIONS':return await self.app(scope,receive,send)
        if scope['method'] not in ('GET','HEAD'):
            origin=headers.get(b'origin')
            try:
                same_origin=origin and urlsplit(origin).netloc==headers.get(b'host')
            except ValueError:
                same_origin=False
            if origin and origin not in self.settings.cors_origins and not same_origin:
                return await JSONResponse({'detail':'Request origin is not allowed.'},403)(scope,receive,send)
        token=self.settings.corplex_access_token
        if token and scope['path'] not in ('/api/health','/api/access'):
            authorization=headers.get(b'authorization','')
            provided=authorization[7:] if authorization.startswith('Bearer ') else ''
            if not hmac.compare_digest(provided.encode(),token.encode()):
                return await JSONResponse({'detail':'A valid workspace access token is required.'},401)(scope,receive,send)
        await self.app(scope,receive,send)


def require_reviewer(request:Request,settings):
    if settings.corplex_review_token:
        provided=request.headers.get('X-Review-Token','')
        if not hmac.compare_digest(provided.encode(),settings.corplex_review_token.encode()):
            raise HTTPException(403,'A valid reviewer token is required for this action.')
