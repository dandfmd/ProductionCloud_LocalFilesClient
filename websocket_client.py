import websockets
import asyncio
import utils
from constants import SERVER_HOST,LOCAL_SERVER_PORT
from answerable_channels import FunctionalChannel,remote, RemoteException
import logging
import aioconsole
import pathlib
import authenticate_box

class Client(FunctionalChannel):
    
    async def send_ac_message(self,m):
        await _ws.send(m)
    @remote
    async def sync_product_down(self,product_id,strict=False,only_if_existing=True):
        if only_if_existing:
            if product_id not in file_manager.get_all_synced_products():
                return
        await file_manager.sync_product_down(product_id,strict)
client=Client()
server=client.remote


import file_manager #abajo porque file_manager importa server
async def login():
    user_id,login_token=utils.get_user_id(),utils.get_login_token()
    just_logged_in=False
    if not user_id or not login_token:
        #webbrowser.open(SERVER_HOST + '/local-products-login?port='+str(LOCAL_SERVER_PORT), new=0, autoraise=True)
        
        await utils.show_info("Sincronizador de archivos","No hay ningún usuario guardado. Inicia sesión...")
        user_mail,password= await authenticate_box.ask_login()
        if user_mail==None or password==None:
            exit()
        #user_mail= (await aioconsole.ainput("Correo electrónico: ")).strip()
        #password= (await aioconsole.ainput("Contraseña: ")).strip()
        try:
            user_id,login_token=await server.login(mail=user_mail,password=password)
        except RemoteException as e:
            await utils.show_warning("Linarand sincronizador de archivos","Hubo un problema. "+str(e))
            return await login()
        utils.set_user_id(user_id)
        utils.set_login_token(login_token)
        utils.save_data()
        just_logged_in=True
    
    try:
        username= await server.authenticate(user_id=user_id,token=login_token)
    except RemoteException as e:
        await utils.show_warning("Sincronizador de archivos","Hubo un problema. "+str(e)+". Eliminando usuario")
        utils.set_user_id(None)
        utils.set_login_token(None)
        utils.save_data()
        return await login()
    if just_logged_in:
        asyncio.ensure_future(utils.show_info("Sincronizador de archivos","Sesión iniciada como %s. Puedes ir a la página de Ingeniería Linarand y sincronizar los archivos que desees desde este equipo."%username))
async def start():
    
    sync_path=utils.get_sync_path()
    while sync_path is None or not pathlib.Path(sync_path).exists():
        await utils.show_info("Sincronizador de archivos","No hay una carpeta de sincronización guardada. Escoge una...")
        path= await utils.ask_for_folder()
        print(path)
        if not path:
            exit()
        try:
            sync_path=pathlib.Path(path)
            if not sync_path.exists():

                sync_path.mkdir(parents=True,exist_ok=True)
            sync_path=str(sync_path)
            utils.set_sync_path(sync_path)
            utils.save_data()
            
        except:
             await utils.show_warning("Sincronizador de archivos","Ruta inválida")
    await login()
    pds=list(file_manager.get_all_synced_products().keys())
    await server.set_synced_products(products=pds)
    await asyncio.gather(*[file_manager.sync_product_down(p) for p in pds])
    await server.tell_people_to_try_port(port=LOCAL_SERVER_PORT)
    file_manager.start_watchdog()

_exit=False
async def run():
    global _ws
    while not _exit:
        try:
            async with websockets.connect(SERVER_HOST.replace("http", "ws") + '/ws/local-products-client') as ws:
                _ws=ws
                asyncio.ensure_future(start())
                while True:
                    m=await _ws.recv()
                    asyncio.ensure_future(client.on_ac_message(m))
        except Exception as e:
            logging.exception("Client Error")
        if not _exit: await asyncio.sleep(1)
async def exit_():
    global _exit
    _exit=True
    await _ws.close()
