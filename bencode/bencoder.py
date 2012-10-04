from .bencode_error import BencodeError

def encode(obj):
    if isinstance(obj, str):
        return str(len(obj)).encode('ASCII') + b':' + obj.encode('UTF-8')
    elif isinstance(obj, bytes):
        return str(len(obj)).encode('ASCII') + b':' + obj
    elif isinstance(obj, list):
        return b'l' + b''.join([encode(item) for item in obj]) + b'e'
    elif isinstance(obj, dict):
        enc = []

        for key, value in obj.items():
            if not (isinstance(key, str) or isinstance(key, bytes)):
                raise BencodeError("Key in dictionary must be string")

            enc.append(encode(key))
            enc.append(encode(value))

        return b'd' + b''.join(enc) + b'e'
    elif isinstance(obj, int):
        return b'i' + str(obj).encode('ASCII') + b'e'
    else:
        raise BencodeError("Can't encode " + str(obj) + 
                           " of type " + obj.__class__.__name__)

if __name__ == '__main__':
    print(encode({'a':1, b'b': [1,2,3, 'as', b'haha go']}))
