import hashlib
import os
import logging

import bitfield
import utils


_logger = logging.getLogger('bittorrent.storage')

DEFAULT_ROOT_DIR = 'downloads'

class Storage(object):
    def __init__(self, torrent, root_dir = DEFAULT_ROOT_DIR):
        self._torrent = torrent
        self._haves = bitfield.Bitfield(torrent.number_of_pieces)
        _logger.info("Creating/opening files")
        self._create_files(torrent, root_dir)

    def _create_files(self, torrent, root_dir):
        self._files = []
        
        if root_dir and not os.path.exists(root_dir):
            os.makedirs(root_dir)

        base = os.path.join(root_dir, torrent.name)
        if torrent.is_single_file:
            f = self._open_file(base)
            self._files.append(f)
        else:
            if not os.path.exists(base):
                os.makedirs(base)

            for i in range(torrent.number_of_files):
                path = torrent.file_path(i)
                dirs = path[0:-1]

                if dirs and not os.path.exists(os.path.join(base, *dirs)):
                    os.makedirs(dirs)

                f = self._open_file(os.path.join(base, *path))
                self._files.append(f)

        for i in range(torrent.number_of_pieces):
            piece = self._piece(i)
            self._haves.set(i, piece.valid())
        
        size = self.size()
        _logger.info("Has file %d/%d bytes" % \
                         (size, torrent.length))

    def _open_file(self, path):
        f = None
        try:
            f = open(path, 'r+b')
            _logger.info("Opening existing file %s" % path)
        except IOError:
            f = open(path, 'w+b')
            _logger.info("Creating file %s" % path)

        return f

    def _close_files(self):
        for f in self._files:
            try:
                f.close()
            except IOError:
                pass

    def _start(self, index):
        off = self._torrent.piece_length * index
        f = 0
        size = self._torrent.file_size(f)

        while off >= size:
            off -= size
            f += 1
            size = self._torrent.file_size(f)

        return f, off, size

    @property
    def bitfield(self):
        return self._haves

    def halt(self):
        self._close_files()

    def has(self, index):
        return self._haves.get(int(index))

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

        f, off, size = self._start(piece.index)
        written = 0
        
        block_index = 0
        while written < piece.length:
            need = piece.length - written
            length = need if off + need < size else size - off
            
            fio = self._files[f]
            fio.seek(off)
            fio.write(piece.block(block_index, length))
            fio.flush()

            written += length
            block_index += length
            if need - length > 0:
                f += 1
                off = 0
                size = self._torrent.file_size(f)

        self._haves.set(piece.index, True)
        return True

    def piece(self, index):        
        if not self._haves.get(index):
            raise IndexError("Don't have piece %d" % index)

        return self._piece(index)

    def empty_piece(self, index):
        return Piece.create_empty_piece(\
            index, self._torrent.piece_size(index), \
                self._torrent.piece_hash(index))

    def _piece(self, index):
        #if not self._haves.get(index):
        #    return Piece.create_empty_piece(\
        #        index, self._torrent.piece_size(index), \
        #            self._torrent.piece_hash(index))

        f, off, size = self._start(index)
        
        content = []
        read = 0
        piece_size = self._torrent.piece_size(index)

        while read < piece_size:
            need = piece_size - read
            length = need if off + need < size else size - off

            fio = self._files[f]
            fio.seek(off)
            content.append(fio.read(length))

            read += length
            if need - length > 0:
                f += 1
                size = self._torrent.file_size(f)
                off = 0

        piece = Piece(index, b''.join(content), \
                      self._torrent.piece_hash(index))

        return piece


@utils.synchronize('write_piece', 'piece')
class SynchronizedStorage(Storage, metaclass = utils.SynchronizedClass):
    pass


class Piece(object):
    @classmethod
    def create_empty_piece(cls, index, length, hash):
        return Piece(index, b'\x00' * length, hash)

    def __init__(self, index, data, hash):
        self._index = index
        self._length = len(data)
        self._data = data
        self._hash = hash

    @property
    def index(self):
        return self._index

    @property
    def length(self):
        return self._length

    @property
    def data(self):
        return self._data

    def __eq__(self, other):
        try:
            return self._index == int(other)
        except TypeError:
            return False

    def __int__(self):
        return self._index

    def __str__(self):
        return "Piece:[index=" + str(self._index) + \
            ", length=" + str(self._length) + "]"
  
    def block(self, index, length):
        if 0 <= index <= index + length <= self._length:
            return self._data[index:index + length]
        else:
            raise IndexError("Invalid index (" + str(index) + \
                                 ") and/or length (" + str(length) + ")")

    def set_block(self, index, data):
        length = len(data)
        if 0 <= index and index + length <= self._length:
            self._data = self._data[0:index] + data + \
                self._data[index + length:self._length]
        else:
            raise IndexError("Invalid index and/or data length")

    def valid(self):
        hashed = hashlib.sha1(self._data).digest()
        return hashed == self._hash

if __name__ == '__main__':
    import torrent
    
    torrent = torrent.Torrent("trusted-computing.torrent")
    print(torrent.name)
    print(torrent.files)

    storage = Storage(torrent, "downloads")

    piece = Piece.create_empty_piece(1, torrent.piece_length, \
                                         torrent.piece_hash(1))
    print(piece.length)
    print(storage._haves)
    storage.write_piece(piece)
    print(storage.piece(0))
    print(storage.piece(1))
    print(storage._haves)

    storage._close_files()
