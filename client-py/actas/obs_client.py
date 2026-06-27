"""Cliente obs-websocket v5 (síncrono, sobre websockets) para controlar OBS.

Maneja el handshake de autenticación (SHA256) y las requests start/stop record,
listar dispositivos de salida y aplicar el device_id elegido.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from contextlib import contextmanager

import websockets


class ObsError(Exception):
    pass


def _auth_string(password: str, salt: str, challenge: str) -> str:
    secret = base64.b64encode(
        hashlib.sha256((password + salt).encode("utf-8")).digest()
    ).decode()
    return base64.b64encode(
        hashlib.sha256((secret + challenge).encode("utf-8")).digest()
    ).decode()


class ObsClient:
    """Conexión efímera a OBS: se usa con `with ObsClient(...) as obs:`."""

    def __init__(self, url: str, password: str, timeout: float = 8.0):
        self.url = url
        self.password = password
        self.timeout = timeout
        self._ws = None
        self._loop = asyncio.new_event_loop()

    def __enter__(self) -> "ObsClient":
        self._loop.run_until_complete(self._connect())
        return self

    def __exit__(self, *exc):
        try:
            self._loop.run_until_complete(self._close())
        finally:
            self._loop.close()

    async def _connect(self):
        self._ws = await asyncio.wait_for(
            websockets.connect(self.url, max_size=None), self.timeout
        )
        hello = json.loads(await self._ws.recv())
        d = hello.get("d", {})
        identify = {"op": 1, "d": {"rpcVersion": 1}}
        auth = d.get("authentication")
        if auth:
            identify["d"]["authentication"] = _auth_string(
                self.password, auth["salt"], auth["challenge"]
            )
        await self._ws.send(json.dumps(identify))
        ident = json.loads(await self._ws.recv())
        if ident.get("op") != 2:
            raise ObsError(f"OBS no identificó la sesión (op={ident.get('op')})")

    async def _close(self):
        if self._ws is not None:
            await self._ws.close()

    async def _request(self, req_type: str, data: dict | None = None) -> dict:
        req_id = f"r-{req_type}"
        msg = {"op": 6, "d": {"requestType": req_type, "requestId": req_id}}
        if data:
            msg["d"]["requestData"] = data
        await self._ws.send(json.dumps(msg))
        while True:
            resp = json.loads(await asyncio.wait_for(self._ws.recv(), self.timeout))
            if resp.get("op") == 7 and resp["d"].get("requestId") == req_id:
                status = resp["d"].get("requestStatus", {})
                if not status.get("result", False):
                    raise ObsError(
                        f"{req_type} falló: {status.get('comment', status)}"
                    )
                return resp["d"].get("responseData", {}) or {}

    def request(self, req_type: str, data: dict | None = None) -> dict:
        return self._loop.run_until_complete(self._request(req_type, data))

    # --- API de alto nivel ---

    def input_exists(self, input_name: str) -> bool:
        r = self.request("GetInputList")
        return any(i.get("inputName") == input_name for i in r.get("inputs", []))

    def list_output_devices(self, input_name: str, retries: int = 8) -> list[dict]:
        """Lista las salidas de audio que ve OBS para esa fuente.

        OBS puede no tener la fuente lista justo tras arrancar; reintenta hasta
        que aparezcan dispositivos reales (más que solo 'default').
        """
        import time as _t

        last: list[dict] = []
        for _ in range(retries):
            if not self.input_exists(input_name):
                _t.sleep(0.6)
                continue
            r = self.request(
                "GetInputPropertiesListPropertyItems",
                {"inputName": input_name, "propertyName": "device_id"},
            )
            items = r.get("propertyItems", [])
            last = [
                {"label": it["itemName"], "id": it["itemValue"]}
                for it in items
                if it.get("itemName") and it.get("itemValue")
            ]
            # más de un dispositivo = OBS ya enumeró el audio del sistema
            if len(last) > 1:
                return last
            _t.sleep(0.6)
        return last

    def set_device(self, input_name: str, device_id: str) -> None:
        self.request(
            "SetInputSettings",
            {"inputName": input_name, "inputSettings": {"device_id": device_id}},
        )

    def set_gain(self, input_name: str, db: float, filter_name: str = "ActasGain") -> None:
        """Aplica (o actualiza) un filtro de ganancia en dB a la fuente de audio.

        Compensa el bajo nivel de captura de salidas HDMI/NVIDIA (parlantes de
        monitor). Si db == 0, deshabilita el filtro.
        """
        try:
            # ¿existe ya el filtro?
            self.request(
                "GetSourceFilter",
                {"sourceName": input_name, "filterName": filter_name},
            )
            exists = True
        except ObsError:
            exists = False

        if not exists and db != 0:
            self.request(
                "CreateSourceFilter",
                {
                    "sourceName": input_name,
                    "filterName": filter_name,
                    "filterKind": "gain_filter",
                    "filterSettings": {"db": float(db)},
                },
            )
        elif exists:
            self.request(
                "SetSourceFilterSettings",
                {
                    "sourceName": input_name,
                    "filterName": filter_name,
                    "filterSettings": {"db": float(db)},
                },
            )
            self.request(
                "SetSourceFilterEnabled",
                {
                    "sourceName": input_name,
                    "filterName": filter_name,
                    "filterEnabled": db != 0,
                },
            )

    def start_record(self) -> None:
        self.request("StartRecord")

    def stop_record(self) -> str:
        r = self.request("StopRecord")
        return r.get("outputPath", "")
