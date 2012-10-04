import struct
import utils

class Vector(object):
    @classmethod
    def create(cls, dimension):
        return cls([0] * dimension)
        #return Vector([0] * dimension)

    def __init__(self, vector):
        self._vector = list(vector)
        self._dim = len(vector)
        #self._dim = dimension
        #self._vector = [0] * dimension

    @property
    def dimension(self):
        return self._dim

    def _entry_error(self, e):
        if not (0 <= e < self._dim):
            raise ValueError("Invalid entry")

    def _dim_error(self, other):
        if len(other) != self._dim:
            raise ValueError("Must be of same dimension")

    def update(self, entry, value):
        self._entry_error(entry)
        self._vector[entry] += value

    def set(self, entry, value):
        self._entry_error(entry)
        self._vector[entry] = value

    def get(self, entry):
        self._entry_error(entry)
        return self._vector[entry]

    def __len__(self):
        return self._dim

    def __str__(self):
        return '(' + ', '.join([str(i) for i in self._vector]) + ')'

    def __getitem__(self, entry):
        return self.get(entry)

    def __setitem__(self, entry, value):
        return self.set(entry, value)

    def __iadd__(self, other):
        self._dim_error(other)
        for i in range(self._dim):
            self._vector[i] += other.get(i)

        return self

    def __add__(self, other):
        self._dim_error(other)
        return Vector([other[i] + self.get(i) for i in range(self._dim)])

    def __isub__(self, other):
        self._dim_error(other)
        for i in range(self._dim):
            self._vector[i] -= other.get(i)

        return self

    def __sub__(self, other):
        self._dim_error(other)
        return Vector([self.get(i) - other[i] for i in range(self._dim)])

    def __rsub__(self, other):
        self._dim_error(other)
        return Vector([other[i] - self.get(i) for i in range(self._dim)])


class SynchronizedVector(Vector, metaclass = utils.SynchronizedClass):
    pass


def _create_lookup_table():
    lookup = []
    for i in range(256):
        count = 0
        for j in range(8):
            count += (0xff & i) >> j & 1
        lookup.append(count)
        
    return lookup

def unpack(field, expected_length):
    bitfield = Bitfield(expected_length)
    bitfield._field = list(field)

    if(bitfield.bytesize * 8 < expected_length):
        raise ValueError(\
            "Invalid bitfield, expected length %d does not match the " +\
            "given length %d" % (expected_length, bitfield.bytesize * 8))

    for i in range(expected_length, bitfield.bytesize - expected_length):
        if bitfield.get(i):
            raise ValueError("Invalid bitfield, bits set beyond " +\
                                 "expected length")

    return bitfield

class Bitfield(object):
    _lookup = _create_lookup_table()

    def __init__(self, length):
        self._length = length
        self._field = [0] * (length // 8)
        if length % 8 != 0:
            self._field.append(0)

    def __str__(self):
        res = []
        current = 0
        for i in range(self._length):
            shift = i % 8
            if shift == 0:
                current = self._field[i // 8] & 0xff

            res.append(str(current >> (7 - shift) & 1))

        return ''.join(res)

    def __eq__(self, other):
        if isinstance(other, Bitfield):
            if other._length == self._length:
                for i in range(self._length):
                    if self._field[i] != other._field[i]:
                        return False

                return True

        return False

    def __len__(self):
        return self._length

    def __iter__(self):
        for i in range(self._length):
            yield self.get(i)
        #return Bitfield._BitIterator(self)

    def __getitem__(self, index):
        return self.get(index)

    def __setitem__(self, index, value):
        self.set(index, value)

    def __and__(self, other):
        return self._each_byte(other, lambda x,y: x & y)

    def __or__(self, other):
        return self._each_byte(other, lambda x,y: x | y)

    def _each_byte(self, other, operator):
        if len(other) != self._length:
            raise ValueError("Can't performe operation on bitfields " +\
                                 "of different length")

        field = Bitfield(self._length)
        for b in range(self._length):
            field._field[b] = operator(self._field[b], other._field[b])

        return field

    @property
    def length(self):
        return self._length

    @property
    def bytesize(self):
        return len(self._field)

    def pack(self):
        res = []
        for b in self._field:
            res.append(struct.pack('!B', b))
        return b''.join(res)

    def all_set(self):
        return self.cardinality() == self._length
            
    def cardinality(self):
        count = 0
        for b in self._field:
            count += Bitfield._lookup[b]
        return count

    def set(self, index, to = True):
        if to != self.get(index):
            self.flip(index)

    def flip(self, index):
        if index >= self._length:
            raise IndexError("Invalid index " + str(index))

        i = index // 8
        shift = index % 8
        value = (0xff & self._field[i]) ^ (128 >> shift)
        self._field[i] = value

    def get(self, index):
        if index >= self._length:
            raise IndexError("Invalid index " + str(index))

        i = index // 8
        shift = index % 8
        value = (0xff & self._field[i]) & (128 >> shift)

        return value != 0

    def to_vector(self):
        return Vector([int(b) for b in self])

if __name__ == '__main__':
    field = Bitfield(10)
    print(field.get(5))
    print(field.get(9))

    print(field._field)
    field.flip(8)
    print(field._field)
    field.flip(9)
    print(field._field)
    field.set(5)
    print(field._field)
    print(field.get(8))
    print(field.get(4))

    print(Bitfield._lookup)
    print(field.cardinality())
    print(field.all_set())
    print(field.pack())
    print(field.bytesize)

    print(field)
    print(list(field))
    print(field.to_vector())

    print("------------------------")

    v = Vector([i for i in range(10)])
    w = SynchronizedVector([2*i for i in range(10)])
    u = v
    print(w + v)
    print(v)
    print(w)
    v += w
    print("++++++")
    print(v)
    print(u)
    print(v - w)
    print(w - v)
    print("------")
    v -= w
    print(v)
    print(u)
    print(w)

    x = SynchronizedVector.create(10)
    print(x)
    with x:
        pass
