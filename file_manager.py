from pathlib import Path
import utils
from websocket_client import server
import pickle
import shutil
import asyncio
import constants
import contextlib
import requests
import os
import shelve
from collections import OrderedDict
import ctypes
from watchdog.events import FileSystemEventHandler, DirModifiedEvent,\
    FileModifiedEvent
from watchdog.observers import Observer
import watchdog.events
from aiohttp.formdata import FormData
from collections import defaultdict
from concurrent.futures.thread import ThreadPoolExecutor
from time import time
from contextlib import contextmanager

INFO_FILE_NAME=".linarandsync"
def get_all_synced_products():
    prods=OrderedDict()
    for f in sorted(get_sync_folder().iterdir(),key=lambda p:p.name.lower()):
        if f.is_dir():
            with load_data_file(f) as df:
                p=df.get("id",None)
                if p is not None:
                    prods[p]=f
    return prods
                
def get_sync_folder():
    return Path(utils.get_sync_path())
async def server_set_synced_products():
    return await server.set_synced_products(products=list(get_all_synced_products().keys()))



def clone_dir(source_folder,dest_folder):
    if os.path.isdir(source_folder):
        source_files = os.listdir(source_folder)
        for source_file in source_files:
                source_file_extension = os.path.splitext(os.path.split(source_file)[-1])[-1]
                dest_file_name = "".join([os.path.split(dest_folder)[-1],source_file_extension])
                dest_file_path = os.path.join(dest_folder,dest_file_name)
                if not os.path.exists(dest_file_path):shutil.copy2(os.path.join(source_folder,source_file),dest_file_path)
        return source_files
    else:
        return False
async def stop_sync_product(pid):
    for f in get_sync_folder().iterdir():
        if f.is_dir():
            with load_data_file(f) as df:
                p=df.get("id",None)
            if p ==pid:
                delete_thing(f)
    await server_set_synced_products()
pathlocks=defaultdict(asyncio.Lock)
up_sync_requests={}
def walk_up_to_product_folder(path):
    parents=list(path.parents)
    
    if not get_sync_folder() in parents: return None
    f= ([path]+parents)[parents.index(get_sync_folder())]
    if f.is_file(): return None
    return f

async def sync_product_up(folder_path):

    folder_path=walk_up_to_product_folder(folder_path)

    if folder_path is None: return
    if not folder_path.exists(): 
        await server_set_synced_products() #se borro algo
       
        return 
    if await bundle_identical(folder_path, up_sync_requests, 1): return
    async with pathlocks[folder_path]:
        futs=[]
        with load_data_file(folder_path) as df:
            id_=df.get("id",None)
        if id_ is None:
            print("new product")
            id_=await new_product(folder_path)

            futs.append(server_set_synced_products()) #se borro algo
        
        async with pathlocks[id_]:
            d= {"name":folder_path.name,
                "id":id_,
                "images":[],
                "g_codes":[],
                "files":[]}
            
            file_dict={}
            newfiles=[]
            for f in folder_path.iterdir():
                if f.is_file() and not is_hidden(f):
                    with load_data_file(f) as local_thing_data:
                        _id=local_thing_data.get("id",None)
                        _type=local_thing_data.get("type",None)
                    if _id is None or _type is None:
                        newfiles.append(f)
                    else:
                        d[_type+"s"].append({"id":_id,"name":f.name,"md5":await get_md5(f)})
                        file_dict[(_type,_id)]=f
        
            need_to_upload,weird_ids=await server.update_product(data=d)
            for t,i in need_to_upload:
                futs.append(upload_file(file_dict[(t,i)],i if not (t,i) in weird_ids else ""))
            for f in newfiles:
                futs.append(upload_file(f))
            await asyncio.gather(*futs)

async def sync_product_down(pid,strict=False):
    #si strict es False, los archivos (y sus nombres) se suben en vez de bajarse y archivos que no estén en el servidor se suben.
    #es bueno para cuando se abre el programa, sincronizar cambios que se hayan hecho mientras estaba cerrado
    async with pathlocks[pid]:
        product=await server.get_product_data(product_id=pid)
        if product["trashed"]: 
            await stop_sync_product(pid)
            return
        parent_path=get_sync_folder()
        futs=[]
        existing_synced={}
        

        name=await solve_potential_conflict(product,"product",[product],parent_path)
        child_path=parent_path / name
        for current_f in parent_path.iterdir():
            if current_f.is_dir():
                with load_data_file(current_f) as df:
                    id_=df.get("id",None)
                if product["id"]==id_:
                    if child_path!=current_f:
                        current_f.rename(child_path) 
                        
                        with load_data_file(child_path) as df:
                            df["name"]=product["name"]
                    break
        else:
            child_path.mkdir(parents=True, exist_ok=True)
            futs.append(server_set_synced_products())
            #Clona la carpeta de templates dfmd
            #if type_=="product" and len(thing["images"]+thing["g_codes"]+thing["files"])==0:
            #    clone_dir(utils.get_template_path(),str(child_path))
                
            with load_data_file(child_path) as child_data:
                child_data["id"]=product["id"]
                child_data["name"]=product["name"]
        
        all_files=product["images"]+product["g_codes"]+product["files"]
        inexisting_files_in_server={f for f in child_path.iterdir() if f.is_file() and not is_hidden(f)}
        for file_type in ["image","g_code","file"]:
            file_things=product[file_type+"s"]
            for file_thing in file_things:
                name=await solve_potential_conflict(file_thing,file_type,all_files,child_path)
                file_path=child_path / name
                inexisting_files_in_server.discard(file_path)
                if not file_path.exists() or strict:
                    if not file_path.exists(): file_path.open("a").close() #lo creamos para detectar conflictos
                    with load_data_file(file_path) as local_thing_data:
                        local_thing_data["id"]=file_thing["id"]
                        local_thing_data["type"]=file_type
                        local_thing_data["name"]=file_thing["name"]
                    
                    if not file_path.exists() or file_thing["md5"]!=await get_md5(file_path): 
                        futs.append(utils.download_file(constants.SERVER_HOST+ file_thing["url"],str(file_path)))

                else:
                    
                    futs.append(update_file_if_changed(file_path))
        for inexisting_file in inexisting_files_in_server:
            if not strict:
                futs.append(delete_or_upload_new_thing(inexisting_file))
            else:
                delete_thing(inexisting_file)
    
                    
        await asyncio.gather(*futs)
        
    

async def solve_potential_conflict(thing,thing_type,siblings,parent_path,conflict_prefix=None):
    with load_data_file(parent_path) as data:
        conflict_list=thing_type+"_conflicts"
        if conflict_prefix is None:
            conflict_prefix=data.get(conflict_list,{}).get(thing["id"],0)
    name=thing["name"]
    if conflict_prefix:
        name=(conflict_prefix*"\u00A0")+name #trucazo
    thing_path= parent_path / name
    if thing_path.exists():
        with load_data_file(thing_path) as local_thing_data:
            other_id=local_thing_data.get("id")
            
        if other_id!=thing["id"]:
            conflict_exists=thing_type=="product" or (other_id in (s["id"] for s in siblings))
            if conflict_exists: 
                return await solve_potential_conflict(thing,thing_type,siblings,parent_path,conflict_prefix+1)        
            else:
                delete_thing(thing_path)
    
    with load_data_file(parent_path) as data:
        if conflict_prefix ==0:
            data.setdefault(conflict_list,{}).pop(thing["id"],None)
        else:
            data.setdefault(conflict_list,{})[thing["id"]]=conflict_prefix
        return name
    
async def delete_or_upload_new_thing(path):
    with load_data_file(path) as info:
        id_=info.get("id",None)
    if id_!=None:
        delete_thing(path) #es un archivo que se habia sincronizado y ya no esta, se borro desde el servidor y lo borramos entonces
    else:
        await upload_file(path)



async def upload_file(path,existing_id=""):   
    if not path.exists():return 
    with load_data_file(path.parent) as parent_data_file:
        parent_id=parent_data_file["id"]
        if parent_id is None: return
    with path.open("rb") as file:
        data = FormData(fields=[("existing_id",existing_id),("product_id",str(parent_id)),("token",utils.get_login_token()),("user_id",str(utils.get_user_id()))],quote_fields=False)
        data.add_field("file", file,filename=path.name)
        resp=await (await utils.upload_file(constants.SERVER_HOST+ "/_back/product-sync-upload",data)).json()
        with load_data_file(path) as data:
            data["id"]=resp.get("id",data.get("id",None))
            data["type"]=resp.get("type",data.get("type",None))
            data["name"]=path.name


async def new_product(path):
    id_=await server.create_product(name=path.name)
    with load_data_file(path) as data:
        data["id"]=id_
        data["name"]=path.name
    return id_
def delete_data_file(path):
    p=get_data_file_path(path)
    if p:
        for n in [p]+[p.with_name(p.name+suff) for suff in [".dat",".bak",".dir"]]:
            if n.exists():
                n.unlink()
def get_data_file_path(path):
    if path.is_dir():
        p=path/INFO_FILE_NAME
    else:
        if is_hidden(path): return None

        p=path.parent/(INFO_FILE_NAME+path.name)
    return p


is_windows= os.name == 'nt'



def load_data_file(path):
    assert path.exists(), "Path %s does not exist"%path
    p=get_data_file_path(path)
    if not p:return shelve.Shelf({}) #no nos deben pedir info por archivos de info, pero si pasara, devolver un dict es lo menos agresivo
    s= shelve.open(str(p),writeback=True)
    if is_windows:
        old_close=s.close
        def hide():
            for n in [p]+[p.with_name(p.name+suff) for suff in [".dat",".bak",".dir"]]:
                if n.exists():
                    ctypes.windll.kernel32.SetFileAttributesW(str(n), 2)
             
        def new_close():
            old_close()
            hide()
        hide()
        s.close=new_close
    return contextlib.closing(s)
                

def delete_thing(path):
    if path.exists():
        if path.is_dir():
            shutil.rmtree(str(path), ignore_errors=True)
        else:
            delete_data_file(path)
            path.unlink()
                
hashing_executor = ThreadPoolExecutor(max_workers=20)



async def bundle_identical(key,bundle_dict,bundle_time=0.3):
    my_check=object()
    last_change_checks[key]=my_check
    await asyncio.sleep(bundle_time)
    last=last_change_checks.get(key,None)
    if my_check is not last:return True
    del last_change_checks[key]
    return False

last_change_checks={}
async def update_file_if_changed(path):
    if is_hidden(path): return
    if not path.exists():return
    
    if await bundle_identical(path,last_change_checks,bundle_time=1): return

    if not path.exists():return
    with load_data_file(path) as d:
        id_=d.get("id",None)
        name=d.get("name",path.name)
        
    if id_ is None: 
        return await upload_file(path)
    
    
    server_md5= await server.set_name_and_get_hash_if_same_size(file_id=id_,file_size=path.stat().st_size,name=name)
    if server_md5 is not None:
        changed=(await get_md5(path))!=server_md5
    else: 
        changed=True
    if changed: await upload_file(path,id_)
async def get_md5(path):
    with load_data_file(path) as d:
            md5=d.get("md5",None)
            md5_creation=d.get("md5_date",None)
        
    last_modified=path.stat().st_mtime
    if md5 is None or md5_creation!=last_modified:
        md5=await asyncio.get_event_loop().run_in_executor(hashing_executor,utils.file_md5,str(path))
        with load_data_file(path) as d:
            d["md5"]=md5
            d["md5_date"]=last_modified
    return md5
class WatchDogHandler(FileSystemEventHandler):
    def __init__(self,loop):
        self.loop=loop
        super(WatchDogHandler, self).__init__()
    pathlocks=defaultdict(asyncio.Lock)
    ingnore_paths=set()
    
    last_touched={}
    async def wait_for_calm(self,path):
        WAIT_TIME=0.5
        paths={path}
        n_path=path
        while n_path.exists() and not n_path==get_sync_folder() and (n_path.parent in WatchDogHandler.last_touched or n_path==path):
            paths.add(n_path.parent)
            n_path=n_path.parent
        for f in paths:
            WatchDogHandler.last_touched[f]=time()
        while True:
            for f in paths:
                if time()- WatchDogHandler.last_touched[f]>WAIT_TIME:
                    break
            else:
                await asyncio.sleep(WAIT_TIME)
                continue
            break
            
    def dispatch(self, event):
        
        f=Path(event.src_path)

        if not is_hidden(f) and f!=get_sync_folder():
            for ignore in WatchDogHandler.ingnore_paths:
                if ignore in [f]+[p for p in f.parents]:
                    return
            _method_map = {
                watchdog.events.EVENT_TYPE_MODIFIED: self.on_modified,
                watchdog.events.EVENT_TYPE_MOVED: self.on_moved,
                watchdog.events.EVENT_TYPE_CREATED: self.on_created,
                watchdog.events.EVENT_TYPE_DELETED: self.on_deleted,
            }
            event_type = event.event_type
            function=_method_map[event_type]
            self.loop.call_soon_threadsafe(lambda: asyncio.ensure_future(function(event)))
            
    last_modified_event={}
    async def on_modified(self, event):
        p=Path(event.src_path)
        await sync_product_up(p)
            
    async def on_created(self, event):
        p=Path(event.src_path)           
        await sync_product_up(p)
        
        
    async def on_moved(self, event):
        p=Path(event.src_path)
        new=Path(event.dest_path)
        await asyncio.gather(sync_product_up(new),sync_product_up(p))

    async def on_deleted(self, event):
        p=Path(event.src_path)
        await sync_product_up(p)
 
observer=None
def start_watchdog():
    global observer
    observer = Observer()
    observer.schedule(WatchDogHandler(asyncio.get_event_loop()), path=utils.get_sync_path(),recursive=True)
    observer.start()
def stop_watchdog():
    global observer
    if observer:
        observer.stop()
IGNORE_ENDINGS={"bak"}
def is_hidden(path):
    return any(path.suffix.endswith(end) for end in IGNORE_ENDINGS) or path.name.startswith(".") or has_hidden_attribute(str(path))
def has_hidden_attribute(filepath):
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(filepath)
        assert attrs != -1
        result = bool(attrs & 2)
    except (AttributeError, AssertionError):
        result = False
    return result
