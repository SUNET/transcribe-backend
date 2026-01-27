from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        self.active[user_id].remove(ws)
        if not self.active[user_id]:
            del self.active[user_id]

    async def send_to_user(self, user_id: str, payload: dict):
        for ws in self.active.get(user_id, []):
            await ws.send_json(payload)
