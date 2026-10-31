from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.db.models import User
from app.db.session import SessionLocal
from app.services.hub import hub

router = APIRouter()


@router.websocket("/ws/monitoring")
async def monitoring(ws: WebSocket, token: str = ""):
    try:
        payload = decode_token(token)
        with SessionLocal() as db:
            user = db.get(User, int(payload["sub"]))
            if user is None or not user.active:
                raise ValueError
            info = {"user_id": user.id, "access_role": user.access_role, "staff_id": user.staff_id}
    except Exception:
        await ws.close(code=4401)
        return
    await hub.connect(ws, info)
    try:
        await ws.send_json({"type": "hello", "data": {"role": info["access_role"]}})
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text('{"type":"pong","data":{}}')
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(ws)
