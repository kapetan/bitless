import bencode.bdecoder as bdecoder
import bencode.bencoder as bencoder

import hashlib
import time
import os.path as path
import os
import copy

_PIECE_LENGTH = 524288 #bytes 8-10GB else 262144?

def hash_file_pieces(file_list, length):
    hashes = []
    piece = b''

    for f in range(len(file_list)):
        with open(file_list[f], 'rb') as fio:
            piece += fio.read(length - len(piece))
            while piece:
                if len(piece) < length:
                    break

                hash = hashlib.sha1(piece)
                hashes.append(hash.digest()) 
                piece = fio.read(length)

    if piece:
        hash = hashlib.sha1(piece)
        hashes.append(hash.digest())

    return b''.join(hashes)

def dir_to_torrent(dir_path, announce, announce_list = None,\
        piece_length = _PIECE_LENGTH, comment = None, is_private = False):
    if dir_path.endswith(os.sep):
        dir_path = dir_path[0:-1]

    torrent = {
        'creation date': round(time.time()),
        'announce': announce
    }

    if announce_list:
        torrent['announce-list'] = announce_list

    if comment:
        torrent['comment'] = comment

    dir_name = path.basename(dir_path)

    def create_paths(dirname = [dir_path]):
        paths = []
        file_list = os.listdir(path.join(*dirname))

        for name in file_list:
            full_path = copy.copy(dirname)
            full_path.append(name)
            ospath = path.join(*full_path)
        
            if path.isfile(ospath):
                paths.append(full_path[1:])
            else:
                files = create_paths(full_path)
                paths = paths + files

        return paths

    paths = create_paths()

    info = {
        'piece length': piece_length,
        'name': dir_name,
        'pieces': hash_file_pieces(\
            [path.join(dir_path, *p) for p in paths], piece_length)
    }

    if is_private:
        torrent['private'] = 1

    files = []
    for p in paths:
        files.append({
                'length': path.getsize(path.join(dir_path, *p)),
                'path': p
        })

    info['files'] = files
    torrent['info'] = info
    return bencoder.encode(torrent)

def file_to_torrent(file_path, announce, announce_list = None,\
        piece_length = _PIECE_LENGTH, comment = None, is_private = False):
    torrent = {
        'creation date': round(time.time()),
        'announce': announce
    }

    if announce_list:
        torrent['announce-list'] = announce_list

    if comment:
        torrent['comment'] = comment

    info = {
        'piece length': piece_length,
        'name': path.basename(file_path),
        'length': path.getsize(file_path)
    }

    if is_private:
        torrent['private'] = 1

    pieces = hash_file_pieces([file_path], piece_length)
    info['pieces'] = pieces
    torrent['info'] = info
    return bencoder.encode(torrent)

def to_torrent(ospath, announce, announce_list = None,\
        piece_length = _PIECE_LENGTH, comment = None, is_private = False):
    if path.isfile(ospath):
        return file_to_torrent(ospath, announce, announce_list,\
                                   piece_length, comment, is_private)
    else:
        return dir_to_torrent(ospath, announce, announce_list,\
                                   piece_length, comment, is_private)


class Torrent(object):
    @classmethod
    def from_file(cls, torrent_path):
        content = None
        with open(torrent_path, 'rb') as f:
            content = f.read()

        return cls(content)

    def __init__(self, content):
        self._load_torrent(content)

    def _load_torrent(self, content):
        #f = open(path, 'rb')
        #content = f.read()
        #f.close()

        parsed = bdecoder.decode(content)
        info_hash = hashlib.sha1(bdecoder.decode(content, 2)[b'info'])
        self._hex_info_hash = info_hash.hexdigest()
        self._info_hash = info_hash.digest()
        
        self._announce = parsed[b'announce'].decode('UTF-8')

        if b'announce-list' in parsed:
            announce_list = parsed[b'announce-list']
            self._announce_list = []
            for tire in announce_list:
                self._announce_list.append(\
                    [announce.decode('UTF-8') for announce in tire])
        else:
            self._announce_list = None

        info = parsed[b'info']
        self._piece_length = info[b'piece length']

        pieces = info[b'pieces']
        self._pieces = []
        
        current = 0
        length = len(pieces)
        while current < length:
            self._pieces.append(pieces[current:current + 20])
            current += 20

        self._name = info[b'name'].decode('UTF-8')
        
        if b'files' in info:
            self._files = info[b'files']
            self._mode = 'multiple'

            self._length = 0
            for f in self._files:
                self._length += f[b'length']
        else:
            self._length = info[b'length']
            self._mode = 'single'

        self._nb_of_pieces = self._length // self._piece_length
        if self._length % self._piece_length != 0:
            self._nb_of_pieces += 1

    @property
    def hex_info_hash(self):
        return self._hex_info_hash

    @property
    def info_hash(self):
        return self._info_hash
            
    @property
    def pieces(self):
        return self._pieces

    @property
    def announce(self):
        return self._announce

    @property
    def announce_list(self):
        return self._announce_list

    @property
    def piece_length(self):
        return self._piece_length

    @property
    def files(self):
        return self._files

    @property
    def length(self):
        return self._length

    @property
    def name(self):
        return self._name

    @property
    def is_single_file(self):
        return self._mode == 'single'

    @property
    def number_of_pieces(self):
        return self._nb_of_pieces

    @property
    def number_of_files(self):
        if self.is_single_file:
            return 1
        else:
            return len(self._files)

    def file_path(self, f):
        if self.is_single_file and f == 0:
            return self._name
        else:
            path = self._files[f][b'path']
            return [p.decode('UTF-8') for p in path]

    def file_size(self, f):
        if self.is_single_file and f == 0:
            return self._length
        else:
            return self._files[f][b'length']

    def piece_hash(self, piece):
        return self._pieces[piece]

    def piece_size(self, piece):
        if piece == self._nb_of_pieces - 1:
            return self.length - self.piece_length * piece
        elif 0 <= piece < self._nb_of_pieces:
            return self.piece_length
        else:
            raise IndexError("Piece " + str(piece) + " is not valid")

if __name__ == '__main__':
    import sys
    
    def usage():
        print("Generate content of .torrent file from given" +\
                  " directory or file")
        print("Usage: python torrent.py <path> <announce> " +\
                  "[--piece-length <length>] [--comment <comment>] [--out <file>]")
        print("  <path>        \t Path to file or directory")
        print("  <announce>    \t One or more tracker urls")
        print("                \t Multiple urls can be grouped into tires with quotes \"\"")
        print("                \t seperated by spaces")
        print("  --piece-length\t Piece length in bytes (default 524288)")
        print("  --comment     \t Comment to be included in the torrent")
        print("  --out         \t Output file for the torrent content")
        print("                \t (default stdin)")
        print()
        print("Example: python torrent.py move.avi http://opentracker:8080/announce")
        print("         python torrent.py music \"http://opentracker/announce http://piratetracker:7005/announce\" http://tracker/announce")

    options = {
        '--piece-length': 'piece_length',
        '--comment': 'comment',
        '--out': 'out'
    }

    arguments = {
        'ospath': sys.argv[1],
    }

    announce_list = []
    opt = -1

    for i, tire in enumerate(sys.argv[2:]):
        if options.get(tire, False):
            opt = i + 2
            break

        trackers = tire.split(' ')
        trackers = [t for t in trackers if t]
        if trackers:
            announce_list.append(trackers)

    if not announce_list:
        print(" - Needed at least one tracker")
        usage()
        sys.exit()

    arguments['announce'] = announce_list[0][0]
    if len(announce_list) == 1 and len(announce_list[0]) == 1:
        announce_list = []
    else:
        arguments['announce_list'] = announce_list
    
    out = None
    i = opt
    while 0 <= i < len(sys.argv):
        opt = sys.argv[i]
        if opt == '--piece-length':
            i += 1
            arguments['piece_length'] = int(sys.argv[i])
        elif opt == '--comment':
            i += 1
            arguments['comment'] = sys.argv[i]
        elif opt == '--out':
            i += 1
            out = sys.argv[i]
        else:
            print(" - Uknown option '" + opt + "'")
            usage()
            sys.exit()

        i += 1

    print("Arguments for program")
    for key,value in arguments.items():
        print(' -' + key + ': ' + str(value))

    if out:
        print(' -out: ' + out)

    content = to_torrent(**arguments)
    if out:
        print("Writing to '" + out + "'...")
        with open(out, 'wb') as f:
            f.write(content)
    else:
        print(content)
