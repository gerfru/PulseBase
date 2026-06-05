import asyncio

_RESPONSE = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/json\r\n"
    b"Content-Length: 15\r\n"
    b"\r\n"
    b'{"status":"ok"}'
)


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        await reader.read(1024)
        writer.write(_RESPONSE)
        await writer.drain()
    finally:
        writer.close()


async def start_health_server(port: int = 8080) -> None:
    server = await asyncio.start_server(_handle, "0.0.0.0", port)  # nosec B104
    asyncio.get_event_loop().create_task(server.serve_forever())
