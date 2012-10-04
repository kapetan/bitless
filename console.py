import sys
import code
import optparse

import environment

def main():
    #if len(sys.argv) < 2:
    #    print("usage: python %prog <torrent> [options]")
    #    return

    opts = optparse.OptionParser(\
        usage = "usage: python console.py <torrent> [options]")
    opts.add_option('-s', '--store', action = 'store_true', \
                        dest = 'store', help = 'files are written to disk')
    opts.add_option('-p', '--path', default = 'downloads', dest = 'path',\
      metavar = 'DIR', help = 'in which dir to store/retrieve the files')
    opts.add_option('-a', '--accept', action = 'store_true', \
      dest = 'accept', help = 'starts listening for incoming connections')

    options, args = opts.parse_args()
    if len(args) != 1:
        opts.error('incorrect number of arguments')

    peer_id = b'a0b1c2d3e4f5g6h7i8j9'
    env = environment.initialize(args[0], peer_id, \
                                     options.store, options.path)
    console = code.InteractiveConsole(env)
    
    console.interact("Python interactive console %s.\nBitTorrent chat client using bitless." % sys.version)

    environment.shutdown()
    print("Finished...")

if __name__ == '__main__':
    main()
