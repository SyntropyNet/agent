import json
import logging
import threading
import time
import queue

from platform_agent.lib.ctime import now

logger = logging.getLogger()


class BatchSender(threading.Thread):

    def __init__(self, client):
        super().__init__()
        self.queue = queue.Queue()
        self.client = client
        self.stop_batch_send = threading.Event()
        self.wg = None
        self.daemon = True

        threading.Thread.__init__(self)

    def get_from_queue(self):
        payloads = {}
        t_end = time.time() + 10  # run for 10 second
        while time.time() < t_end:
            try:
                message = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            msg_type = message['msg_type']
            if not payloads.get(msg_type):
                payloads[msg_type] = [message.get('data')]
            elif not message.get('data') in payloads[msg_type]:
                payloads[msg_type].append(message.get('data'))
        return payloads

    def run(self):
        while True:
            payloads = self.get_from_queue()
            for msg_type in payloads.keys():
                self.client.send(json.dumps({
                    'id': "ID." + str(now()),
                    'executed_at': now(),
                    "type": msg_type,
                    "data": payloads[msg_type]
                }))

    def join(self, timeout=None):
        self.stop_batch_send.set()
        super().join(timeout)

