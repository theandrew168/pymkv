import argparse
import base64
from contextlib import contextmanager
import dbm
import hashlib
import os
import subprocess
import tempfile
from urllib.request import Request, urlopen

import waitress


def nginx_index_server_conf(port, proxy_port):
    nginx_conf = """
    daemon off;
    worker_processes auto;
    pcre_jit on;

    pid nginx_index.pid;
    error_log /dev/stderr;

    events {
        multi_accept on;
        accept_mutex off;
        worker_connections 4096;
    }

    http {
        access_log off;

        tcp_nodelay on;
        tcp_nopush on;

        server_tokens off;
        default_type application/octet-stream;

        server {
            listen %d backlog=4096;
            location / {
                client_body_temp_path /tmp/body_temp;
                client_max_body_size 0;
                proxy_pass http://127.0.0.1:%d;
                proxy_redirect off;
            }
        }
    }
    """
    return nginx_conf % (port, proxy_port)


def nginx_temporary_config_file(conf):
    fd, path = tempfile.mkstemp()
    os.write(fd, conf.encode())
    os.close(fd)
    return path


@contextmanager
def nginx_run_in_background(run_cmd):
    proc = subprocess.Popen(run_cmd)
    yield
    proc.terminate()
    proc.wait()


# determine the volume directory path for a given key
def key2path(key):
    bkey = key.encode()
    md5key = hashlib.md5(bkey).digest()
    b64key = base64.b64encode(bkey).decode()
    return '/{:02x}/{:02x}/{:s}'.format(md5key[0], md5key[1], b64key)


# determine which volume a key should be associated with
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
            if int(environ['CONTENT_LENGTH']) == 0:
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

    proxy_port = 8080
    volumes = list(args.volume)

    conf = nginx_index_server_conf(args.port, proxy_port)
    conf_path = nginx_temporary_config_file(conf)
    run_cmd = ['nginx', '-c', conf_path, '-p', '.']

    with nginx_run_in_background(run_cmd):
        with dbm.open(args.index, 'c') as db:
            try:
                app = Application(db, volumes)
                print('PyMKV is listening on :{}'.format(args.port))
                waitress.serve(app, host='127.0.0.1', port=proxy_port)
            except KeyboardInterrupt:
                pass
