import argparse
import base64
import dbm
import hashlib
from urllib.request import Request, urlopen

import bjoern


# determine the volume directory path for a given key
def key2path(key):
    bkey = key.encode()
    md5key = hashlib.md5(bkey).digest()
    b64key = base64.b64encode(bkey).decode()
    return '/{:02x}/{:02x}/{:s}'.format(md5key[0], md5key[1], b64key)


# determine which volume(s) keys should be associated with
def key2volume(key, volumes):
    bkey = key.encode()
    best_score = None
    best_volume = None

    # pick the "best" volume for this key
    for volume in volumes:
        bvolume = volume.encode()
        score = hashlib.md5(bvolume + bkey).digest()
        if best_score is None or score > best_score:
            best_score = score
            best_volume = volume

    return best_volume


class Application:

    def __init__(self, db, volumes):
        self.db = db
        self.volumes = volumes

    def __call__(self, environ, start_response):
        method = environ['REQUEST_METHOD']
        key = environ['PATH_INFO']

        headers = []
        if method == 'GET' or method == 'HEAD':
            volume = self.db.get(key)

            # reject invalid keys
            if volume is None:
                start_response('404 Not Found', headers)
                return [b'']

            # determine where this KV pair lives
            path = key2path(key)
            volume = volume.decode()
            remote = 'http://{}{}'.format(volume, path)

            # redirect client to the value's location
            headers.append(('Location', remote))
            start_response('302 Found', headers)
            return [b'']
        elif method == 'PUT':
            # reject empty values
            if environ['CONTENT_LENGTH'] == 0:
                start_response('411 Length Required', headers)
                return [b'']
            # reject duplicate keys
            if key in self.db:
                start_response('409 Conflict', headers)
                return [b'']

            # determine where this KV pair will live
            path = key2path(key)
            volume = key2volume(key, self.volumes)
            remote = 'http://{}{}'.format(volume, path)

            # call out to the volume server
            resp = urlopen(Request(remote, data=environ['wsgi.input'], method='PUT'))
            if resp.status != 201 and resp.status != 204:
                start_response('500 Internal Server Error', headers)
                return [b'']

            # store the KV location into the index
            self.db[key] = volume
            start_response('201 Created', headers)
            return [b'']
        elif method == 'DELETE':
            volume = self.db.get(key)

            # reject invalid keys
            if volume is None:
                start_response('404 Not Found', headers)
                return [b'']

            # determine where this KV pair lives
            path = key2path(key)
            volume = volume.decode()
            remote = 'http://{}{}'.format(volume, path)

            # delete the pair from the index
            del self.db[key]

            # delete the pair from its volume server
            resp = urlopen(Request(remote, method='DELETE'))
            if resp.status != 204:
                start_response('500 Internal Server Error', headers)
                return [b'']

            start_response('204 No Content', headers)
            return [b'']
        else:
            start_response('405 Method Not Allowed', headers)
            return [b'']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the pymkv index server')
    parser.add_argument('volume', nargs='+', help='address of a volume server')
    parser.add_argument('--port', type=int, default=3000, help='index server port')
    parser.add_argument('--index', default='/tmp/indexdb', help='path to index database')
    args = parser.parse_args()

    volumes = list(args.volume)
    with dbm.open(args.index, 'c') as db:
        try:
            app = Application(db, volumes)
            print('PyMKV is listening on :{}'.format(args.port))
            bjoern.run(app, host='0.0.0.0', port=args.port, reuse_port=True)
        except KeyboardInterrupt:
            pass
