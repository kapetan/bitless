import base
import bittorrent

import peer_id
        
class Peer(base.Model):
    properties = base.property_set()

    properties.define('id', type = bytes)
    properties.define('ip')
    properties.define('port')

    properties.define('client')

    properties.define('completed')

    properties.define('uploaded')
    properties.define('downloaded')

    properties.define('upload_speed')
    properties.define('download_speed')

    @classmethod
    def _from_bittorrent_peer(cls, peer):
        completed = round(peer.haves.cardinality() / len(peer.haves), 1) \
            if not peer.haves is None else 0

        attrs = {
            'id': peer.id,
            'ip': peer.ip.decode('ascii'),
            'port': peer.port,
            'client': peer_id.parse(peer.id),
            'completed': completed,
            'uploaded': peer.uploaded,
            'downloaded': peer.downloaded,
            'upload_speed': peer.upload_speed(),
            'download_speed': peer.download_speed()
        }

        return cls(attrs)

class PeerManager(base.Model):
    properties = base.property_set()

    properties.define('info_hash', type = bytes)

    properties.define('name')
    
    properties.define('state')

    properties.define('upload_speed')
    properties.define('download_speed')

    properties.define('size')
    properties.define('completed')
    properties.define('uploaded')
    properties.define('ratio')

    @classmethod
    def all(cls):
        return [cls._from_bittorrent_peer_manager(m) for m in \
                    bittorrent.client.managers.values()]

    @classmethod
    def find(cls, info_hash):
        info_hash = base.parse(info_hash, bytes)
        man = cls._find(info_hash)
        if man is None:
            return None

        return cls._from_bittorrent_peer_manager(man)

    @classmethod
    def _find(cls, info_hash):
        return bittorrent.client.manager(info_hash)

    @classmethod
    def _from_bittorrent_peer_manager(cls, manager):
        torrent = manager.torrent
        storage = manager.storage
        tracker = manager.tracker

        down, up = cls._speed(manager)
        ratio = round(tracker.uploaded / tracker.downloaded, 3) \
            if tracker.downloaded else 0

        attrs = {
            'info_hash': torrent.info_hash,
            'name': torrent.name,
            'state': manager.state,
            'upload_speed': up,
            'download_speed': down,
            'size': storage.size(),
            'completed': \
                round(storage.bitfield.cardinality() / \
                          len(storage.bitfield), 2),
            'uploaded': tracker.uploaded,
            'downloaded': tracker.downloaded,
            'ratio': ratio
        }
        
        return cls(attrs)

    @classmethod
    def _speed(cls, man):
        down, up = 0, 0
        for p in man.peers:
            d, u = p.speed()
            down += d
            up += u

        return down, up

    def peers(self):
        man = self._find(self.info_hash)
        return [Peer._from_bittorrent_peer(p) for p in man.peers]
