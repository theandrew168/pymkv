# pymkv
Exploring George Hotz's [minikeyvalue](https://github.com/geohot/minikeyvalue) design in Python.

Volume "servers" store all of the actual data.
The data is evenly distributed into a predictable nested directory structure based on the base64'd hash of its contents.
Could be text, a file, doesn't really matter.
It is all bytes.
This part of the program is just an NGINX subprocess.
The config is generated as needed, thrown into a tempfile, and started as a child process.
NGINX then starts up its own worker child processes.

The index server manages a mapping of where stuff lives on the volume servers.
A [DBM database](https://docs.python.org/3/library/dbm.html) is used to store this mapping in a fast, persistent way.
The index server also exposes the primary API.
GET gets data, PUT stores data, DELETE deletes data.
Pretty simple!
The index server talks with the volume servers in a similar manner.

## Dependencies
Besides [Python](https://www.python.org), this project also depends on having [NGINX](http://nginx.org/) installed.
```
# linux, debian-based
sudo apt install nginx

# macos
brew install nginx
```

## Usage
The index and volume servers can be started by running:
```
python3 main.py
```

TODO What now? How do I use this thing?
