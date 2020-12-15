import logging
import os
import json
import socket
import queue
import threading
import traceback
import time

import requests
import websocket

from platform_agent.lib.ctime import now
from platform_agent.agent_api import AgentApi
from platform_agent.config.logger import PublishLogToSessionHandler
from platform_agent.wireguard.helpers import check_if_wireguard_installled
from platform_agent.__main__ import __version__

logger = logging.getLogger()


class AgentRunner:

    STOP_MESSAGE = now()

    def __init__(self, ws):
        self.ws = ws
        self.queue = queue.Queue()
        self.active = None
        self.agent_api = AgentApi(self)

        logging.root.addHandler(PublishLogToSessionHandler(self))

    def run(self):
        while True:
            message = self.queue.get()
            if message == self.STOP_MESSAGE:
                break
            request = json.loads(message)
            logger.debug(f"[RUNNER] Parsed request | {request}")
            try:
                result = self.agent_api.call(request['type'], request['data'], request['id'])
            except:  # noqa
                # Catch all exceptions that not handled
                traceback.print_exc()
                result = {
                    'error': {
                        'traceback': traceback.format_exc(),
                        'payload': request
                    }
                }
                logger.error(result)
            self.queue.task_done()
            logger.debug(f"[RUNNER] Result | {result}")
            if result:
                payload = self.create_response(request, result)
                self.send(payload)

    @staticmethod
    def create_response(request, result):
        payload = {
            'id': request['id'],
            'executed_at': now(),
            'type': request['type'],
        }
        if isinstance(result, dict) and ('error' in result):
            payload.update(result)
        else:
            payload.update({'data': result})
        return json.dumps(payload)

    def send(self, message):
        status = getattr(self.ws, 'sock')
        if status and status.status:
            logger.debug(f"[SENDING]: {message}")
            try:
                self.ws.send(message)
            except:
                pass
        else:
            logger.error("[SENDING]: websocket offline")

    def send_log(self, message):
        status = getattr(self.ws, 'sock')
        if status and status.status:
            try:
                self.ws.send(message)
            except:
                pass


class WebSocketClient(threading.Thread):

    def __init__(self, host, api_key, ssl="wss"):
        threading.Thread.__init__(self)

        if check_if_wireguard_installled():
            status = 'OK'
        else:
            status = 'WG_ERROR'

        self.host = host
        self.active = True
        websocket.enableTrace(False)
        self.connection_url = f"{ssl}://{host}"
        self.ws = websocket.WebSocketApp(
            self.connection_url,
            header={
                'authorization': api_key,
                'x-deviceid': self.generate_device_id(),
                'x-devicename': os.environ.get('SYNTROPY_AGENT_NAME', socket.gethostname()),
                'x-devicestatus': status,
                'x-agentversion': __version__,
            },
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
            on_open=self.on_open
        )
        self.agent_runner = AgentRunner(self.ws)
        threading.Thread(target=self.agent_runner.run).start()
        self.ws.on_message = self.on_message
        self.ws.on_open = self.on_open

    def run(self):
        while True and self.active:
            logger.debug(f"[AGENT-{__version__}] Connecting {self.connection_url}")
            self.ws.run_forever(ping_interval=60, ping_timeout=10)
            logger.warning(f"[AGENT-{__version__}] Disconnected {self.connection_url}")
            time.sleep(10)

    def on_message(self, message):
        logger.debug(f"[WEBSOCKET] Received | {message}")
        logger.debug(f"[WEBSOCKET] Queue size | {self.agent_runner.queue.qsize()}")
        self.agent_runner.queue.put(message)

    def on_error(self, error):
        self.agent_runner.active = False
        logger.error(f"[WEBSOCKET] Error | {error}")
        self.ws.close()
        time.sleep(10)

    def on_close(self):
        self.agent_runner.active = False
        logger.debug("[WEBSOCKET] Close")
        time.sleep(10)

    def on_open(self):
        logger.debug("[WEBSOCKET] Connection open")
        self.agent_runner.active = True

    def stop(self):
        self.ws.close()
        self.agent_runner.active = False
        self.agent_runner.queue.put(self.agent_runner.STOP_MESSAGE)

    @staticmethod
    def getserial():
        # Extract serial from cpuinfo file
        cpuserial = "0000000000000000"
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:6] == 'Serial':
                cpuserial = line[10:26]
        f.close()

        return cpuserial

    def generate_device_id(self):
        try:
            with open('/sys/class/dmi/id/product_uuid', 'r') as file:
                machine_id = file.read().replace('\n', '')
        except FileNotFoundError:
            try:
                with open('/etc/machine-id', 'r') as file:
                    machine_id = file.read().replace('\n', '') + requests.get("https://ip.syntropystack.com/").json()
            except FileNotFoundError:
                machine_id = self.getserial()

        return machine_id

