import argparse
import os
import subprocess
import tempfile


def nginx_volume_server_conf(port, path):
    nginx_conf = """
    daemon off;
    worker_processes auto;
    pcre_jit on;

    pid %s/nginx_volume.pid;
    error_log /dev/stderr;

    events {
        multi_accept on;
        accept_mutex off;
        worker_connections 4096;
    }

    http {
        access_log off;

        sendfile on;
        sendfile_max_chunk 1024k;

        tcp_nodelay on;
        tcp_nopush on;

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
    return nginx_conf % (path, path, port, path)


def nginx_temporary_config_file(conf):
    fd, path = tempfile.mkstemp()
    os.write(fd, conf.encode())
    os.close(fd)
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Start a pymkv volume server')
    parser.add_argument('port', type=int, help='volume server port')
    parser.add_argument('path', help='volume server path')
    args = parser.parse_args()

    if not os.path.exists(args.path):
        os.makedirs(args.path)

    conf = nginx_volume_server_conf(args.port, args.path)
    conf_path = nginx_temporary_config_file(conf)
    run_cmd = ['nginx', '-c', conf_path, '-p', args.path]

    try:
        subprocess.run(run_cmd)
    except KeyboardInterrupt:
        pass
