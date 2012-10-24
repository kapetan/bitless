# Bitless

A small BitTorrent client library written using Python 3. It is not finished, but all the core functionalities are in place: encoding/decoding torrent files, retrieving peer lists from trackers, writting/reading files from disk, exchanging messages with other peers and coordinating file download and upload.

Given a torrent file the client is able to download the specified files from other peers and subsequently share the downloaded files.

# Usage

See `main.py` for an usage example using the `main.Client` class. There is also a web interface created with [CherryPy][cp] (see the `web/` directory).

Additionally there is a client console (`console.py`), which starts a chat session in the terminal, allowing you manually to talk to other BitTorrent clients. Run `python console.py [path_to_torrent_file]` and call the `available()` function, after the session has started, to see available commands.

To download/upload file using the individual library components, following code can be run

```Python
import torrent
import manager
import tracker_client
import storage
import peer_id

# Generate an id and initiate an ConnectionAcceptor, which will
# listen for incomming connections
my_id = peer_id.generate()
acceptor = manager.ConnectionAcceptor()

# Parse .torrent file and prepare to retrieve and store file pieces
meta = torrent.Torrent.from_file('/path/to/file.torrent')
store = storage.SynchronizedStorage(meta)

coordinator = manager.PeerManager(my_id, acceptor, meta, store)

# Create a composite tracker instance which manages communications with all
# available trackers specified in the .torrent file
tracker = tracker_client.AsyncTrackerManager(coordinator, store.missing(), acceptor.port)

# Register tracker and start download/upload
coordinator.set_tracker(tracker)
coordinator.start()

# Start listening for incoming connections.
acceptor.start()
```

When downloading/uploading multiple files using different .torrent files, it is possible to reuse the same `ConnectionAcceptor` and peer id (`my_id` in the example). For every other .torrent file, a new `torrent.Torrent` instance needs to be created together with a new `storage.SynchronizedStorage`, `manager.PeerManager` and `tracker_client.AsyncTrackerManager`. The acceptor should only be started once.

# License 

**This software is licensed under "MIT"**

> Copyright (c) 2012 Mirza Kapetanovic
> 
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the 'Software'), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
> 
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
> 
> THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

[cp]: http://www.cherrypy.org/ "CherryPy"
