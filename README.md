# Bitless

A small BitTorrent client library written using Python 3. It is not finished, but all the core functionalities are in place: encoding/decoding torrent files, retrieving peer lists from trackers, writting/reading files from disk, exchanging messages with other peers and coordinating file download and upload.

Given a torrent file the client is able to download the specified files from other peers and subsequently share the downloaded files.

# Usage

See `main.py` for an usage example. There is also a web interface created with [CherryPy][cp] (see the `web/` directory).

Additionally there is a client console (`console.py`), which starts a chat session in the terminal, allowing you manually to talk to other BitTorrent clients. Run `python console.py [path_to_torrent_file]` and call the `available()` function, after the session has started, to see available commands.

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
