import logging
import threading
import time
import random
from urllib.request import URLError
import socket

import storage
import peer
import utils
import bitfield
import protocol
import tracker_client

# TODO LIST
# Send bitfield after handshake - DONE
# Implement unchoke_peers - DONE
# Add more logging
# Add close methods to storage, manager and acceptor - DONE
# Add error handling - DONE
# Send tracker request and connect to peers (every interval?) - DONE
# Implement stale in download task - DONE
# Start everything up from given torrent file - DONE
# Check with peers if we are still interested after receiving a piece
# Handshake should be done in an another thread - DONE
# Modify Peer: invalid message received, task never called again. - FIXED
# PeerManager: remove pieces from wanted_pieces when requested - DONE
# Connection queuing. Send multiple requests to peer when ready. - DONE
# Bitfield is optional and only sent at the begining. - DONE
# In peer. Handshake: except ValueError => close socket - DONE
# PeerManager: wanted_pieces and tasks == interesting pieces - DONE
# PeerManager: save the unused peers received from tracker
# PeerManager, Storage => AsyncStorage - NOPE
# Missing: snubbed, endgame and stale (DONE)

_logger = logging.getLogger('bittorrent.manager')

# Typical port range for bittorrent clients
PORTS = range(6881, 6890)

# If a interval is not specified use this
#TRACKER_INTERVAL = 300 #seconds

BLOCK_LENGTH = 16384 #bytes

UNCHOKE_INTERVAL = 10 #seconds
OPTIMISTIC_UNCHOKE = 3
MAX_DOWNLOADERS = 4

MAX_TASKS = 5
#MAX_DOWNLOADS = 10
MAX_PEERS = 30
DELTA_PEERS = 5

STALE = 120 #seconds

class ConnectionAcceptor(threading.Thread):
    def __init__(self, ports = PORTS):
        threading.Thread.__init__(self)
        self.daemon = True

        #self._manager = man
        self._managers = {}
        
        self._port, self._socket = self._connect(ports)

        #self._socket = socket.socket()
        #self._socket.bind(('localhost', port))
        #self._listen(5)

    def _connect(self, ports):
        if isinstance(ports, str) or isinstance(ports, int):
            ports = [int(ports)]

        for port in ports:
            try:
                sock = socket.socket()
                sock.bind(('localhost', port))
                sock.listen(5)
                _logger.info("Listening on port %d" % port)
                return port, sock
            except socket.error:
                pass

        _logger.critical("Unable to bind to a port")
        raise socket.error("Could not bind to a port")

    @property
    def managers(self):
        return self._managers

    @property
    def port(self):
        return self._port

    def halt(self):
        self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()

    def add_manager(self, manager):
        info_hash = manager.torrent.info_hash
        if not info_hash in self._managers:
            self._managers[info_hash] = manager

    def remove_manager(self, info_hash):
        if info_hash in self._managers:
            del self._managers[info_hash]

    def run(self):
        try:
            while True:
                sock, addr = self._socket.accept()
                peer.accept_handshake(sock, addr, self._managers.values())
                #if self._manager.need_more():
                #    peer.accept_handshake(sock, addr, \
                #                              self._managers.values())
                #else:
                #    try:
                #        sock.close()
                #    except socket.error:
                #        pass
                #try:
                    # Should be done in a separate thread
                #    peer = peer.handshake(sock, addr, \
                #        self._manager.peer_id, self._manager.torrent)
                #    self._manager.add_peer(peer)
                #except (ValueError, TypeError, socket.error):
                #    _logger.info("Handshake with peer %s:%d failed" % addr)
        except socket.error as err:
            _logger.critical("Connection acceptor failed, with %s" % err)


class DownloadTask(object):
    def __init__(self, piece, man):
        #threading.Thread.__init__(self)
        #self.daemon = True

        self._manager = man
        self._piece = piece

        self._peers = utils.SynchronizedList()
        self._requests = utils.SynchronizedList()
        self._create_requests(self._requests, piece)

        self._last_contact = time.time()

    def __int__(self):
        return self._piece

    def __eq__(self, other):
        try:
            return self._piece == int(other)
        except TypeError:
            return False

    def __lt__(self, other):
        try:
            return self._piece < int(other)
        except TypeError:
            return False

    def _create_requests(self, requests, piece):
        offset = 0
        while offset < piece.length:
            length = BLOCK_LENGTH if offset + BLOCK_LENGTH <= piece.length\
                else piece.length - offset
            requests.append(\
                protocol.request_message(piece.index, offset, length))
            offset += BLOCK_LENGTH

    @property
    def index(self):
        return self._piece.index

    def done(self):
        return not bool(self._requests)

    # Called by the peer manager to check if the taks needs more
    # peers to help download the piece
    def stale(self):
        return not self.done() or not bool(self._peers) or \
            time.time() - self._last_contact > STALE

    def piece_received(self, piece, request):
        with self._requests:
            if not request in self._requests:
                _logger.debug(\
                    "Recevied a PIECE message that is already downloaded")
                return

            if piece.index != self._piece.index:
                raise ValueError("Wrong piece id %d expected was %d" % \
                                     (piece.index, self._piece))
            elif request.offset != piece.offset or\
                    request.length != len(piece.block):
                raise ValueError("Piece does not match request")

            self._piece.set_block(piece.offset, piece.block)
            self._requests.remove(request)
            self._last_contact = time.time()
            _logger.debug("Got PIECE message: %s" % piece)

            if self.done():
                self._manager.got_piece(self._piece)
                with self._peers:
                    del self._peers[:]

    def requests(self, num, have = []):
        with self._requests:
            if self.done():
                return []

            result = []
            for req in self._requests:
                if len(result) == num:
                    break

                if not req in have:
                    result.append(req)

            return result

        """
        with self._requests:
            if self.done():
                return []

            requests = self._requests[0:num]
            del self._requests[0:num]
            self._requests += requests
            return requests
        """

    def next_request(self, have = []):
        with self._requests:
            request = self.requests(1, have)
            if request:
                return request[0]
            else:
                return None

#    def next_request(self):
#        with self._requests:
#            if self.done():
#                return None

#            request = self._requests.pop(0)
#            self._requests.append(request)
#            return request

    def has_peer(self, peer):
        return bool(next((p for p in self._peers if p == peer), False))

    def remove_peer(self, peer):
        with self._peers:
            if self.has_peer(peer):
                self._peers.remove(peer)

    def add_peer(self, peer):
        with self._peers:
            self._peers.append(peer)


class PeerMonitor(threading.Thread):
    def __init__(self, man):
        super(PeerMonitor, self).__init__()
        self.daemon = True

        self._manager = man

        self._halt = False

        self._round = 0
        self._downloaders = []
        self._unchoken = []
        self._optimistic = 1

    # Called when a new peer has connected
    # Should favour this peer in the next optimistic unchoke
    def peer_arrived(self, peer):
        pass

    # Called when a peer becomes interested in us
    def interested(self, peer):
        if self._manager.completed():
            return

        with self._manager.peers:
            # Got interested from a already interested peer. Ignore.
            if peer in self._downloaders:
                return

            if peer in self._unchoken:
                p = min(\
                    self._downloaders, key = lambda p: p.upload_speed())
                if peer.upload_speed() > p.upload_speed():
                    p.choke(True)
                    self._downloaders.remove(p)
                    self._downloaders.append(peer)

    # Called when the client thinks it's being snubbed
    # Should increase number of optimistic unchokes
    def snubbed(self):
        self._optimistic += 1

    def run(self):
        while not self._halt:
            self._unchoke_peers()
            time.sleep(UNCHOKE_INTERVAL)

    # Called every ten seconds. Unchokes four peers based on how much
    # they uploaded to us (if we are actively downloading, else
    # uses the download rate). Every 30 seconds randomly unchoke a peer
    # (optimistic unchoke), favour the newly arriaved peer.
    # Only unchoke interested peers. If a peer with better upload rate
    # becomes interested, choke the worst uploader.
    def _unchoke_peers(self):
        with self._manager.peers:
            del self._unchoken[:]
            del self._downloaders[:]

            which = lambda p: p.upload_speed() if not \
                self._manager.completed() else lambda p: p.download_speed()

            peers = sorted(\
                self._manager.peers, key = which)

            if self._round % 3 == 0:
                for i in range(self._optimistic):
                    if peers:
                        peer = random.choice(peers)
                        if peer.interested:
                            self._downloaders.append(peer)
                            
                        if peer.choking:
                            peer.choke(False)

                        self._unchoken.append(peer)
                        peers.remove(peer)
                    else:
                        return

            for peer in peers:
                if len(self._downloaders) < MAX_DOWNLOADERS:
                    if peer.interested:
                        self._downloaders.append(peer)

                    if peer.choking:
                        peer.choke(False)

                    self._unchoken.append(peer)
                elif not peer.choking:
                    peer.choke(True)

            if self._round % 2 == 0:
                for peer in self._manager.peers:
                    peer.mark()

            self._round += 1


class PeerManager(object):
    RAREST_PIECES = 5

    def __init__(self, peer_id, acceptor, torrent, storage, tracker_client = None):
        self._peer_id = peer_id
        self._torrent = torrent
        self._tracker_client = tracker_client
        self._storage = storage
        self._acceptor = acceptor

        #self._acceptor = ConnectionAcceptor(port, self)
        self._peers = utils.SynchronizedList()
        self._tasks = []
        self._wanted_pieces = utils.SynchronizedList()

        self._piece_count = bitfield.Vector.create(\
            torrent.number_of_pieces)

        self._halt = False
        self._state = 'initialized'

        for piece in range(torrent.number_of_pieces):
            if not storage.has(piece):
                self._wanted_pieces.append(piece)

        if self.completed():
            _logger.info("File already completed")
            self._state = 'seeding'

        acceptor.add_manager(self)
        self._worker = utils.TimerTask()
        self._worker.start()

        self._monitor = PeerMonitor(self)
        self._monitor.start()

        #self._contact_tracker()

    def set_tracker(self, tracker):
        self._tracker_client = tracker

    @property
    def peers(self):
        return self._peers

    @property
    def peer_id(self):
        return self._peer_id

    @property
    def torrent(self):
        return self._torrent

    @property
    def tracker(self):
        return self._tracker_client

    @property
    def storage(self):
        return self._storage

    @property
    def state(self):
        return self._state

    def number_of_peers(self):
        with self._peers:
            return len(self._peers)

    def completed(self):
        with self._wanted_pieces:
            return not bool(self._wanted_pieces)

    def start(self):
        self._contact_tracker()

    def halt(self):
        # Before total shutdown, call tracker with stopped event
        if self._halt:
            return

        self._halt = True
        self._state = 'finished' if self.completed() else 'stopped'
        self._tracker_client.stopped()

        self._worker.halt()

        try:
            self._storage.halt()
        except IOError:
            pass

        for peer in self._peers:
            try:
                peer.halt()
            except socket.error:
                pass

        del self._peers[:]

    def need_more(self):
        return len(self._peers) < MAX_PEERS

    def add_peer(self, peer):
        with self._peers:
            if not peer in self._peers and self.need_more():
                self._peers.append(peer)
                peer.bitfield(self._storage.bitfield)

    def remove_peer(self, peer):
        with self._peers:
            if peer in self._peers:
                self._peers.remove(peer)
                # Synchronize _piece_count?
                if peer.ready():
                    self._piece_count -= peer.haves.to_vector()

                if len(self._peers) < MAX_PEERS - DELTA_PEERS:
                    self._contact_tracker()

    # Called when a critical error ocurres - UNUSED
    def crititacl_error(self, err):
        pass

    # Called when a REQUEST message has been received from a peer
    # that we currently not are choking
    def request_received(self, piece):
        #if not self._storage.has(piece):
        #    raise ValueError("Requested piece not in storage")

        try:
            return self._storage.piece(piece)
        except IOError as err:
            _logger.critical("Piece (%d) retrieval failed, with %s" %\
                                 (piece, err))

        return None

    # Called when a HAVE message has been received from a peer
    # Return true if we are interested
    def have_received(self, piece):
        with self._wanted_pieces:
            self._piece_count.update(piece, 1)
            return piece in self._wanted_pieces or piece in self._tasks

    # Called when a BITFIELD messasge has been received from a peer
    # Return true if we are interested
    def bitfield_received(self, bitfield):
        with self._wanted_pieces:
            self._piece_count += bitfield.to_vector()
            
            for piece in self._wanted_pieces:
                if bitfield.get(piece):
                    return True

            for task in self._tasks:
                if piece == task.index:
                    return True

            return False

    def interested_received(self, peer):
        self._monitor.interested(peer)

    def gave_block(self, index, offset, length):
        self._tracker_client.update_uploaded(length)

    # Called when the peer is ready to start download of a new piece
    def next_piece(self, peer, bitfield):
        with self._wanted_pieces:
            if self.completed() or self._halt:
                return None

            for task in self._tasks:
                if task.stale() and bitfield.get(task.index):
                    task.add_peer(peer)
                    return task

            if len(self._tasks) > MAX_TASKS:
                return None

            next = self._select_piece(bitfield)
            #task = DownloadTask(self._storage.piece(next), self)
            task = DownloadTask(self._storage.empty_piece(next), self)#\
                #storage.Piece.create_empty_piece(\
                #    next, self._torrent.piece_size(next)), self)
            self._wanted_pieces.remove(next)
            self._tasks.append(task)
            task.add_peer(peer)

            return task
            # Check if the existing tasks need more peers - DONE
            # Start a task with the peer and return task - DONE

    def tracker_responded(self, resp):
        for addr in resp.peers_enum():
            if not self.need_more():
                return

            sock = None
            try:
                if not addr in self._peers:
                    #sock = socket.socket()
                    #sock.connect(addr)
                    peer.initiate_handshake(addr, self)
            except socket.error as err:
                _logger.info("Could not open connection to %s, with %s" % (addr, err))
                if sock:
                    sock.close()

        if len(self._peers) < MAX_PEERS - DELTA_PEERS:
            self._contact_tracker()

    def got_piece(self, piece):
        self._worker.now(self._got_piece, piece)

    # Called when a piece has been finished downloading
    def _got_piece(self, piece):
        with self._wanted_pieces:
            if self.completed() or self._halt:
                return

            self._tracker_client.update_downloaded(piece.length)
            try:
                index = piece.index
                task = next((t for t in self._tasks if t.index == index), None)
                #if not index in self._wanted_pieces:
                if task is None:
                    _logger.info(\
                        "Got a piece %d we are not interested in" % index)
                else:
                    if self._storage.write_piece(piece):
                        #self._wanted_pieces.remove(index)
                        self._tasks.remove(task)
                        self._tracker_client.update_left(piece.length)
                        self._send_have(index)
                        self._complete()
                        _logger.info("Valid piece %d downloaded" % index)
                    else:
                        _logger.info("Got bad piece %d" % index)
            except IOError as err:
                _logger.critical(\
                    "Writing to storage failed, with %s" % err)
                # What now? Try to open a new storage? Ignore?

    #def _tracker_task(self):
    #    self._worker.now(self._contact_tracker)

    def _contact_tracker(self):
        if not self.need_more():
            return

        self._tracker_client.request()

    def _select_piece(self, bitfield):
        wanted = [p for p in self._wanted_pieces if bitfield[p]]
        sorted(wanted, key = lambda p: self._piece_count[p])
        
        #top = PeerManager.RAREST_PIECES
        #if len(wanted) < top:
        #    top = len(wanted)

        last = -1
        different = 0
        top = 0
        for piece in wanted:
            if different > PeerManager.RAREST_PIECES:
                break

            top += 1
            piece = self._piece_count[piece]

            if last != piece:
                last = piece
                different += 1

        return wanted[random.randrange(0, top)]

    def _send_have(self, index):
        with self._peers:
            for peer in self._peers:
                peer.have(index)

    def _complete(self):
        if self.completed():
            _logger.info("Completed download of file")
            self._state = 'seeding'
            self._tracker_client.completed()


if __name__ == '__main__':
    import torrent
    import socket
    import time
    import bitfield
    import random
    import peer
    import storage

    # Setup logging.
    logger = logging.getLogger('bittorrent')
    logger.setLevel(logging.INFO)
    sthl = logging.StreamHandler()
    formatter = logging.Formatter(\
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sthl.setFormatter(formatter)
    logger.addHandler(sthl)

    t = torrent.Torrent('trusted-computing.torrent')
    addr = ('localhost', 3000)
    peer_id = b'a1b2c3d4e5f6g7h8i9j0'
    sock = socket.socket()
    #sock.settimeout(10)
    sock.connect(addr)

    class StorageMock(object):
        def __init__(self, t):
            self._torrent = t

        def has(self, piece):
            return False

        def completed(self):
            return False

        def piece(self, index):
            return storage.Piece.create_empty_piece(\
                index, 256000, self._torrent.piece_hash(index))

        def write_piece(self, piece):
            print("Writting piece ", piece)

    manager = PeerManager(peer_id, t, None, None, StorageMock(t))
    peer = peer.handshake(sock, addr, peer_id, t, manager)

    field = bitfield.Bitfield(t.number_of_pieces)
    #for i in range(len(field)):
    #    if random.random() < 0.5:
    #        field.set(i)
    field.set(8)

    peer.bitfield(field)
    peer.choke(True)
    peer.choke(False)
    peer.have(9)
    time.sleep(5)
    peer.close()
