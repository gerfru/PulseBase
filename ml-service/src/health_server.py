import asyncio
from typing import Any

_RESPONSE_OK = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: 15\r\n"
    b"\r\n"
    b'{"status":"ok"}'
)
_RESPONSE_503 = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: 22\r\n"
    b"\r\n"
    b'{"status":"not ready"}'
)

_pool: Any = None


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        data = await reader.read(1024)
        path = data.split(b" ")[1] if b" " in data else b"/"
        if path.startswith(b"/ready") and _pool is not None:
            try:
                await _pool.fetchval("SELECT 1")
                writer.write(_RESPONSE_OK)
            except Exception:
                writer.write(_RESPONSE_503)
        else:
            writer.write(_RESPONSE_OK)
        await writer.drain()
    finally:
        writer.close()


async def start_health_server(port: int = 8080, pool: Any = None) -> None:
    global _pool
    _pool = pool
    server = await asyncio.start_server(_handle, "0.0.0.0", port)  # nosec B104
    asyncio.get_running_loop().create_task(server.serve_forever())
