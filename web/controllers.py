from models import *
import base
import bittorrent

import cherrypy
from cherrypy.process import plugins

class PeerResource(object):
    @base.produces_json
    def index(self, info_hash = ''):
        manager = PeerManager.find(info_hash)
        if not manager is None:
            return manager.peers()
        else:
            raise cherrypy.HTTPError(404)

class PeerManagerResource(object):
    peers = PeerResource()

    @base.produces_json
    def index(self):
        return PeerManager.all()

    @cherrypy.expose
    def destroy(self, info_hash):
        man = bittorrent.client.halt_manager(base.parse(info_hash, bytes))
        if man is None:
            raise cherrypy.HTTPError(404)

    @cherrypy.expose
    def create(self, torrent):
        try:
            #print('-----------------------', torrent.file.read())
            bittorrent.client.start(torrent.file.read())
        except:
            raise cherrypy.HTTPError(422)

        #raise cherrypy.HTTPRedirect('/client.html')

class ClientResource(object):
    torrents = PeerManagerResource()
    
    @base.produces_json
    def index(self):
        return {'peer_id': bittorrent.client.peer_id.decode('ascii')}

class BittorrentClient(plugins.SimplePlugin):
    def __init__(self, bus):
        super(BittorrentClient, self).__init__(bus)

    def start(self):
        bittorrent.start_client()
        #bittorrent.client.start('../computing.torrent')

    def stop(self):
        bittorrent.stop_client()

client = BittorrentClient(cherrypy.engine)
client.subscribe()

#cherrypy.config.update('server.config')

cherrypy.quickstart(ClientResource(), config = 'server.config')
