from .bencode_error import BencodeError

def decode(string, level = -2):
    decoded, index = _decode(string, 0, level)
    return decoded

def _decode(string, index, level):
    try:
        values = {
            ord('i'): _decode_integer,
            ord('l'): _decode_list,
            ord('d'): _decode_dictionary,
            ord('0'): _decode_string,
            ord('1'): _decode_string,
            ord('2'): _decode_string,
            ord('3'): _decode_string,
            ord('4'): _decode_string,
            ord('5'): _decode_string,
            ord('6'): _decode_string,
            ord('7'): _decode_string,
            ord('8'): _decode_string,
            ord('9'): _decode_string
        }
        if  -1 <= level <= 0:
            decoded, end = values.get(string[index])(string, index, -2)
            return string[index:end], end
        else:
            return values.get(string[index])(string, index, level - 1)
    except TypeError:
        raise BencodeError("Unexpected character " + chr(string[index]) + 
                           " at " + str(index))
    except IndexError:
        raise BencodeError("Unexpected end of string at " + str(index))

def _decode_string(string, index, level):
    try:
        end = string.index(b':', index)
        length = string[index:end]
        length = int(length)

        index = end + length + 1
        return string[end + 1:index], index
    except ValueError:
        raise BencodeError("Invalid string at " + str(index))

def _decode_integer(string, index, level):
    try:
        end = string.index(b'e', index)

        return int(string[index + 1:end]), end + 1
    except ValueError:
        raise BencodeError("Invalid integer at " + str(index))

def _decode_list(string, index, level):
    try:
        index += 1
        next = string[index]
        res = []

        while(next != ord('e')):
            decoded, index = _decode(string, index, level)
            res.append(decoded)
            next = string[index]
            
        return res, index + 1
    except IndexError:
        raise BencodeError("Invalid list at " + str(index))

def _decode_dictionary(string, index, level):
    try:
        index += 1
        next = string[index]
        res = {}

        while(next != ord('e')):
            decoded_key, index = _decode(string, index, level)
            if not isinstance(decoded_key, bytes):
                raise BencodeError("Invalid dictionary at " + str(index) 
                                   + ", key must be a string")
            decoded_value, index = _decode(string, index, level - 1)
            res[decoded_key] = decoded_value
            next = string[index]

        return res, index + 1
    except IndexError:
        raise BencodeError("Invalid dictionary at " + str(index))

if __name__ == '__main__':
    print(decode(b'd4:sapmlee'))
    print(decode(b'd4:spamli34ei-3eee'))

    d = decode(b'd4:spamli23ei4e2:asd5:12345leee4:sponi345ee', 2)
    print(d)
