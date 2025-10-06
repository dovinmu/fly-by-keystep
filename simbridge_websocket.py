import asyncio
import websockets

async def proxy(websocket, path):
    async with websockets.connect("ws://localhost:2048" + path) as ws:
        consumer_task = asyncio.ensure_future(consumer_handler(websocket, ws))
        producer_task = asyncio.ensure_future(producer_handler(websocket, ws))
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()

async def consumer_handler(websocket, ws):
    async for message in websocket:
        await ws.send(message)

async def producer_handler(websocket, ws):
    async for message in ws:
        await websocket.send(message)

start_server = websockets.serve(proxy, "0.0.0.0", 8181)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()