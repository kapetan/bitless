# Bitless

A small BitTorrent client library written using Python 3. It is not finished, but all the core functionalities are in place: encoding/decoding torrent files, retrieving peer lists from trackers, writting/reading files from disk, exchanging messages with other peers and coordinating file download and upload.

Given a torrent file the client is able to download the specified files from other peers and subsequently share the downloaded files.

# Usage

See `main.py` for an usage example. There is also a web interface created with [CherryPy][cp] (see the `web/` directory).

Additionally there is a client console (`console.py`), which starts a chat session in the terminal, allowing you manually to talk to other BitTorrent clients. Run `python console.py [path_to_torrent_file]` and call the `available()` function, after the session has started, to see available commands.

[cp]: http://www.cherrypy.org/ "CherryPy"
