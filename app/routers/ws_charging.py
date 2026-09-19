import json
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..services.charging_engine import ChargingEngine

router = APIRouter(tags=["WebSockets"])

class ConnectionManager:
    """Manages active WebSocket connections and message broadcasting."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        payload = json.dumps(message)
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

def setup_ws_broadcaster():
    """Hooks the WebSocket manager broadcast function into ChargingEngine."""
    ChargingEngine.register_listener(manager.broadcast)

@router.websocket("/ws/station/{station_code}")
async def websocket_station_endpoint(websocket: WebSocket, station_code: str):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({
            "event": "CONNECTED",
            "station_code": station_code,
            "message": f"Terhubung ke live stream SPKLU '{station_code}'"
        }))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
