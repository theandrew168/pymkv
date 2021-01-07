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
LevelDB (via plyvel) is store this mapping in a fast, persistent way.
The index server also exposes the primary API.
GET gets data, PUT stores data, DELETE deletes data.
Pretty simple!
The index server talks with the volume servers in a similar manner.

## Dependencies
Besides [Python](https://www.python.org), this project also depends on [NGINX](http://nginx.org/) and [LevelDB](https://github.com/google/leveldb).
The following commands can be used install these dependencies on your given platform.
```
# linux, debian-based
sudo apt install python3 nginx libleveldb-dev

# macos
brew install python nginx leveldb
```

## Building
If you are unfamiliar with [virtual environments](https://docs.python.org/3/library/venv.html), I suggest taking a brief moment to learn about them and set one up.
The Python docs provide a great [tutorial](https://docs.python.org/3/tutorial/venv.html) for getting started with virtual environments and packages.

Install the project's dependencies via:
```
pip install wheel
pip install -r requirements.txt
```

## Running
Once the dependencies are installed, the project can be ran by calling `main.py`:
```
python3 main.py
```

## Usage
TODO: coming soon...
