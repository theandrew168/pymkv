import argparse
from contextlib import contextmanager
import dbm
import subprocess

import bjoern

from pymkv import core
from pymkv import nginx


@contextmanager
def background(cmd):
    proc = subprocess.Popen(cmd)
    yield
    proc.terminate()
    proc.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start the pymkv index server')
    parser.add_argument('volume', nargs='+', help='address of a volume server')
    parser.add_argument('--port', type=int, default=3000, help='index server port')
    parser.add_argument('--index', default='/tmp/indexdb', help='path to index database')
    parser.add_argument('--replicas', type=int, default=3, help='number of data replicas')
    parser.add_argument('--subvolumes', type=int, default=10, help='number of data subvolumes')
    args = parser.parse_args()

    volumes = list(args.volume)
    if len(volumes) < args.replicas:
        raise SystemExit('Need at least as many volume servers as replicas')

    proxy_port = 8080
    conf = nginx.index_server_conf(args.port, proxy_port)
    conf_path = nginx.temporary_config_file(conf)
    run_cmd = nginx.run_cmd(conf_path, '.')

    with background(run_cmd):
        with dbm.open(args.index, 'c') as db:
            try:
                app = core.Application(db, volumes, args.replicas, args.subvolumes)
                bjoern.run(app, host='127.0.0.1', port=proxy_port, reuse_port=True)
            except KeyboardInterrupt:
                pass
