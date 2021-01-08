import argparse
import dbm

import bjoern

from pymkv import core


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the pymkv index server')
    parser.add_argument('volume', nargs='+', help='address of a volume server')
    parser.add_argument('--port', type=int, default=3000, help='index server port')
    parser.add_argument('--index', default='/tmp/indexdb', help='path to index database')
    args = parser.parse_args()

    volumes = list(args.volume)
    with dbm.open(args.index, 'c') as db:
        try:
            app = core.Application(db, volumes)
            print('PyMKV is listening on :{}'.format(args.port))
            bjoern.run(app, host='0.0.0.0', port=args.port, reuse_port=True)
        except KeyboardInterrupt:
            pass
