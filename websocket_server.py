from answerable_channels import FunctionalChannel,remote, RemoteException
import websockets
import constants
import logging
import asyncio
from websocket_client import server
import file_manager
import os
import platform
import subprocess

class LocalServer(FunctionalChannel):
    def __init__(self,ws):
        self.ws=ws
        super(LocalServer, self).__init__()
    async def send_ac_message(self,m):
        await self.ws.send(m)
    @remote
    async def sync_file(self,pid):
        await file_manager.sync_product_down(pid)
        
    @remote
    async def stop_sync_file(self,pid):
        await file_manager.stop_sync_product(pid)

    @remote 
    def get_synced_products(self):
        return list(file_manager.get_all_synced_products().keys())
    @remote
    def open_file_exlorer(self,product_id=None):
        if product_id:
            folder=file_manager.get_all_synced_products()[product_id]
        else:
            folder=file_manager.get_sync_folder()
 
        if platform.system() == "Windows":
            os.startfile(str(folder))
        else:
            subprocess.Popen(["xdg-open", str(folder)])
      


_local_server=None    
local_listeners=set()
async def run():
    global _local_server
    async def _handle_connection(websocket, path):
        local_server=LocalServer(websocket)
        local_listeners.add(local_server)
        while True:
            try:
                asyncio.ensure_future(local_server.on_ac_message(await websocket.recv()))
            except websockets.exceptions.ConnectionClosed: break
            except Exception as e:
                logging.exception("Server Error")
        local_listeners.remove(local_server)
    _local_server= await websockets.server.serve(_handle_connection,"",constants.LOCAL_SERVER_PORT)
    await _local_server.wait_closed()
async def exit_():
    if _local_server:_local_server.close()
