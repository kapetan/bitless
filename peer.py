import struct
import socket
import threading
import logging
import time

import protocol
import bitfield

HANDSHAKE_TIMEOUT = 60
KEEP_ALIVE_TIMEOUT = 120 #seconds
RECEIVE_TIMEOUT = KEEP_ALIVE_TIMEOUT + 60

OUTSTANDING_REQUESTS = 10

_logger = logging.getLogger('bittorrent.peer')

def accept_handshake(sock, addr, managers):
    def run():
        try:
            hs = receive_handshake(sock, addr)
            for manager in managers:
                torrent = manager.torrent
                if torrent.info_hash == hs.info_hash:
                    if not manager.need_more():
                        break

                    peer = Peer(hs.peer_id, sock, addr,\
                                torrent.number_of_pieces, manager)
                    send_handshake(sock, manager.peer_id, torrent.info_hash)
                    manager.add_peer(peer)
                    return
        except (ValueError, socket.error, socket.timeout, struct.error) as err:
            _logger.info("Handshake failed with peer %s, because %s" % \
                             (addr, err))

        sock.close()

    hs = threading.Thread(target = run)
    hs.daemon = True
    hs.start()

def initiate_handshake(addr, manager):
    def run():
        try:
            sock = socket.socket()
            sock.connect(addr)

            torrent = manager.torrent
            send_handshake(sock, manager.peer_id, torrent.info_hash)
            hs = receive_handshake(sock, addr)
            
            if hs.info_hash != torrent.info_hash:
                sock.close()
                return
        
            peer = Peer(hs.peer_id, sock, addr, \
                            torrent.number_of_pieces, manager)
            manager.add_peer(peer)
        except (ValueError, socket.error, socket.timeout, struct.error) as err:
            _logger.info("Handshake failed with peer %s, bacause %s" % \
                             (addr, err))
            sock.close()

    hs = threading.Thread(target = run)
    hs.daemon = True
    hs.start()

def send_handshake(sock, peer_id, info_hash):
    hs = protocol.handshake_message(info_hash, peer_id)
    sock.settimeout(HANDSHAKE_TIMEOUT)
    sock.send(hs.payload())

def receive_handshake(sock, addr):
    sock.settimeout(HANDSHAKE_TIMEOUT)
    pstrlen = sock.recv(1)
    pstrlen = protocol.parse_pstrlen(pstrlen)
    if pstrlen != len(protocol.PSTR):
        raise ValueError("Unexpected pstr length " + str(pstrlen))

    hs = sock.recv(protocol.HANDSHAKE_LENGTH + pstrlen)
    hs = protocol.parse_handshake(pstrlen, hs)

    if hs.pstr != protocol.PSTR:
        raise ValueError("Unexpected pstr " + hs.pstr.decode('ASCII'))
    #elif hs.info_hash != torrent.info_hash:
    #    raise ValueError("Wrong info hash")

    #return Peer(hs.peer_id, sock, addr, torrent.number_of_pieces, manager)
    return hs


class MessageIn(threading.Thread):
    def __init__(self, peer, _in):
        threading.Thread.__init__(self)
        self.daemon = True

        self._peer = peer
        self._in = _in
        _in.settimeout(RECEIVE_TIMEOUT)
        self._halt = False

    def halt(self):
        self._halt = True

    def run(self):
        try:
            while not self._halt:
                length = self._in.recv(4)
                length = protocol.parse_length(length)
 
                need = length
                msg = b''
                while need > 0:
                    read = self._in.recv(need)
                    need -= len(read)
                    msg += read

                _logger.debug("Message recevied of length %d from peer %s"\
                                 % (length, self._peer))
                self._peer.message_received(length, msg)
        except (socket.error, socket.timeout, struct.error):
            _logger.info("Peer %s disconnected" % self._peer)
            self._peer.disconnected()


class MessageOut(threading.Thread):
    def __init__(self, peer, out):
        threading.Thread.__init__(self)
        self.daemon = True

        self._peer = peer
        self._out = out

        self._messages = []
        self._ready = threading.Condition()
        self._halt = False

    def cancel_messages(self, id, cond = lambda msg: True):
        with self._ready:
            self._messages[:] = [m for m in self._messages \
                                     if not (m.id == id and cond(m))]

    def cancel_piece(self, index, offset, length):
        self.cancel_messages(protocol.PIECE, \
            lambda msg: msg.index == index and msg.offset == offset and\
                len(msg.block) == length)

    def cancel_request(self, index, offset, length):
        with self._ready:
            self.cancel_messages(protocol.REQUEST, \
               lambda msg: msg.index == index and msg.offset == offset and\
                   msg.length == length)

            self.add_message(protocol.cancel_message(\
                    index, offset, length))

    def halt(self):
        self._halt = True
        with self._ready:
            self._ready.notify()

    def add_message(self, msg):
        with self._ready:
            self._messages.append(msg)
            self._ready.notify()

    def run(self):
        try:
            while not self._halt:
                self._ready.acquire()
                if self._messages:
                    m = self._messages.pop(0)
                    self._ready.release()

                    if not (m.id == protocol.PIECE and self._peer.choking):
                        _logger.debug("Sending message %s to peer %s" %\
                                     (m, self._peer))
                        self._out.send(m.payload())

                        if m.id == protocol.PIECE:
                            self._peer.sent(\
                                m.index, m.offset, len(m.block))
                else:
                    self._ready.wait(KEEP_ALIVE_TIMEOUT)
                    if not self._messages:
                        self._messages.append(\
                            protocol.keep_alive_message())
                    self._ready.release()
        except socket.error:
            #Connection closed. Notify peer!
            self._peer.disconnected()
            _logger.info("Peer %s disconnected" % self._peer)


class Peer(object):
    def __init__(self, peer_id, sock, addr, pieces, manager):
        self._pieces = pieces
        self._manager = manager
        self._id = peer_id
        self._hex_id = ''.join(['%02x' % b for b in peer_id])

        self._socket = sock
        self._ip, self._port = addr

        self._haves = None
        # How much the peer has uploaded to us
        self._uploaded = 0
        # How much the peer has downloaded from us
        self._downloaded = 0

        self._tasks = []
        self._outstanding_requests = []
        self.mark()

        # The peer is interested in us
        self._interested = False
        # We are interested in the peer
        self._interesting = False
        # The peer is choking us
        self._choked = True
        # We are choking the peer
        self._choking = True

        self._out = MessageOut(self, sock)
        self._in = MessageIn(self, sock)
        self._out.start()
        self._in.start()

    def _update_downloaded(self, down):
        self._downloaded += down
        self._donwload_rate += down

    def _update_uploaded(self, up):
        self._uploaded += up
        self._upload_rate += up

    def __eq__(self, other):
        if isinstance(other, Peer):
            return self._ip ==  other._ip and self._port == other._port
        else:
            try:
                ip, port = iter(other)
                return self._ip == ip and self._port == port
            except TypeError:
                return False

    def __repr__(self):
        return '<Peer %s>' % str(self)

    def __str__(self):
        return '%s@%s:%d' % (self._hex_id, self._ip, self._port)

    @property
    def id(self):
        return self._id

    @property
    def ip(self):
        return self._ip

    @property
    def port(self):
        return self._port

    @property
    def haves(self):
        return self._haves

    @property
    def downloaded(self):
        return self._downloaded

    @property
    def uploaded(self):
        return self._uploaded

    @property
    def choking(self):
        return self._choking

    @property
    def interested(self):
        return self._interested

    def add_task(self, task):
        self._tasks.append(task)

    def mark(self):
        self._download_rate = 0
        self._upload_rate = 0
        # Seconds since epoch as float
        self._marked = time.time()

    def speed(self):
        dtime = time.time() - self._marked
        if dtime == 0:
            return 0, 0

        return self._download_rate / dtime, self._upload_rate / dtime

    def download_speed(self):
        down, up = self.speed()
        return down

    def upload_speed(self):
        down, up = self.speed()
        return up

    def ready(self):
        return not self._haves is None

    def has(self, piece):
        return self._haves[piece]

    def halt(self):
        self._socket.close()

    def keep_alive(self):
        self._out.add_message(protocol.keep_alive_message())

    def choke(self, do_choke):
        if self._choking == do_choke:
            return

        self._choking = do_choke

        msg = protocol.choke_message() if do_choke else \
            protocol.unchoke_message()
        self._out.add_message(msg)

    def interested(self, is_interesting):
        if self._interesting == is_interesting:
            return

        self._interesting = is_interesting

        msg = protocol.interested_message() if is_interesting else \
            protocol.not_interested_message()
        self._out.add_message(msg)

        #self._next_request()

    def have(self, piece):
        # Check if we are still interested in this peer
        self._out.add_message(protocol.have_message(piece))

    def bitfield(self, bitfield):
        self._out.add_message(protocol.bitfield_message(bitfield))

    def request(self, index, offset, length):
        self._out.add_message(\
            protocol.request_message(index, offset, length))

    def piece(self, index, offset, block):
        self._out.add_message(protocol.piece_message(\
                index, offset, block))

    def cancel(self, index, offset, length):
        self._out.add_message(protocol.cancel_message(\
                index, offset, length))

    def disconnected(self):
        # Tell coordinator the peer has disconnected
        self.halt()
        self._manager.remove_peer(self)

    def sent(self, index, offset, length):
        self._manager.gave_block(index, offset, length)

    def message_received(self, length, msg):
        try:
            if length == 0:
                protocol.parse_keep_alive(msg)
                return

            id = msg[0]

            if not self.ready() and id != protocol.BITFIELD:
                self._haves = bitfield.Bitfield(self._pieces)
            elif self.ready() and id == protocol.BITFIELD:
                raise ValueError(\
                    "Already received BITFIELD from peer %s" % self)

            if id == protocol.CHOKE:
                # If we are downloading, stop - DONE
                protocol.parse_choke(msg)
                self._choked = True
                del self._outstanding_requests[:]
            elif id == protocol.UNCHOKE:
                # If we are interested start downloading - DONE
                protocol.parse_unchoke(msg)
                self._choked = False
                self._request_piece()
            elif id == protocol.INTERESTED:
                protocol.parse_interested(msg)
                self._interested = True
                self._manager.interested_received(self)
            elif id == protocol.NOT_INTERESTED:
                protocol.parse_not_interested(msg)
                self._interested = False
            elif id == protocol.HAVE:
                # Check with coordinator if we are interested - DONE
                have = protocol.parse_have(msg)
                self._haves.set(have.piece)
                self.interested(self._manager.have_received(have.piece))
            elif id == protocol.BITFIELD:
                # Only receive bitfield once after handshake - DONE
                # Check with coordinator if we are interested - DONE
                field = protocol.parse_bitfield(msg, self._pieces)
                self._haves = field.bitfield
                self.interested(\
                    self._manager.bitfield_received(field.bitfield))
            elif id == protocol.REQUEST:
                req = protocol.parse_request(msg)
                if not self._choking and self._interested:
                    piece = self._manager.request_received(req.index)
                    if piece:
                        data = piece.block(req.offset, req.length)
                        self.piece(req.index, req.offset, data)
                # If we are choking this peer ignore - DONE
                # Else get piece from storage and send via out - DONE
            elif id == protocol.PIECE:
                piece = protocol.parse_piece(msg)
                #self.task.piece_received(piece, self._request)
                self._piece(piece)
                self._request_piece()
                # Tell coordinator we received a piece - DONE
            elif id == protocol.CANCEL:
                cancel = protocol.parse_cancel(msg)
                self._out.cancel_piece(cancel.index, \
                                           cancel.offset, cancel.length)
            elif id == protocol.PORT:
                # Not supported. Ignore.
                pass
            else:
                raise ValueError(\
                    "Message with unknown id %d received" % id)
        except(ValueError, TypeError, IndexError, struct.error) as err:
            # Invalid message recevied from peer. Close connection?
            _logger.info(\
                "Invalid message recevied from peer %s: %s" % (self, err))
            #raise
            self._request_piece()

    def _need(self):
        return OUTSTANDING_REQUESTS - len(self._outstanding_requests)

    def _send_requests(self, task, need):
        requests = task.requests(need, self._outstanding_requests)
                
        for req in requests:
            self._out.add_message(req)
            self._outstanding_requests.append(req)

    def _request_piece(self):
        if not self._interesting or self._choked:
            return

        self._tasks[:] = [t for t in self._tasks if not t.done()]

        need = self._need()
        if need > 0:
            for task in self._tasks:
                self._send_requests(task, need)

                #requests = task.requests(need, self._outstanding_requests)
                #need -= len(requests)
                
                #for req in requests:
                #    self._out.add_message(req)
                #    self._outstanding_requests.append(req)

                #if req:
                #    for req in requests:
                #        if not req in self._outstanding_requests:
                #            self._outstanding_requests.append(req)

                #    need = self._need()

                need = self._need()
                if need <= 0:
                    return

        task = self._manager.next_piece(self, self._haves)
        if not task is None and not task in self._tasks:
            self._tasks.append(task)
            self._send_requests(task, need)
                

        # Check if theres are enough outstanding requests
        # If not ask for more from a task
        # If no more ask manager for a new task
        # Send requests

        # When choke received clear _outstanding_requests

        # Call this when unchoke and piece message received
        # When piece received check if in outstanding requests
        # and then give to task

    def _piece(self, piece):
        for task in self._tasks:
            if task.index == piece.index:
                req = next((r for r in self._outstanding_requests \
                if r.index == piece.index and r.offset == piece.offset \
                                and r.length == len(piece.block)), None)

                if not req is None:
                    task.piece_received(piece, req)
                    self._outstanding_requests.remove(req)
                    return

        raise ValueError("Invalid PIECE message %s received" % piece)

    """
    def _requests(self, resend = False):
        if not self._interesting or self._choked:
            return

        if resend:
            for request in self._requests:
                self._out.add_message(request)

        need = self._need()
        
        for task in self._tasks:
            if not need:
                return

            requests = task.requests(need)
            if requests:
                self._requests += requests
                for request in requests:
                    self._out.add_message(request)
                need = self._need()

        while need:
            task = self._manager.next_piece(self, self._haves)
            if not task:
                return

            self._tasks.append(task)
    """      

    #def _next_request(self):
    #    if not self._interesting or self._choked:
    #        return None

    #    if self.task is None or self.task.done():
    #        self.task = self._manager.next_piece(self, self._haves)

    #    self._request =  \
    #        self.task.next_request(self) if self.task else None
    #    if self._request:
    #        self._out.add_message(self._request)
        
    #    return self._request


if __name__ == '__main__':
    import torrent
    import socket
    import time
    import bitfield
    import random

    t = torrent.Torrent('trusted-computing.torrent')
    addr = ('localhost', 3000)
    peer_id = b'a1b2c3d4e5f6g7h8i9j0'
    sock = socket.socket()
    sock.settimeout(10)
    sock.connect(addr)

    print("Pieces: ", t.number_of_pieces)
    peer = handshake(sock, addr, peer_id, t)
    peer.choke(True)
    peer.request(4, 1024, 16200)
    peer.interested(False)
    #peer.have(230)

    field = bitfield.Bitfield(t.number_of_pieces)
    #for i in range(len(field)):
    #    if random.random() < 0.5:
    #        field.set(i)
    field.set(8)
    
    peer.bitfield(field)
    peer.have(123)

    peer.cancel(6, 1024, 56332)
    peer.piece(101, 100, b'\x05'*100)

    class MM:
        id = 10

        def payload(self):
            print("What")
            return b'\x00\x00\x00\x01\x04'

    #peer._out.add_message(MM())

    time.sleep(2)
    peer.halt()
