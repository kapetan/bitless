import urllib.parse as parse
import urllib.request as request
import random
import socket
import struct
import logging
import time

import utils
import bencode.bdecoder as bdecoder
from bencode.bencode_error import BencodeError

NUMWANT = 30

EVENT_STARTED = 'started'
EVENT_STOPPED = 'stopped'
EVENT_COMPLETED = 'completed'

RETRY = 300 # Seconds

_logger = logging.getLogger('bittorrent.tracker')

class TrackerResponseError(Exception):
    pass

class TrackerManager(object):
    def __init__(self, torrent, left, peer_id, port):
        self._torrent = torrent
        self._peer_id = peer_id
        self._port = port

        self._trackers = []
        self._current_tracker = None

        self.downloaded = 0
        self.uploaded = 0
        self.left = left

        announce_list = torrent.announce_list
        if not announce_list is None:
            self._number_of_trackers = 0
            for tier in announce_list:
                self._number_of_trackers += len(tier)
                t = [TrackerClient(a, torrent.info_hash,\
                    peer_id, port, left) for a in tier]
                random.shuffle(t)
                self._trackers.append(t)
        else:
            self._number_of_trackers = 1
            self._trackers.append([TrackerClient(torrent.announce, \
                  torrent.info_hash, peer_id, port, left)])

    def _tier(self, next):
        off = next
        t = None
        for tier in self._trackers:
            length = len(tier)
            if off < length:
                t = tier
                break
            else:
                off -= length

        return t, off

    def _tracker(self, tracker):
        tier, off = self._tier(tracker)
        return tier[off]

    def _success(self, tracker):
        tier, off = self._tier(tracker)
        client = tier.pop(off)
        tier.insert(0, client)

    def _send_event(self, event):
        for tracker in self.active_trackers():
            try:
                tracker.event = event
                tracker.request(0)
            except (TrackerResponseError, request.URLError) as err:
                _logger.info("Could not send %s event to tracker %s" \
                                 % (event, tracker.announce))

    def started(self):
        return self.request()

    completed = lambda self: self._send_event(EVENT_COMPLETED)

    stopped = lambda self: self._send_event(EVENT_STOPPED)

    def any_ready(self):
        for tracker in self.trackers():
            if not tracker.wait():
                return True

        return False

    # Trackers which have successfully received the started event
    def active_trackers(self):
        for tracker in self.trackers():
            if tracker.active:
                yield tracker

    def trackers(self):
        for t in range(self._number_of_trackers):
            yield self._tracker(t)

    def update_downloaded(self, down):
        self.downloaded += down
        for tracker in self.active_trackers():
            tracker.update_downloaded(down)

    def update_uploaded(self, up):
        self.uploaded += up
        for tracker in self.active_trackers():
            tracker.update_uploaded(up)

    def update_left(self, left):
        self.left -= left
        for tracker in self.active_trackers():
            tracker.update_left(left)

    def request(self, numwant = NUMWANT, force = False):
        for t,tracker in enumerate(self.trackers()):
            if tracker.wait() and not force:
                _logger.info("Skipping tracker %s" % tracker.announce)
                continue

            try:
                resp = tracker.request(numwant)
                self._success(t)
                return resp
            except (TrackerResponseError, request.URLError, \
                        KeyError) as err:
                tracker.request_failed()
                _logger.info("Could not contact tracker %s. %s" %\
                                 (tracker.announce, err))

        _logger.info("Could not contact any tracker")
        return None
        #raise request.URLError("Could not connect any tracker")


class AsyncTrackerManager(TrackerManager):
    def __init__(self, peer_manager, left, port):
        super(AsyncTrackerManager, self).__init__(\
            peer_manager.torrent, left, peer_manager.peer_id, port)
        
        self._peer_manager = peer_manager
        self._worker = utils.TimerTask()
        self._worker.start()
        self._waiting = False

    def _contact(self, numwant, force):
        resp = super(AsyncTrackerManager, self).request(numwant, force)
        self._waiting = False
        if not resp is None:
            self._peer_manager.tracker_responded(resp)
            #self._waiting = False
        else:
            self.request(numwant, force)

    def halt(self):
        self._worker.halt()

    def request(self, numwant = NUMWANT, force = False):
        if self._waiting:
            return
        self._waiting = True

        if self.any_ready() or force:
            self._worker.now(self._contact, numwant, force)
        else:
            next = min([t.next_contact for t in self.trackers()])
            self._worker.at(next, self._contact, numwant, force)


class TrackerClient(object):
    _TIMEOUT = 10

    def __init__(self, announce, info_hash, peer_id, port, left):
        self._announce = announce
        self._info_hash = info_hash

        self._peer_id = peer_id
        self._port = port

        self.downloaded = 0
        self.uploaded = 0
        self.left = left
        self._tracker_id = None
        self._last_event = EVENT_STARTED
        self._active = False
        self._next_contact = None

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "<TrackerClient (%s) downloaded=%s uploaded=%s left=%s>" \
            % (self._announce, self.downloaded, self.uploaded, self.left)

    @property
    def announce(self):
        return self._announce

    @property
    def active(self):
        return self._active

    @property
    def next_contact(self):
        return self._next_contact

    @property
    def event(self):
        return self._last_event

    @event.setter
    def event(self, e):
        self._last_event = e

    def request_failed(self):
        self._next_contact = time.time() + RETRY

    def wait(self):
        return self._next_contact and time.time() < self._next_contact

    def update_downloaded(self, value):
        self.downloaded += value

    def update_uploaded(self, value):
        self.uploaded += value

    def update_left(self, value):
        self.left -= value

    def set_progress(self, down, up, left):
        self.downloaded = down
        self.uploaded = up
        self.left = left

    def request(self, numwant = NUMWANT):
        params = {
            'info_hash': self._info_hash,
            'peer_id': self._peer_id,
            'port': self._port,
            'uploaded': self.uploaded,
            'downloaded': self.downloaded,
            'left': self.left,
            'compact': 1,
            'no_peer_id': 1,
            'numwant': numwant
        }

        if self._tracker_id:
            params['trackerid'] = self._tracker_id
        
        if self._last_event:
            params['event'] = self._last_event
            self._last_event = None

        url = self._announce + "?" + parse.urlencode(params)
        _logger.info("Contacting tracker on url %s" % url)
        resp = request.urlopen(url, timeout=TrackerClient._TIMEOUT)
        
        content = resp.read()
        resp.close()
        tracker_response = TrackerResponse(content, self)

        self._tracker_id = tracker_response.tracker_id
        if tracker_response.interval:
            self._next_contact = time.time() + tracker_response.interval
        self._active = True

        return tracker_response


class TrackerResponse(object):
    def __init__(self, response, tracker):
        self._tracker = tracker
        self._parse_response(response)

    def _parse_response(self, resp):
        parsed = None
        try:
            parsed = bdecoder.decode(resp)
        except BencodeError as err:
            raise TrackerResponseError("Response parsing failed. %s" % err)

        if b'failure reason' in parsed:
            _logger.info("Tracker %s failure, with %s" %\
                             (self._tracker.announce, parsed[b'failure']))
            raise TrackerResponseError(\
                parsed[b'failure reason'].decode('UTF-8'))

        self._interval = parsed[b'interval']
        self._min_interval = parsed.get(b'min interval', 0)
        self._tracker_id = parsed.get(b'tracker id', None)
        self._complete = parsed[b'complete']
        self._incomplete = parsed[b'incomplete']
        
        peers = parsed[b'peers']
        if isinstance(peers, list):
            self._peers = peers
        else:
            if len(peers) % 6 != 0:
                _logger.info("Invalid peer list length from tracker %s" \
                                 % self._tracker.announce)
                raise TrackerResponseError("Peer list corrupted")

            self._peers = []
            start = 0
            while start < len(peers):
                ip = peers[start:start + 4]
                ip = socket.inet_ntoa(ip)
                port = peers[start + 4:start + 6]
                port, = struct.unpack('!H', port)

                self._peers.append({b'ip': ip, b'port': port})

                start += 6

    @property
    def interval(self):
        return self._interval

    @property
    def min_interval(self):
        return self._min_interval

    @property
    def tracker_id(self):
        return self._tracker_id

    @property
    def complete(self):
        return self._complete

    @property
    def incomplete(self):
        return self._incomplete

    @property
    def peers(self):
        return self._peers

    @property
    def tracker(self):
        return self._tracker

    def peers_enum(self):
        for peer in self._peers:
            yield peer[b'ip'], peer[b'port']


if __name__ == '__main__':
    import torrent

    torrent = torrent.Torrent("trusted-computing.torrent")
    tracker = TrackerManager(\
        torrent, torrent.length, "a1b2c3d4e5f6g7h8i9j0", 6881)
    response = tracker.request()

    print(response.interval)
    print(response.min_interval)
    print(response.peers)
    print(len(response.peers))
    print(response.complete)
    print(response.incomplete)
    print(response.tracker_id)
    print(response.tracker)

    for peer in response.peers_enum():
        print(peer)
