import re
import random

ID_LENGTH = 20

CLIENT_ID = b'bL'
CLIENT_VERSION = b'0700'

def generate():
    header = b'-' + CLIENT_ID + CLIENT_VERSION + b'-'
    bytes = SHADOW_STYLE_VERSION
    bytes = ''.join([bytes[random.randrange(len(bytes))] \
                               for _ in range(ID_LENGTH - len(header))])
    return header + bytes.encode('ascii')

UNKNOWN = 'Unknown'

AZUREUS_STYLE_ENCODING = re.compile(b'^-([a-zA-z]{2})(\d{4})-')

AZUREUS_STYLE_CLIENTS = {
    'AG' : 'Ares',
    'A~' : 'Ares',
    'AR' : 'Arctic',
    'AT' : 'Artemis',
    'AX' : 'BitPump',
    'AZ' : 'Azureus',
    'BB' : 'BitBuddy',
    'BC' : 'BitComet',
    'BF' : 'Bitflu',
    'BG' : 'BTG (uses Rasterbar libtorrent)',
    'bL' : 'Bitless',
    'BL' : 'BitBlinder',
    'BP' : 'BitTorrent Pro (Azureus + spyware)',
    'BR' : 'BitRocket',
    'BS' : 'BTSlave',
    'BW' : 'BitWombat',
    'BX' : '~Bittorrent X',
    'CD' : 'Enhanced CTorrent',
    'CT' : 'CTorrent',
    'DE' : 'DelugeTorrent',
    'DP' : 'Propagate Data Client',
    'EB' : 'EBit',
    'ES' : 'electric sheep',
    'FC' : 'FileCroc',
    'FT' : 'FoxTorrent',
    'GS' : 'GSTorrent',
    'HK' : 'Hekate',
    'HL' : 'Halite',
    'HN' : 'Hydranode',
    'KG' : 'KGet',
    'KT' : 'KTorrent',
    'LC' : 'LeechCraft',
    'LH' : 'LH-ABC',
    'LP' : 'Lphant',
    'LT' : 'libtorrent',
    'lt' : 'libTorrent',
    'LW' : 'LimeWire',
    'MK' : 'Meerkat',
    'MO' : 'MonoTorrent',
    'MP' : 'MooPolice',
    'MR' : 'Miro',
    'MT' : 'MoonlightTorrent',
    'NX' : 'Net Transport',
    'OS' : 'OneSwarm',
    'OT' : 'OmegaTorrent',
    'PD' : 'Pando',
    'PT' : 'PHPTracker',
    'qB' : 'qBittorrent',
    'QD' : 'QQDownload',
    'QT' : 'Qt 4 Torrent example',
    'RT' : 'Retriever',
    'RZ' : 'RezTorrent',
    'S~' : 'Shareaza alpha/beta',
    'SB' : '~Swiftbit',
    'SD' : 'Thunder (aka XunLei)',
    'SM' : 'SoMud',
    'SS' : 'SwarmScope',
    'ST' : 'SymTorrent',
    'st' : 'sharktorrent',
    'SZ' : 'Shareaza',
    'TN' : 'TorrentDotNET',
    'TR' : 'Transmission',
    'TS' : 'Torrentstorm',
    'TT' : 'TuoTu',
    'UL' : 'uLeecher!',
    'UM' : 'uTorrent for Mac',
    'UT' : 'uTorrent',
    'VG' : 'Vagaa',
    'WT' : 'BitLet',
    'WY' : 'FireTorrent',
    'XL' : 'Xunlei',
    'XS' : 'XSwifter',
    'XT' : 'XanTorrent',
    'XX' : 'Xtorrent',
    'ZT' : 'ZipTorrent '
}

SHADOW_STYLE_ENCODING = re.compile(b'^([a-zA-Z])(([a-zA-Z0-9]|-|\.){5})')

SHADOW_STYLE_VERSION = \
    '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

SHADOW_STYLE_CLIENTS = {
    'A' : 'ABC',
    'O' : 'Osprey Permaseed',
    'Q' : 'BTQueue',
    'R' : 'Tribler',
    'S' : 'Shadow\'s client',
    'T' : 'BitTornado',
    'U' : 'UPnP NAT Bit Torrent '
}

MAINLINE_STYLE_ENCODING = re.compile(b'^([a-zA-Z])(\d-\d\d?-\d(\d|-))')

MAINLINE_STYLE_CLIENTS = {
    'M' : 'Mainline (Bram\'s client)',
    'Q' : 'Queen Bee'
}

def azureus_encoded(id):
    match = AZUREUS_STYLE_ENCODING.match(id)
    return not match is None

def shadow_encoded(id):
    if not SHADOW_STYLE_ENCODING.match(id) is None:
        sep = id[6:9]
        return all(s == sep[0] for s in sep)

    return False

def mainline_encoded(id):
    match = MAINLINE_STYLE_ENCODING.match(id)
    return not match is None

def encoding(id):
    if azureus_encoded(id): return 'azureus'
    elif shadow_encoded(id): return 'shadow'
    elif mainline_encoded(id): return 'mainline'
    else: return UNKNOWN

def _parse(client, version, name):
    if name is None:
        return UNKNOWN + (' %s/%s' % (client, version))
    else:
        return '%s %s' % (name, version)

def parse_azureus_encoded(id):
    client, version = AZUREUS_STYLE_ENCODING.match(id).groups()
    client = client.decode('ascii')
    name = AZUREUS_STYLE_CLIENTS.get(client, None)

    version = version.decode('ascii')
    version = '.'.join(list(version))

    return _parse(client, version, name)

def parse_shadow_encoded(id):
     match = SHADOW_STYLE_ENCODING.match(id).groups()
     client, version = match[0].decode('ascii'), match[1].decode('ascii')
     name = SHADOW_STYLE_CLIENTS.get(client, None)

     version = list(version.rstrip('-'))
     version = '.'.join([str(SHADOW_STYLE_VERSION.index(v)) for v in version])

     return _parse(client, version, name)

def parse_mainline_encoded(id):
    match = MAINLINE_STYLE_ENCODING.match(id).groups()
    client, version = match[0].decode('ascii'), match[1].decode('ascii')
    name = MAINLINE_STYLE_CLIENTS.get(client, None)

    version = '.'.join([v for v in version.split('-') if v != ''])

    return _parse(client, version, name)

def parse(id):
    return {
        'azureus': parse_azureus_encoded,
        'shadow': parse_shadow_encoded,
        'mainline': parse_mainline_encoded,
        UNKNOWN: lambda id: UNKNOWN
    }[encoding(id)](id)

if __name__ == '__main__':
    id = b'-AZ2030-randomstring'
    print(azureus_encoded(id))
    print(parse_azureus_encoded(id))

    id = b'SBR4--###random'
    print(shadow_encoded(id))
    print(parse_shadow_encoded(id))

    id = b'M4-2-5--random'
    print(mainline_encoded(id))
    print(parse_mainline_encoded(id))

    print(parse(id))

    print(generate())
