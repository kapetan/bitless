import sys
sys.path.append('..')

import cherrypy

import json
import struct

class Encoder(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, 'serialize'):
            return o.serialize()
        
        return super(Encoder, self).default(o)

JSON = Encoder()

def encode_json(o):
    return JSON.encode(o)

def produces_json(f):
    def deco(self, *args, **kwargs):
        out = f(self, *args, **kwargs)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return encode_json(out).encode('ascii')

    deco.exposed = True

    return deco

def serialize_bytes(value):
    return ''.join(['%02x' % b for b in value])

def parse_bytes(value):
    result = []
    for i in range(0, len(value), 2):
        v = value[i:i+2]
        result.append(int(v, 16))

    print(result)
    return struct.pack('%dB' % len(result), *result)

def serialize(value):
    return serializers.get(type(value), lambda x: x)(value)

serializers = {
    bytes: serialize_bytes
}

def parse(value, of_type):
    return parsers.get(of_type, lambda x: x)(value)

parsers = {
    bytes: parse_bytes
}

class Property(object):
    def __init__(self, name, options):
        self._name = name
        self._options = options

        if not 'key' in options: options['key'] = name
        if not 'type' in options: options['type'] = str

    def __str__(self):
        return self._name

    def __eq__(self, other):
        return str(other) == self._name

    @property
    def name(self):
        return self._name

    @property
    def key(self):
        return self._options['key']

    @property
    def type(self):
        return self._options['key']

    def value(self, obj):
        return getattr(obj, self._name, None)

    def parse(self, value):
        parser = self._options.get('parse', parsers.get(\
                self._options['type'], lambda x: x))
        return self._name, parser(value)

    def serialize(self, obj):
        value = self.value(obj)
        serializer = self._options.get('serialize', serialize)
        return self._options.get('key', self._name), serializer(value)

class Properties(object):
    def __init__(self):
        self._defined = []

    def __iter__(self):
        return (prop for prop in self._defined)

    def define(self, name, **options):
        self._defined.append(Property(name, options))

def property_set():
    return Properties()

class Model(object):
    @classmethod
    def parse(cls, attributes):
        result = {}

        for name, value in attributes.items():
            prop = next(\
               (prop for prop in cls.properties if prop.key == name), None)
            if not prop is None:
                n, v = prop.parse(value)
                result[n] = v

        return cls(result)

    def __init__(self, attrs = {}):
        for prop in self.properties:
            setattr(self, prop.name, None)

        self.attributes = attrs

    @property
    def attributes(self):
        return dict([(prop.name, prop.value(self)) for prop in \
                         self.properties if not prop.value(self) is None])

    @attributes.setter
    def attributes(self, attrs):
        for name, value in attrs.items():
            if name in self.properties:
                setattr(self, name, value)

    def to_json(self):
        return json.dumps(self.serialize())

    def serialize(self):
        out = {}
        for prop in self.properties:
            name, value = prop.serialize(self)
            if not value is None:
                out[name] = value

        return out
