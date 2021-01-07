import os
import tempfile


def volume_server_conf(port, path):
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
        #access_log /dev/stdout;
        access_log off;

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
    return nginx_conf % (path, port, path, path)


def index_server_conf(port, proxy_port):
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
        #access_log /dev/stdout;
        access_log off;

        tcp_nodelay on;
        tcp_nopush on;

        server_tokens off;
        default_type application/octet-stream;

        server {
            listen %d backlog=4096;
            location / {
                proxy_pass http://127.0.0.1:%d;
                proxy_redirect off;
            }
        }
    }
    """
    return nginx_conf % (port, proxy_port)


def temporary_config_file(conf):
    # write NGINX config out to a temp file and return its path
    fd, path = tempfile.mkstemp()
    os.write(fd, conf.encode())
    os.close(fd)
    return path


def run_cmd(conf_path, prefix):
    return ['nginx', '-c', conf_path, '-p', prefix]
