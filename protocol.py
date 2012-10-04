import struct

import bitfield

# TODO Every message function creates its own instance of the payload
# method. 

HANDSHAKE = -2
KEEP_ALIVE = -1
CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6
PIECE = 7
CANCEL = 8
PORT = 9

MESSAGE_NAMES = [
    'handshake',
    'keep alive',
    'choke',
    'unchoke',
    'interested',
    'not interested',
    'have',
    'bitfield',
    'request',
    'piece',
    'cancel',
    'port'
]

# Handshake length without len(pstr) and the first byte 
# representing that value (pstrlen). Total length of handshake
# message: HANDSHAKE_LENGTH  + pstrlen + 1.
HANDSHAKE_LENGTH = 48
KEEP_ALIVE_LENGTH = 0
CHOKE_LENGTH = 1
UNCHOKE_LENGTH = 1
INTERESTED_LENGTH = 1
NOT_INTERESTED_LENGTH = 1
HAVE_LENGTH = 5
BITFIELD_LENGTH = 1
REQUEST_LENGTH = 13
PIECE_LENGTH = 9
CANCEL_LENGTH = 13

PSTR = b'BitTorrent protocol'
RESERVED = b'\x00' * 8

def parse_pstrlen(len):
    len, = struct.unpack('!B', len)
    return len

def parse_length(len):
    len, = struct.unpack('!I', len)
    return len

def message_id(name):
    name = name.lower()
    if name in MESSAGE_NAMES:
        return MAESSAGE_NAMES.index(name)

    return None

def message_name(id):
    if -2 <= id <= 9:
        return MESSAGE_NAMES[id + 2]

    return None

def _error(msg, expected, msg_type, op = lambda x,y: x == y):
    if not op(len(msg), expected):
        raise ValueError("Invalid message " + msg_type +\
                             ", length was " + str(len(msg)) +\
                             " expected " + str(expected))

def parse_handshake(pstrlen, handshake):
    _error(handshake, HANDSHAKE_LENGTH + pstrlen, 'handshake')

    pstr = handshake[0 : pstrlen]
    reserved = handshake[pstrlen : 8]
    info_hash = handshake[pstrlen + 8 : pstrlen + 28]
    peer_id = handshake[pstrlen + 28 : pstrlen + 48]

    return handshake_message(info_hash, peer_id, reserved, pstr)

def parse_keep_alive(msg):
    _error(msg, KEEP_ALIVE_LENGTH, \
                    'keep alive', lambda x,y: x == y or x is None)
    return keep_alive_message()

def parse_choke(msg):
    _error(msg, CHOKE_LENGTH, 'choke')
    return choke_message()

def parse_unchoke(msg):
    _error(msg, UNCHOKE_LENGTH, 'unchoke')
    return unchoke_message()

def parse_interested(msg):
    _error(msg, INTERESTED_LENGTH, 'interested')
    return interested_message()

def parse_not_interested(msg):
    _error(msg, NOT_INTERESTED_LENGTH, 'not interested')
    return not_interested_message()

def parse_have(msg):
    _error(msg, HAVE_LENGTH, 'have')
    piece, = struct.unpack('!I', msg[1:])
    return have_message(piece)

def parse_bitfield(msg, pieces):
    expected = pieces // 8 + (0 if pieces % 8 == 0 else 1)
    _error(msg, BITFIELD_LENGTH + expected, 'bitfield')
    field = bitfield.unpack(msg[1:], pieces)
    return bitfield_message(field)

def parse_request(msg):
    _error(msg, REQUEST_LENGTH, 'request')
    #struc = struct.Struct('!3I')
    index, offset, length = struct.unpack('!3I', msg[1:])
    return request_message(index, offset, length)

def parse_piece(msg):
    _error(msg, 9, 'piece', lambda x,y: x > y)
    index, offset = struct.unpack('!2I', msg[1:9])
    return piece_message(index, offset, msg[9:])

def parse_cancel(msg):
    _error(msg, CANCEL_LENGTH, 'cancel')
    #struc = struct.Struct('!I')
    index, offset, length = struct.unpack('!3I', msg[1:])
    return cancel_message(index, offset, length)


#def handshake_message(info_hash, peer_id, reserved = RESERVED, pstr = PSTR#):
#    m = Message(HANDSHAKE, HANDSHAKE_LENGTH + len(pstr))
#    m.pstr = pstr
#    m.reserved = reserved
#    m.info_hash = info_hash
#    m.peer_id = peer_id
    
#    def payload(self):
#        load = struct.pack('!B', len(pstr)) + self.pstr
#        load += self.reserved + self.info_hash + self.peer_id
#        return load
#    m._payload = payload

#    return m

#def _format_begin(id, len):
#    return struct.pack('!I', len) + struct.pack('!B', id)

#def simple_message(id):
#    m = Message(id, 1)
#    m._payload = lambda self: _format_begin(self.id, self.len)
#    return m

#def keep_alive_message():
#    m = Message(KEEP_ALIVE, 0)
#    m._payload = lambda self: struct.pack('!I', self.len)
#    return m

#def choke_message():
#    return simple_message(CHOKE)

#def unchoke_message():
#    return simple_message(UNCHOKE)

#def interested_message():
#    return simple_message(INTERESTED)

#def not_interested_message():
#    return simple_message(NOT_INTERESTED)

#def have_message(piece):
#    m = Message(HAVE, 5)
#    m.piece = piece
    
#    def payload(self):
#        begin = _format_begin(self.id, self.len)
#        return begin + struct.pack('!I', self.piece)
#    m._payload = payload

#    return m

#def bitfield_message(bitfield):
#    m = Message(BITFIELD, 1 + bitfield.bytesize)
#    m.bitfield = bitfield

#    def payload(self):
#        begin = _format_begin(self.id, self.len)
#        return begin + self.bitfield.pack()
#    m._payload = payload

#    return m

#def request_message(index, offset, length):
#    m = Message(REQUEST, 13)
#    m.index = index
#    m.offset = offset
#    m.length = length

#    def payload(self):
#        begin = _format_begin(self.id, self.len)
#        begin += struct.pack('!I', self.index) 
#        begin += struct.pack('!I', self.offset)
#        return begin + struct.pack('!I', self.length)
#    m._payload = payload

#    return m

#def piece_message(index, offset, block):
#    m = Message(PIECE, 9 + len(block))
#    m.index = index
#    m.offset = offset
#    m.block = block

#    def payload(self):
#        begin = _format_begin(self.id, self.len)
#        begin += struct.pack('!I', index)
#        begin += struct.pack('!I', offset)
#        return begin + self.block
#    m._payload = payload

#    return m

#def cancel_message(index, offset, length):
#    m = request_message(index, offset, length)
#    m._id = CANCEL
#    return m

class Message(object):
    prestruct = struct.Struct('!IB')

    def __init__(self, id, len):
        self._id = id
        self._len = len
        self._name = message_name(id)

    def __eq__(self, other):
        if isinstance(other, Message):
            return self._id == other.id

        return False

    def __len__(self):
        return self._len

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "<Message (%s) id=%d len=%d>" %\
            (self._name, self._id, self._len)

    @property
    def id(self):
        return self._id

    @property
    def len(self):
        return self._len

    @property
    def name(self):
        return self._name

    def payload(self):
        return Message.prestruct.pack(self._len, self._id)

class handshake_message(Message):
    def __init__(self, info_hash, peer_id,\
                     reserved = RESERVED, pstr = PSTR):
        Message.__init__(self, HANDSHAKE, HANDSHAKE_LENGTH + len(pstr))
        
        self._info_hash = info_hash
        self._peer_id = peer_id
        self._reserved = reserved
        self._pstr = pstr

    def __eq__(self, other):
        return super(handshake_message, self).__eq__(other) and\
            self._info_hash == other._info_hash and\
            self._peer_id == other._peer_id and\
            self._pstr == other._pstr

    @property
    def info_hash(self):
        return self._info_hash

    @property
    def peer_id(self):
        return self._peer_id

    @property
    def reserved(self):
        return self._reserved

    @property
    def pstr(self):
        return self._pstr

    def payload(self):
        load = struct.pack('!B', len(self._pstr)) + self._pstr
        load += self._reserved + self._info_hash + self._peer_id
        return load

class keep_alive_message(Message):
    def __init__(self):
        super(keep_alive_message, self).__init__(\
            KEEP_ALIVE, KEEP_ALIVE_LENGTH)

    def payload(self):
        return struct.pack('!I', self._len)

def choke_message():
    return Message(CHOKE, CHOKE_LENGTH)

def unchoke_message():
    return Message(UNCHOKE, UNCHOKE_LENGTH)

def interested_message():
    return Message(INTERESTED, INTERESTED_LENGTH)

def not_interested_message():
    return Message(NOT_INTERESTED, NOT_INTERESTED_LENGTH)

class have_message(Message):
    def __init__(self, piece):
        super(have_message, self).__init__(HAVE, HAVE_LENGTH)
        self._piece = piece

    def __eq__(self, other):
        return super(have_message, self).__eq__(other) and\
            self._piece == other._piece

    @property
    def piece(self):
        return self._piece

    def payload(self):
        pre = super(have_message, self).payload()
        return pre + struct.pack('!I', self._piece)

class bitfield_message(Message):
    def __init__(self, bitfield):
        super(bitfield_message, self).__init__(BITFIELD, \
                             BITFIELD_LENGTH + bitfield.bytesize)
        self._bitfield = bitfield

    def __eq__(self, other):
        return super(bitfield_message, self).__eq__(other) and\
            self._bitfield == other._bitfield

    @property
    def bitfield(self):
        return self._bitfield

    def payload(self):
        pre = super(bitfield_message, self).payload()
        return pre + self._bitfield.pack()

class request_message(Message):
    def __init__(self, index, offset, length):
        super(request_message, self).__init__(REQUEST, REQUEST_LENGTH)
        
        self._index = index
        self._offset = offset
        self._length = length

    def __eq__(self, other):
        return super(request_message, self).__eq__(other) and\
            self._index == other._index and\
            self._offset == other._offset and\
            self._length == other._length

    def __str__(self):
        return "<REQUEST Message len=%d index=%d offset=%d>" % \
            (self._len, self._index, self._offset)

    @property
    def index(self):
        return self._index

    @property
    def offset(self):
        return self._offset

    @property
    def length(self):
        return self._length

    def payload(self):
        pre = super(request_message, self).payload()
        return pre + struct.pack(\
            '!3I', self._index, self._offset, self._length)

class piece_message(Message):
    def __init__(self, index, offset, block):
        super(piece_message, self).__init__(\
            PIECE, PIECE_LENGTH + len(block))

        self._index = index
        self._offset = offset
        self._block = block

    def __str__(self):
        return "<PIECE Message len=%d index=%d offset=%d>" % \
            (self._len, self._index, self._offset)

    def __eq__(self, other):
        return super(request_message, self).__eq__(other) and\
            self._index == other._index and\
            self._offset == other._offset and\
            self._block == other._block

    @property
    def index(self):
        return self._index

    @property
    def offset(self):
        return self._offset

    @property
    def block(self):
        return self._block

    def payload(self):
        pre = super(piece_message, self).payload()
        return pre + struct.pack('!2I', self._index, self._offset) +\
            self._block

def cancel_message(index, offset, length):
    req = request_message(index, offset, length)
    req._id = CANCEL
    return req

if __name__ == '__main__':
    import bitfield

    m = Message(CHOKE, 1)
    print(m.id)

    m = have_message(123)
    print(m.len)
    print(m.piece)
    print(m.payload())
    n = have_message(122)
    print(m == n)

    field = bitfield.Bitfield(10)
    field.set(5)
    field.set(6)
    m = bitfield_message(field)
    print(m.payload())
