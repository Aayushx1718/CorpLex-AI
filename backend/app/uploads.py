"""Whole-request cap prevents multipart spooling of unbounded bodies."""
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from app.extraction import MAX_FILE_BYTES


class UploadLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        limit = MAX_FILE_BYTES + 64 * 1024  # bounded form overhead
        headers = dict(scope['headers'])
        try:
            declared = int(headers.get(b'content-length', b'0'))
            if declared < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length.'}, status_code=400)(scope, receive, send)
        if declared > limit:
            return await JSONResponse({'detail': 'Upload request exceeds the size limit.'}, status_code=413)(scope, receive, send)
        consumed = 0

        async def bounded_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get('body', b''))
            if consumed > limit:
                raise HTTPException(413, 'Upload request exceeds the size limit.')
            return message

        await self.app(scope, bounded_receive, send)
