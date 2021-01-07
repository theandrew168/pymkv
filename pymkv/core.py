import base64
import hashlib


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


class Application:

    def __init__(self, db, volumes, replica_count, subvolume_count):
        self.db = db
        self.volumes = volumes
        self.replica_count = replica_count
        self.subvolume_count = subvolume_count

    def __call__(self, environ, start_response):
        method = environ['REQUEST_METHOD']
        key = environ['PATH_INFO']

        headers = []
        if method == 'GET':
            if key not in self.db:
                start_response('404 Not Found', headers)
                return [b'']
            path = key2path(key)
            volumes = key2volume(key, self.volumes, self.replica_count, self.subvolume_count)

            location = 'http://{}{}'.format(volumes[0], path)
            headers.append(('Location', location))

            start_response('302 Found', headers)
            return [b'']
        else:
            start_response('405 Method Not Allowed', headers)
            return [b'']
