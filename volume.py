import argparse
import os
import subprocess

from pymkv import nginx


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start a pymkv volume server')
    parser.add_argument('port', type=int, help='volume server port')
    parser.add_argument('path', help='volume server path')
    args = parser.parse_args()

    if not os.path.exists(args.path):
        os.makedirs(args.path)

    conf = nginx.volume_server_conf(args.port, args.path)
    conf_path = nginx.temporary_config_file(conf)
    run_cmd = nginx.run_cmd(conf_path, args.path)

    try:
        subprocess.run(run_cmd)
    except KeyboardInterrupt:
        pass
