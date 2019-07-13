import json,os,shelve
import asyncio,sys
from tkinter import filedialog,Tk,messagebox
from pathlib import Path

import functools
DATAFILENAME="data"
def set_user_id(new_id):
    _local_data["user_id"]=new_id
def set_login_token(token):
    _local_data["login_token"]=token
def load_data():
    global _local_data
    if(os.path.exists(os.path.join(get_current_path(),DATAFILENAME))):
        with open(os.path.join(get_current_path(),DATAFILENAME), 'r') as f:       
            try:
                _local_data=json.loads(f.read())
            except: _local_data={}
    else:_local_data={}
    

def save_data():
    with open(os.path.join(get_current_path(),DATAFILENAME), 'w') as f:       
        f.write(json.dumps(_local_data))
def get_user_id():
    return _local_data.get("user_id")
def get_login_token():
    return _local_data.get("login_token")
def get_template_path():
    return os.path.join(get_current_path(),"templates")
def get_current_path():
    if getattr(sys, 'frozen', False):
        # we are running in a bundle
        f = sys.executable
    else:
        # we are running in a normal Python environment
        f = __file__
    return os.path.dirname(os.path.abspath(f))
def get_client_version():
    VERSIONFILE="client_version"
    with open(os.path.join(get_current_path(),VERSIONFILE), 'r') as f:
        return float(f.read().strip())
def get_sync_path():
    return _local_data.get("sync_path",None)
def set_sync_path(path):
    _local_data["sync_path"]=path
record=None
from contextlib import closing
import aiohttp # $ pip install aiohttp
download_semaphore = asyncio.Semaphore(5)
async def download_file(url,path):
    chunk_size=1<<15
    async with download_semaphore:
        with closing(aiohttp.ClientSession()) as session:
            filename = str(path)
            response = await session.get(url)
            with closing(response), open(filename, 'wb') as file:
                while True: # save file
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    file.write(chunk)
    return filename
upload_semaphore = asyncio.Semaphore(5)
async def upload_file(url,data):
    async with upload_semaphore:
        with closing(aiohttp.ClientSession()) as session:
            return await session.post(url, data=data)
import hashlib

def file_md5(filename):
    h = hashlib.md5()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(lambda : f.read(128*1024), b''):
            h.update(b)
    return h.hexdigest()



async def ask_for_folder():
    def ask():
        t=Tk()
        t.withdraw()
        a=filedialog.askdirectory(initialdir =str(Path.home()),title = "Escoge una carpeta para sincronizar (vacía)",mustexist = False)
        t.destroy()
        return a
    return await asyncio.get_event_loop().run_in_executor(None, ask)
async def _show_warning(title,message,f):
    def ask():
        t=Tk()
        t.withdraw()
        f(title, message)
        t.destroy()
    return await asyncio.get_event_loop().run_in_executor(None, ask)
async def show_info(title,message):
    return await _show_warning(title,message,messagebox.showinfo)
async def show_warning(title,message):
    return await _show_warning(title,message,messagebox.showwarning)

