import argparse
import asyncio
import base64
import hashlib
import os
import subprocess
import tempfile
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server

import plyvel


def generate_nginx_conf(port, volume_path):
    nginx_conf = """
    daemon off;
    worker_processes auto;
    pcre_jit on;
    
    pid %s/nginx.pid;
    error_log /dev/stderr;
    
    events {
        multi_accept on;
        accept_mutex off;
        worker_connections 4096;
    }
    
    http {
        access_log /dev/stdout;
    
        sendfile on;
        sendfile_max_chunk 1024k;
    
        tcp_nodelay on;
        tcp_nopush on;

        types_hash_max_size 2048;
    
        server_tokens off;
        default_type application/octet-stream;
    
        server {
            listen %d backlog=4096;
            location / {
                root %s;
    
                client_body_temp_path %s/body_temp;
                client_max_body_size 0;
    
                dav_methods PUT DELETE;
                dav_access group:rw all:r;
                create_full_put_path on;
    
                autoindex on;
                autoindex_format json;
            }
        }
    }
    """
    return nginx_conf % (volume_path, port, volume_path, volume_path)


def generate_nginx_cmd(conf_path, volume_path):
    return ['nginx', '-c', conf_path, '-p', volume_path]


# determine the volume directory path for a given key
def key2path(key):
    bkey = key.encode()
    md5key = hashlib.md5(bkey).digest()
    b64key = base64.b64encode(bkey).decode()
    return '/{:02x}/{:02x}/{:s}'.format(md5key[0], md5key[1], b64key)


# determine which volume(s) keys should be associated with
def key2volume(key, volume_names, replicas, subvolumes):
    bkey = key.encode()

    scores = {}
    for name in volume_names:
        bname = name.encode()
        score = hashlib.md5(bkey + bname).digest()
        scores[score] = name

    sorted_scores = sorted(scores.keys())

    volumes = []
    for i in range(replicas):
        score = sorted_scores[i]
        name = scores[score]
        svhash = (score[12] << 24) + (score[13] << 16) + (score[14] << 8) + score[15]
        volume = '{:s}/sv{:02X}'.format(name, svhash % subvolumes)
        volumes.append(volume)

    return volumes


"""
Volume "servers" store all of the actual data. The data is evenly
dispersed into a predictable nested directory structure based on
the base64'd hash of its contents. Could be text, a file, doesn't
really matter. It is all bytes. This part of the program is just
an NGINX subprocess. The config is generated as needed, thrown into
a tempfile, and started as a child process. NGINX then starts up
its own worker child processes.

The index server manages a mapping of where stuff lives on the volume
servers. LevelDB (via plyvel) is store this mapping in a fast, persistent
way. The index server also exposes the primary API. GET gets data, PUT
stores data, DELETE deletes data. Pretty simple! The index server talks
with the volume servers in a similar manner.
"""

class Application:

    def __init__(self, db, volume_names, replicas, subvolumes):
        self.db = db
        self.volume_names = volume_names
        self.replicas = replicas
        self.subvolumes = subvolumes

    def __call__(self, environ, start_response):
        from pprint import pprint
        pprint(environ)

        method = environ['REQUEST_METHOD']
        key = environ['PATH_INFO']

        status = '200 OK'
        headers = []
        if method == 'GET':
            path = key2path(key)
            volumes = key2volume(key, self.volume_names, self.replicas, self.subvolumes)
            location = 'http://{}{}'.format(volumes[0], path)
            status = '302 Found'
            headers.append(('Location', location))

        start_response(status, headers)
        return [b'']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start pykv master and volume servers')
    parser.add_argument('--volumes', type=int, default=3, help='number of volume server instances')
    parser.add_argument('--replicas', type=int, default=3, help='number of data replicas')
    parser.add_argument('--subvolumes', type=int, default=10, help='number of data subvolumes')
    args = parser.parse_args()

    # start volume instances (they are just NGINX)
    volume_names = []
    volume_procs = []
    for v in range(args.volumes):
        volume_name = 'localhost:{}'.format(3000 + v + 1)
        volume_names.append(volume_name)

        volume_path = '/tmp/volume{}'.format(v + 1)
        volume_port = 3000 + (v + 1)

        # ensure volume data directory exists
        if not os.path.exists(volume_path):
            os.makedirs(volume_path)

        # create nginx config as a temp file
        nginx_conf = generate_nginx_conf(volume_port, volume_path)
        fd, name = tempfile.mkstemp()
        os.write(fd, nginx_conf.encode())
        os.close(fd)

        # start nginx and track its process
        nginx_cmd = generate_nginx_cmd(name, volume_path)
        proc = subprocess.Popen(nginx_cmd, stderr=subprocess.DEVNULL)
        print('starting volume instance: {}'.format(proc.pid))
        volume_procs.append(proc)

    # open a connection to the LevelDB instance
    db = plyvel.DB('/tmp/indexdb', create_if_missing=True)

    # run the main index server til stop
    try:
        app = Application(db, volume_names, args.replicas, args.subvolumes)
        with make_server('', 3000, app) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    # close the LevelDB
    db.close()

    # stop the volume instances
    for proc in volume_procs:
        print('stopping volume instance: {}'.format(proc.pid))
        proc.terminate()
        proc.wait()
