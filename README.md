# pymkv
Exploring George Hotz's [minikeyvalue](https://github.com/geohot/minikeyvalue) design in Python.
Overall, I think George's implementation (and language choice) is better.
Sure, my Python version can match his when it comes to performance and throughput but it takes an extra reverse proxy layer (more NGINX) to get there.
Go really is a powerhouse when it comes to high-performance network-based applications and it shows.

## Design
Volume "servers" store all of the actual data.
The data is evenly distributed into a predictable nested directory structure based on the base64'd hash of its contents.
Could be text, a file, doesn't really matter.
It's all bytes.
This part of the program is just an NGINX subprocess.
The config is generated as needed, thrown into a tempfile, and started as a child process.
NGINX then starts up its own worker child processes.

The index server manages a mapping of where stuff lives on the volume servers.
A [DBM database](https://docs.python.org/3/library/dbm.html) is used to store this mapping in a fast, persistent way.
The index server also exposes the primary API.
GET gets data, PUT stores data, DELETE deletes data.
Pretty simple!
The index server talks with the volume servers in a similar manner.

## System Dependencies
Besides [Python](https://www.python.org), this project also depends on having [NGINX](http://nginx.org/) installed.
```
# linux, debian-based
sudo apt install nginx

# macos
brew install nginx
```

## Python Dependencies
If you are unfamiliar with [virtual environments](https://docs.python.org/3/library/venv.html), I suggest taking a brief moment to learn about them and set one up.
The Python docs provide a great [tutorial](https://docs.python.org/3/tutorial/venv.html) for getting started with virtual environments and packages.

Install the project's Python dependencies via:
```
pip install -r requirements.txt
```

## Running
First start one or more volume servers (these could run on different systems):
```
# ignore the nginx "could not open error log" warnings
python3 volume.py 3001 /tmp/volume1/ &
python3 volume.py 3002 /tmp/volume2/ &
python3 volume.py 3003 /tmp/volume3/ &
```

Then start the index server using the addresses of the volume servers:
```
python3 index.py localhost:3001 localhost:3002 localhost:3003
```

## Usage
With the index server running on port 3000, the following commands demonstrate core functionality:
```
# put "bigswag" in key "wehave"
curl -v -L -X PUT -d bigswag http://localhost:3000/wehave

# get key "wehave" (should be "bigswag")
curl -v -L -X GET http://localhost:3000/wehave

# delete key "wehave"
curl -v -L -X DELETE http://localhost:3000/wehave

# put file in key "file.txt"
curl -v -L -X PUT -T /path/to/local/file.txt http://localhost:3000/file.txt

# get file in key "file.txt"
curl -v -L -X GET -o /path/to/local/file.txt http://localhost:3000/file.txt
```

## Performance
All of these benchmarks were executed against a small cluster (1 index, 3 volumes) of Digital Ocean droplets (1vCPU, 512MB, $5/month).

| **Benchmark** | **Command** |
| --- | --- |
| **fetch missing** | `hey -c 100 -z 10s http://<index_server_ip>:3000/missing` |
| **fetch present** | `hey -c 100 -z 10s http://<index_server_ip>:3000/present` |
| **thrasher.go** | `go run extras/thrasher.go -addr <index_server_ip>:3000` |

Each of these results are the average of three trials and are measured in requests per second.

| **Benchmark** | **[pymkv](https://github.com/theandrew168/pymkv)** | **[minikeyvalue](https://github.com/geohot/minikeyvalue)** |
| --- | --- | --- |
| **fetch missing** | 1397 | 2152 |
| **fetch present** | 1012 | 941 |
| **thrasher.go** | 99 | 102 |
