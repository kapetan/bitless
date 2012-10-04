(function($) {
    Array.prototype.remove = function(from, to) {
	var rest = this.slice((to || from) + 1 || this.length);
	this.length = from < 0 ? this.length + from : from;
	return this.push.apply(this, rest);
    }

    Array.prototype.find = function(func) {
	for(var i = 0; i < this.length; i++)
	    if(func(this[i])) return this[i];

	return null;
    }

    function Client(torrentPad, peerPad) {
	this.torrentPad = $(torrentPad);
	this.peerPad = $(peerPad);

	this.torrents = [];
    }

    Client.prototype = {
	TORRENT_UPDATE: 5000,
	PEER_UPDATE: 3000,

	fetchTorrents: function(before, after) {
	    var self = this;

	    $.ajax('/torrents/', {
		type: 'GET',
		success: function(data) {
		    if(before) before();

		    /*
		    var remove = self.torrents.filter(function(t) {
			return !data.find(function(torrent) {
			    return t.equal(torrent);
			});
		    });

		    $.each(remove, function(i, t) {
			self.removeTorrent(t);
		    }); */

		    $.each(self.torrents, function(i, t) {
			var remove = !data.find(function(torrent) {
			    return t.equals(torrent);
			});

			if(remove)
			    self.removeTorrent(t);
		    });

		    $.each(data, function(i, t) {
			var torrent = 
			    new Torrent(self, self.torrentPad, t);
			self.torrent(torrent);
		    });

		    if(after) after();
		}
	    });
	},

	createTorrent: function(inp, before) {
	    var self = this;

	    var fd = new FormData();
	    fd.append('torrent', inp.files[0]);
	    var xhr = new XMLHttpRequest();

	    xhr.onreadystatechange = function() {
		switch(xhr.readyState) {
		case 1:
		case 2:
		    uploading(true);
		    break;
		case 3:
		    uploading(false);
		    downloading(true);
		    break;
		case 4:
		    uploading(false);
		    downloading(false);

		    var status = xhr.status;
		    if(200 <= status && status < 300) {
			// It went okay
		    }
		    else {
			console.error("Server responded with " + 
				      status + ": " + xhr.responseText);
		    }
		    break;
		}
	    }

	    xhr.open('POST', '/torrents/create');
	    xhr.send(fd);
	},

	createTorrenFromUrl: function(url, before) {
	    
	},

	destroyTorrent: function(torrent, before) {
	    var self = this;

	    $.ajax('/torrents/destroy', {
		type: 'POST',
		data: { info_hash: torrent.info_hash },
		success: function() {
		    if(before) before();
		    self.removeTorrent(torrent);
		}
	    });
	},

	fetchPeers: function(torrent, before, after) {
	    var self = this;

	    $.ajax('/torrents/peers/', {
		type: 'GET',
		data: { info_hash: torrent.info_hash },
		error: function() {
		    if(before) before();
		    if(after) after();
		},
		success: function(data) {
		    if(before) before();
		    var peers = data.map(function(p) {
			return new Peer(self.peerPad, p);
		    });
		    torrent.setPeers(peers);
		    if(after) after();
		}
	    });
	},

	loadPeers: function(torrent) {
	    if(this.currentTorrent && !this.currentTorrent.equals(torrent))
		this.currentTorrent.destroyPeers();

	    this.currentTorrent = torrent;
	    this.fetchPeers(torrent);
	},

	run: function() {
	    var self = this;
	    
	    var torrentUpdate = function() {
		setTimeout(function() { 
		    self.fetchTorrents(null, torrentUpdate); 
		}, self.TORRENT_UPDATE);
	    }
	    this.fetchTorrents(null, torrentUpdate);

	    var peerUpdate = function() {
		setTimeout(function() {
		    if(self.currentTorrent)
			self.fetchPeers(self.currentTorrent, null, peerUpdate);
		    else
			peerUpdate();
		}, self.PEER_UPDATE);
	    }
	    peerUpdate();
	},

	eachTorrent: function(func) {
	    for(var i = 0; i < this.torrents.length; i++)
		func(this.torrents[i], i);
	},

	renderTorrents: function() {
	    this.eachTorrent(function(t) { t.render(); });
	},

	destroyTorrents: function() {
	    this.eachTorrent(function(t) { t.destroy(); });
	},

	selectAllTorrents: function() {
	    this.eachTorrent(function(t) { t.select(); });
	},

	unselectAllTorrents: function() {
	    this.eachTorrent(function(t) { t.unselect(); });
	},

	eachSelectedTorrent: function(func) {
	    this.eachTorrent(function(t, i) {
		if(t.selected())
		    func(t, i);
	    });
	},

	destroySelectedTorrents: function() {
	    var self = this;
	    this.eachSelectedTorrent(function(t) {
		self.destroyTorrent(t);
	    });
	},

	findTorrent: function(comp) {
	    for(var i = 0; i < this.torrents.length; i++) {
		var t = this.torrents[i];
		if(comp(t)) return t;
	    }

	    return null;
	},

	hasTorrent: function(torrent) {
	    return !!this.findTorrent(function(t) { t.equals(torrent) });
	},

	addTorrent: function(torrent) {
	    if(!this.hasTorrent(torrent))
		this.torrents.push(torrent);
	    
	    return torrent;
	},

	torrent: function(torrent) {
	    var t = this.findTorrent(function(t) { 
		return t.equals(torrent) 
	    });

	    if(t)
		t.updateAttributes(torrent);
	    else {
		this.addTorrent(torrent);
		torrent.render();
	    }
	},

	removeTorrent: function(torrent) {
	    var self = this;
	    this.eachTorrent(function(t, i) {
		if(t.equals(torrent)) {
		    t.destroy();
		    t.destroyPeers();
		    self.torrents.remove(i);
		    if(self.currentTorrent && 
		       self.currentTorrent.equals(torrent)) {
			self.currentTorrent = null;
		    }
		}
	    });
	}
    }

    var Base = function() {}

    Base.prototype = {
	destroy: function() {
	    if(this.element)
		this.element.remove();

	    this.element = null;
	},

	updateAttributes: function(options) {
	    for(key in options)
		this.update(key, options[key]);
	},

	update: function(name, value) {
	    if(this.attributes.indexOf(name) == -1 || !this.element)
		return;

	    /*var position = this.attributes.indexOf(name) + 2;
	    var child = $('td:nth-child(' + position + ')', this.element);
	    */
	    var child = 
		$('td[data-attribute="' + name + '"]', this.element);
	    this[name] = value;
	    child.text(value);
	}
    };

    function Torrent(client, pad, options) {
	this.client = client;
	this.pad = $(pad);
	$.extend(this, options);

	this.peers = [];
    }

    Torrent.prototype = new Base();

    Torrent.prototype.attributes = ['size', 'completed', 'download_speed', 
				    'upload_speed', 'uploaded', 'ratio'];

    Torrent.prototype.renderEmpty = function() {
	this.destroy();

	var tr = $('<tr>');
	for(var i = 0; i < 9; i++)
	    tr.append('<td>&nbsp;</td>');

	this.pad.append(tr);
	this.element = tr;
    }

    Torrent.prototype.render = function() {
	var self = this;

	this.destroy();
	
	var tr = $('<tr data-id="' + this.info_hash + '">');
	tr.append('<td><input type="checkbox"/></td>');
	tr.append('<td data-attribute="state">' + this.state + '</td>');

	var a = $('<a href="javascript:void(0);">' + this.name + '</a>');
	a.click(function() {
	    //self.client.unselectAllTorrents();
	    self.select();
	    self.client.loadPeers(self);
	});

	tr.append($('<td>').attr('data-attribute', 'name').append(a));

	//tr.append('<td><a class="load-peers" href="#">' + 
	//	  this.name + '</a></td>');

	$.each(this.attributes, function(i, attr) {
	    var td = $('<td>').text(self[attr]).attr('data-attribute', attr);
	    /*if(attr === 'completed') {
		td = $('<td class="progress">');
		var progress = $('<progress max="100" value="' + 
				 self[attr] + '"></progress>');
		td.append(progress);
		td.append('<tt> ' + self[attr] + '%</tt>');
	    }*/

	    //if(attr === 'completed') td.addClass('progress');
	    tr.append(td);
	});

	this.pad.append(tr);
	this.element = tr;
    }

    Torrent.prototype.equals = function(other) {
	return this.info_hash === other.info_hash;
    }
    
    Torrent.prototype.renderPeers = function() {
	this.eachPeer(function(peer) { peer.render(); });
	this.showingPeers = true;
    }

    Torrent.prototype.destroyPeers = function() {
	this.eachPeer(function(peer) { peer.destroy(); });
	this.showingPeers = false;
    }

    Torrent.prototype.eachPeer = function(block) {
	for(var i = 0; i < this.peers.length; i++)
	    block(this.peers[i], i);
    }

    Torrent.prototype.findPeer = function(comp) {
	for(var i = 0; i < this.peers.length; i++) {
	    var p = this.peers[i];
	    if(comp(p)) return p;
	}

	return null;
    }

    Torrent.prototype.hasPeer = function(peer) {
	return !!this.findPeer(function(p) { return p.equals(peer) });
    }

    Torrent.prototype.addPeer = function(peer) {
	if(!this.hasPeer(peer))
	    this.peers.push(peer);

	return peer;
    }

    Torrent.prototype.peer = function(peer) {
	var p = this.findPeer(function(p) { return p.equals(peer); });
	if(p)
	    p.updateAttributes(peer);
	else
	    this.addPeer(peer).render();
    }

    Torrent.prototype.setPeers = function(peers) {
	var remove = this.peers.filter(function(p) {
	    return !peers.find(function(peer) { return p.equals(peer) });
	});

	var self = this;

	$.each(remove, function(i, p) {
	    self.removePeer(p);
	});

	$.each(peers, function(i, p) {
	    self.peer(p);
	});
    }

    Torrent.prototype.removePeer = function(peer) {
	var self = this;
	this.eachPeer(function(p, i) {
	    if(p.equals(peer)) {
		p.destroy();
		self.peers.remove(i);
	    }
	});
    }

    Torrent.prototype.selected = function() {
	return $('input:checkbox', this.element).is(':checked');
    }

    Torrent.prototype.select = function() {
	$('input:checkbox', this.element).attr('checked', 'checked');
    }

    Torrent.prototype.unselect = function() {
	$('input:checkbox', this.element).removeAttr('checked');
    }

    function Peer(pad, options) {
	this.pad = $(pad);
	$.extend(this, options);
    }

    Peer.prototype = new Base();

    Peer.prototype.attributes = ['ip', 'client', 'completed', 'uploaded', 
		'downloaded', 'upload_speed', 'download_speed'];

    Peer.prototype.renderEmpty = function() {
	this.destroy();

	var tr = $('<tr>');
	for(var i = 0; i < 7; i++)
	    tr.append('<td>&nbsp;</td>');

	this.pad.append(tr);
	this.element = tr;
    }

    Peer.prototype.render = function() {
	var self = this;

	this.destroy();

	tr = $('<tr>');
	$.each(this.attributes, function(i, attr) {
	    td = $('<td>').text(self[attr]).attr('data-attribute', attr);
	    tr.append(td);
	});

	this.pad.append(tr);
	this.element = tr;
    }

    Peer.prototype.equals = function(other) {
	return other.ip === this.ip && other.port === this.port;
    }

    function Overlay(element, options) {
	this.element = $(element);
	this.element.hide();
	this.element.addClass('overlay');

	var self = this;

	$('.close', this.element).click(function() {
	    self.hide();
	});

	this.modal = $('.modal');
	$.extend(this, options);
    }

    Overlay.prototype = {
	hide: function() {
	    this.element.hide();
	    this.modal.hide();
	    
	},

	show: function() {
	    this.modal.show();
	    this.element.show();
	    this.element.center();
	},

	destroy: function() {
	    $('.close', this.element).unblind('click');
	    this.element.remove();
	}
    }

    $.fn.overlay = function() {
	return new Overlay(this);
    }

    $.fn.center = function () {
	this.css("position","absolute");
	this.css("top", ( $(window).height() - this.height() ) / 2 + 
		 $(window).scrollTop() + "px");
	this.css("left", ( $(window).width() - this.width() ) / 2 + 
		 $(window).scrollLeft() + "px");
	return this;
    }

    //var down = $('#activety-bar .download');
    function downloading(active, element) {
	//if(!element)
	element = element ? $(element) : $('#activety-bar .download');

	//console.log(element); console.log(active);

	element.css('opacity', (active ? 1.0 : 0.5))

	//console.log(element);
    }

    //var up = $('#activety-bar .upload');
    function uploading(active, element) {
	//console.log(up);
	//if(!element)
	element = element ? $(element) : $('#activety-bar .upload');


	//console.log(element); console.log(active);

	element.css('opacity', (active ? 1.0 : 0.5));

	//console.log(element);
    }

    function both(active, element) {
	downloading(active, element);
	uploading(active, element);
    }

    $(function() {
	var c = new Client('#torrents > tbody', '#info > tbody');
	c.run();
	//c.fetchTorrents();
	//c.renderTorrents();

	for(var i = 0; i < 5; i++)
	    new Torrent(c, '#torrents > tbody').renderEmpty();

	for(var i = 0; i < 5; i++)
	    new Peer('#info > tbody').renderEmpty();

	// Torrent selection
	$('#torrents input:checkbox').click(function() {
	    if($(this).is(':checked'))
		c.selectAllTorrents();
	    else
		c.unselectAllTorrents();
	});

	// Icons
	$('#add-torrent').file(function(inp) {
	    c.createTorrent(inp);
	});

	var win = $('#download-torrent-window').overlay();

	$('#download-torrent').click(function() {
	    win.show();
	});

	$('#remove-torrent').click(function() {
	    c.destroySelectedTorrents();
	});

	// Activety bar
	$(document).ajaxSend(function() {
	    //downloading(true, this);
	    //uploading(true, this);
	    both(true);
	});

	$(document).ajaxComplete(function() {
	    //downloading(false, this);
	    //uploading(false, this);
	    both(false);
	});
    });
})(jQuery);