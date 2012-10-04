import torrent
import manager
import tracker_client
import storage
import logging
import peer_id as id

import time
import sys
import socket
import threading

logger = logging.getLogger('bittorrent')

def setup_logger(level = logging.INFO):
    #global logger
    #logger = logging.getLogger('bittorrent')
    logger.setLevel(level)
    sthl = logging.StreamHandler()
    formatter = logging.Formatter(\
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sthl.setFormatter(formatter)
    logger.addHandler(sthl)

class Client(object):
    def __init__(self):
        self._peer_id = id.generate()
        self._acceptor = manager.ConnectionAcceptor()
        self._wait = threading.Condition()
        
        self._started = False

    @property
    def peer_id(self):
        return self._peer_id

    @property
    def connection_acceptor(self):
        return self._acceptor

    @property
    def managers(self):
        return self._acceptor.managers

    def manager(self, info_hash):
        return self.managers.get(info_hash, None)

    def halt(self):
        for info_hash, manager in self.managers.items():
            manager.halt()

        try:
            self._acceptor.halt()
        except socket.error as err:
            pass

    def wait(self):
        with self._wait:
            self._wait.wait()

    def halt_manager(self, info_hash):
        man = self.manager(info_hash)
        if not man is None:
            man.halt()
            self._acceptor.remove_manager(info_hash)

        return man

    def start(self, torrent_path_or_content):
        meta = None
        if isinstance(torrent_path_or_content, bytes):
            meta = torrent.Torrent(torrent_path_or_content)
        else:
            meta = torrent.Torrent.from_file(torrent_path_or_content)
        
        store = storage.SynchronizedStorage(meta)

        coord = manager.PeerManager(\
            self._peer_id, self._acceptor, meta, store)
        tracker = tracker_client.AsyncTrackerManager(\
            coord, store.missing(), self._acceptor.port)
        coord.set_tracker(tracker)

        coord.start()

        if not self._started:
            self._started = True
            self._acceptor.start()

    #time.sleep(120)

    #coord.halt()

if __name__ == '__main__':
    torrent_path = 'trusted-computing.torrent'

    setup_logger()

    client = Client()

    try:
        client.start(torrent_path)
        client.wait()
    except Exception as e:
        logger.exception(e)
        sys.exit(0)
