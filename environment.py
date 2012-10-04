import manager
import peer
import tracker_client
import storage as disk
import torrent as metainfo
import protocol
import bitfield
import tracker_client
import utils

import socket
import struct
import logging
import threading

peer_manager = None
trackers = None
tracker = None
log = None

def initialize(torrent_path, peer_id, store, path):
    global log
    log = PPList()

    # Setup logging
    logger = logging.getLogger('bittorrent')
    logger.setLevel(logging.INFO)
    sthl = MemoryHandler()
    formatter = logging.Formatter(\
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sthl.setFormatter(formatter)
    logger.addHandler(sthl)

    global peer_manager, trackers, tracker, pieces
    
    trackers = tracker_list()
    torrent = metainfo.Torrent(torrent_path)
    
    storage = None#MemoryStorage(torrent)
    if store:
        storage = disk.Storage(torrent, path)
    else:
        storage = MemoryStorage(torrent)

    peer_manager = PeerManagerConsole(torrent, peer_id, storage)

    port = 6881
    left = torrent.length

    # Initialize trackers
    announce_list = torrent.announce_list
    if not announce_list is None:
        for tier in announce_list:
            trackers += [tracker_client.TrackerClient(\
                 a, torrent.info_hash, peer_id, port, left) for a in tier]
    else:
        trackers += [tracker_client.TrackerClient(torrent.announce, \
                          torrent.info_hash, peer_id, port, left)]

    tracker = trackers[0]

    return {
        'contact': contact,
        'tail': tail,
        'available': avail,
        'table':table,
        'localhost': 'localhost',
        'peer_id': peer_id,
        #'peer_manager': peer_manager,
        'peers': peer_manager._peers,
        #'storage': storage,
        #'pieces': storage._pieces,
        'haves': storage._haves,
        'have': storage.has,
        'size': storage.size,
        'missing': storage.missing,
        'piece': storage.piece,
        'torrent': peer_manager.torrent,
        'trackers': trackers,
        'tracker': tracker,
        'log': log
    }

def shutdown():
    peer_manager.halt()

def avail():
    print("Available objects and functions. help can be used to get more detailed informations about a object. NOTE the available lists have some extra attributes (e.g. peers.first returns the first peer or None).\n")

    print("objects:")
    print("\ttrackers \tlist of all available trackers")
    print("\ttracker  \tshortcut for the first tracker in trackers")
    print("\tpeers    \tlist of all connected peers")
    print("\thaves    \tbitfield over local pieces")
    print("\tlog      \tlist of all log messages")
    print("\tpeer_id  \tlocal peer id")
    print("\ttorrent  \trepresenting the .torrent file")

    print("\nfunctions:")
    print("\tcontact(ip, port) \tconnect to a peer and exchange handshake")
    print("\t                  \tadds the peer to peers and returns peer")
    print("\tpiece(index)      \tget the piece given by index")
    print("\thave(index)       \treturns true if the piece given by index")
    print("\t                  \tis present")
    print("\tsize()            \tsize of the file present in bytes")
    print("\tmissing()         \tbytes missing of file")
    print("\ttail(li, lines = 10, follow = False, before = None)")
    print("\t                  \ttail one of the given lists (e.g. peers)")
    print("\ttable(li)         \tprint list in table form")
    print("\tavailable()       \toutputs this text")

# Override peer default behaviour.
def message_received(self, length, msg):
    try:
        message = None

        if length == 0:
            message = protocol.parse_keep_alive(msg)
            self._messages.append(message)
            return
        
        id = msg[0]
        
        if not self.ready() and id != protocol.BITFIELD:
            self._haves = bitfield.Bitfield(self._pieces)
        elif self.ready() and id == protocol.BITFIELD:
            raise ValueError(\
                "Already received BITFIELD from peer %s" % self)

        if id == protocol.CHOKE:
            message = protocol.parse_choke(msg)
            self._choked = True
        elif id == protocol.UNCHOKE:
            message = protocol.parse_unchoke(msg)
            self._choked = False
        elif id == protocol.INTERESTED:
            message = protocol.parse_interested(msg)
            self._interested = True
        elif id == protocol.NOT_INTERESTED:
            message = protocol.parse_not_interested(msg)
            self._interested = False
        elif id == protocol.HAVE:
            message = protocol.parse_have(msg)
            self._haves.set(message.piece)
        elif id == protocol.BITFIELD:
            message = protocol.parse_bitfield(msg, self._pieces)
            self._haves = message.bitfield
        elif id == protocol.REQUEST:
            message = protocol.parse_request(msg)
            with self._requests:
                self._requests.append(message)
        elif id == protocol.PIECE:
            message = protocol.parse_piece(msg)
        elif id == protocol.CANCEL:
            message = protocol.parse_cancel(msg)
        elif id == protocol.PORT:
            # Not supported. Ignore.
            pass
        else:
            raise ValueError(\
                "Message with unknown id %d received" % id)

        self._messages.append(message)
    except(ValueError, TypeError, IndexError, struct.error) as err:
        pass
        # Invalid message recevied from peer. Close connection?
        #_logger.info(\
        #    "Invalid message recevied from peer %s: %s" % (self, err))

peer.Peer.messages = property(lambda self: self._messages)
peer.Peer.message_received = message_received

def satisfy_requests(self):
    with self._requests:
        if not self._interested:
            return

        while self._requests:
            request = self._requests.pop()
            piece = self._manager.request_received(request.index)
            self.piece(request.index, request.offset, \
                           piece.block(request.offset, request.length))

peer.Peer.satisfy = satisfy_requests

# Storage interface
class MemoryStorage(object):
    def __init__(self, torrent):
        self._torrent = torrent
        self._haves = bitfield.Bitfield(torrent.number_of_pieces)
        self._pieces = piece_list()

    @property
    def bitfield(self):
        return self._haves

    def halt(self):
        pass

    def has(self, index):
        return self._haves[index]

    def completed(self):
        return self._haves.all_set()

    def size(self):
        result = 0
        for piece in range(self._torrent.number_of_pieces):
            result += self._haves[piece] * self._torrent.piece_size(piece)
            
        return result

    def missing(self):
        return self._torrent.length - self.size()

    def write_piece(self, piece):
        if not piece.valid():
            return False

        if piece in self._pieces:
            self._pieces.remove(piece)

        self._pieces.append(piece)
        self._haves.set(piece.index, True)
        return True

    def piece(self, index):
        if not self._haves.get(index):
            raise IndexError("No piece with the index %d" % index)

        return next([p for p in self._piece if p.index == index])

# Implementing the PeerManager interface.
class PeerManagerConsole(object):
    def __init__(self, meta, peer_id, storage):
        self._torrent = meta
        self._peer_id = peer_id
        #self._peers = PeerList()
        self._peers = peer_list()
        self._storage = storage

    @property
    def torrent(self):
        return self._torrent

    @property
    def peer_id(self):
        return self._peer_id

    def request_received(self, piece):
        try:
            return self._storage.piece(piece)
        except IOError:
            pass

    def halt(self):
        for peer in self._peers:
            try:
                peer.halt()
            except socket.error:
                pass

        try:
            self._storage.halt()
        except IOError:
            pass

    def add_peer(self, peer):
        if not peer in self._peers:
            self._peers.append(peer)

    def remove_peer(self, peer):
        if peer in self._peers:
            self._peers.remove(peer)

    def gave_block(self, index, offset, length):
        pass

# Macro functions.
def contact(ip, port):
    addr = (ip, port)
    sock = None

    try:
        sock = socket.socket()
        sock.connect(addr)

        torrent = peer_manager.torrent
        peer.send_handshake(sock, peer_manager.peer_id, torrent.info_hash)
        hs = peer.receive_handshake(sock, addr)

        if hs.info_hash != torrent.info_hash:
            raise ValueError("info_hash mismatch, peer %s" % addr)

        p = peer.Peer(hs.peer_id, sock, addr, \
                        torrent.number_of_pieces, peer_manager)
        #p._messages = MessageList()

        p._requests = utils.SynchronizedList()
        p._messages = message_list()
        peer_manager.add_peer(p)

        return p
    except (socket.error, ValueError) as err:
        print("Connection to %s failed with %s" % (addr, err))
        if sock:
            sock.close()

    return None

def upload(p, bitfield = peer_manager._storage.bitfield):
    if not isinstance(p, peer.Peer):
        p = contact(*p)

    if bitfield:
        p.bitfield(bitfield)

    p.choke(False)

    tail(p.messages, follow = True)

def tail(li, lines = 10, follow = False, before = None):
    if before:
        before()

    for line in li[-lines:]:
        print(line)

    if follow:
        li.follow = True
        input()
        li.follow = False

def table(li):
    print(li._pp)

# Utils
class MemoryHandler(logging.Handler):
    def emit(self, record):
        log.append(record)

class _Identity(object):
    def __getattr__(self, name):
        return name

class ListPrettyPrinter(object):
    PADDING = 2
    IDENTITY = _Identity()
    LENGTH = 75

    def __init__(self, li, title, *attrs, **opts):
        self._list = li
        self._attrs = attrs
        self._headers = opts.get('header', {})
        self._map = opts.get('attr_map', {})
        self._title = title

    def output(self):
        print(str(self))

    def __str__(self):
        headers = [self._headers.get(a, a) for a in self._attrs]

        row_lengths = [len(header) for header in headers]
        for column in self._list:
            for i, attr in enumerate(self._attrs):
                value = getattr(column, attr)
                value = len(str(self._map.get(attr, value)))

                if value > row_lengths[i]:
                    row_lengths[i] = value

        row_lengths = [l + ListPrettyPrinter.PADDING for l in row_lengths]
        total = sum(row_lengths) + len(row_lengths) - 1

        total_length = ListPrettyPrinter.LENGTH
        if total < total_length:
            each = (total_length - total) // len(row_lengths)
            rest = total_length - total - each * len(row_lengths)

            def add():
                nonlocal rest
                if rest:
                    rest -= 1
                    return 1
                else:
                    return 0

            row_lengths = [l + each + add() for l in row_lengths]

        result = self._line(row_lengths, False)
        result += self._row([sum(row_lengths)], \
                               ListPrettyPrinter.IDENTITY, [self._title])
        result += self._line(row_lengths, False)
        result += self._row(row_lengths, ListPrettyPrinter.IDENTITY, \
                                headers)
        result += self._line(row_lengths)
        
        for item in self._list:
            result += self._row(row_lengths, item, self._attrs)

        return ''.join(result)

    def _line(self, lengths, delimiter = True):
        result = []
        for length in lengths:
            result += ['-'] * length
            if delimiter:
                result.append('|')
            else:
                result.append('-')

        result.pop()
        result.append('\n')

        return result

    def _empty(self, row_lengths):
        result = []
        for length in row_lengths:
            result += [' '] * length
            result.append('|')

        result.pop()
        result.append('\n')

        return result

    def _row(self, lengths, item, attrs):
        result = []
        for i, attr in enumerate(attrs):
            value = getattr(item, attr)
            value = str(self._map.get(attr, value))

            left_padding = (lengths[i] - len(value)) // 2
            right_padding = lengths[i] - len(value) - left_padding
            result += [' '] * left_padding + [value] + \
                [' '] * right_padding
            result.append('|')

        result.pop()
        result.append('\n')

        return result

class PPList(list):
    def __init__(self, *args, **kwargs):
        super(PPList, self).__init__(*args, **kwargs)
        self._pp = None
        self.follow = False

    @property
    def first(self):
        return self[0] if self else None

    @property
    def last(self):
        return self[-1] if self else None

    def append(self, *args, **kwargs):
        super(PPList, self).append(*args, **kwargs)
        if self.follow:
            print(*args, **kwargs)

def tracker_list(*args, **kwargs):
    pplist = PPList(*args, **kwargs)
    pplist._pp = ListPrettyPrinter(pplist, 'Trackers',\
          'announce', 'active', 'event', 'downloaded', 'uploaded')
    return pplist

def peer_list(*args, **kwargs):
    pplist = PPList(*args, **kwargs)
    pplist._pp = ListPrettyPrinter(pplist, 'Peers', \
                    'id', 'ip', 'port', 'downloaded', 'uploaded')
    return pplist

def piece_list(*args, **kwargs):
    pplist = PPList(*args, **kwargs)
    pplist._pp = ListPrettyPrinter(pplist, 'Pieces',\
          'index', 'length', 'valid', map = {'valid': lambda v: v()})
    return pplist

def message_list(*args, **kwargs):
    pplist = PPList(*args, **kwargs)
    pplist._pp = ListPrettyPrinter(pplist, 'Messages',\
                   'id', 'name', 'len', header = {'len': 'length'})
    return pplist

if __name__ == '__main__':
    class T(object):
        def __init__(self, id, ip, port, down, up):
            self.id = id
            self.ip = ip
            self.port = port
            self.downloaded = down
            self.uploaded = up

    ts = []
    for i in range(10):
        ts.append(T(i, '127.1.1.' + str(i), 1023 * i, 1024 * i, 128 * i))

    pp = ListPrettyPrinter(\
        ts, 'Tests', 'id', 'ip', 'port', 'downloaded', 'uploaded', \
            id = 'i', downloaded = 'down')
    pp.output()
