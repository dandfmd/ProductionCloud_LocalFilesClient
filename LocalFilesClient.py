#esto es para poder congelar a exe, hay un problema con aioconsole si no
import builtins
def help(*args,**kwds):
    pass
builtins.help=help

import websocket_client,websocket_server
import asyncio
import logging
import os.path
import sys
import utils
logger = logging.getLogger()
logPan = os.path.join(os.path.dirname( __file__ ), "log.log")
fh = logging.FileHandler(logPan)
fh.setLevel(logging.ERROR)
formatter = logging.Formatter("%(asctime)s:%(name)s:"
    "%(levelname)s:%(message)s")
fh.setFormatter(formatter)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.DEBUG)
console.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(console)


utils.load_data()
ev=asyncio.get_event_loop()
ev.slow_callback_duration=5*60
asyncio.ensure_future(websocket_client.run())
asyncio.ensure_future(websocket_server.run())
ev.set_debug(True)
ev.run_forever()
