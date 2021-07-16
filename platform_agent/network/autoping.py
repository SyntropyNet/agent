import json
import logging
import threading
import time

from icmplib import multiping

from platform_agent.lib.ctime import now

logger = logging.getLogger()


class AutopingClient(threading.Thread):

    def __init__(self, client, ips, interval, response_limit=5):
        super().__init__()
        self.client = client
        self.interval = interval
        self.response_limit = response_limit
        self.hosts = ips
        self.stop_autoping = threading.Event()
        self.daemon = True
        threading.Thread.__init__(self)

    def run(self, max_threads=1000):
        while not self.stop_autoping.is_set():
            pings = []
            ping_res = multiping(self.hosts, count=2, interval=0.5, max_threads=max_threads)
            max_threads = 2
            ping_res.sort(key=lambda x: x.avg_rtt)
            for res in ping_res:
                if res.is_alive:
                    pings.append({
                        "ip": res.address,
                        "latency_ms": res.avg_rtt if res.is_alive else -1,
                        "packet_loss": res.packet_loss if res.is_alive else 1
                    })
                if len(pings) >= self.response_limit:
                    break

            self.client.send_log(json.dumps({
                'id': "ID." + str(time.time()),
                'executed_at': now(),
                'type': 'AUTO_PING',
                'data': {"pings": pings}
            }))
            time.sleep(int(self.interval))

    def join(self, timeout=None):
        self.stop_autoping.set()
        super().join(timeout)
