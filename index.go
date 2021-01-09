package main

import (
	"bytes"
	"crypto/md5"
	"encoding/base64"
	"flag"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/syndtr/goleveldb/leveldb"
)

// determine the volume directory path for a given key
func key2path(key []byte) string {
	md5key := md5.Sum(key)
	b64key := base64.StdEncoding.EncodeToString(key)
	return fmt.Sprintf("/%02x/%02x/%s", md5key[0], md5key[1], b64key)
}

// determine which volume a key should be associated with
func key2volume(key []byte, volumes []string) string {
	var best_score []byte
	var best_volume string
	for _, volume := range volumes {
		hash := md5.New()
		hash.Write([]byte(volume))
		hash.Write(key)
		score := hash.Sum(nil)
		if best_score == nil || bytes.Compare(score, best_score) == 1 {
			best_score = score
			best_volume = volume
		}
	}
	return best_volume
}

type Application struct {
	db      *leveldb.DB
	volumes []string
}

func (app *Application) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	key := []byte(r.URL.Path)

	switch r.Method {
	case "GET", "HEAD":
		// reject invalid keys
		volume, err := app.db.Get(key, nil)
		if err != nil {
			if err == leveldb.ErrNotFound {
				w.WriteHeader(404)
				return
			} else {
				w.WriteHeader(500)
				return
			}
		}

		// determine where this KV pair lives
		path := key2path(key)
		remote := fmt.Sprintf("http://%s%s", volume, path)

		// redirect to the value's location
		w.Header().Set("Location", remote)
		w.WriteHeader(302)
		return
	case "PUT":
		// reject empty values
		if r.ContentLength == 0 {
			w.WriteHeader(411)
			return
		}

		// reject duplicate keys
		exists, err := app.db.Has(key, nil)
		if err != nil {
			w.WriteHeader(500)
			return
		}
		if exists {
			w.WriteHeader(409)
			return
		}

		// determine where this KV pair will live
		path := key2path(key)
		volume := key2volume(key, app.volumes)
		remote := fmt.Sprintf("http://%s%s", volume, path)

		// call out to the volume server
		req, err := http.NewRequest("PUT", remote, r.Body)
		if err != nil {
			w.WriteHeader(500)
			return
		}
		req.ContentLength = r.ContentLength
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			w.WriteHeader(500)
			return
		}
		if resp.StatusCode != 201 && resp.StatusCode != 204 {
			w.WriteHeader(500)
			return
		}

		// store the KV location into the index
		err = app.db.Put(key, []byte(volume), nil)
		if err != nil {
			w.WriteHeader(500)
			return
		}

		w.WriteHeader(201)
		return
	case "DELETE":
		// reject invalid keys
		volume, err := app.db.Get(key, nil)
		if err != nil {
			if err == leveldb.ErrNotFound {
				w.WriteHeader(404)
				return
			} else {
				w.WriteHeader(500)
				return
			}
		}

		// determine where this KV pair lives
		path := key2path(key)
		remote := fmt.Sprintf("http://%s%s", volume, path)

		// delete the pair from the index
		err = app.db.Delete(key, nil)
		if err != nil {
			w.WriteHeader(500)
			return
		}

		// delete the pair from its volume server
		req, err := http.NewRequest("DELETE", remote, nil)
		if err != nil {
			w.WriteHeader(500)
			return
		}
		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			w.WriteHeader(500)
			return
		}
		if resp.StatusCode != 204 {
			w.WriteHeader(500)
			return
		}

		w.WriteHeader(204)
		return
	default:
		w.WriteHeader(405)
		return
	}
}

func main() {
	addr := flag.String("addr", "0.0.0.0:3000", "index server listen address")
	index := flag.String("index", "/tmp/indexdb/", "index database path")
	volumes := flag.String("volumes", "", "comma-delimited list of volume server addresses")
	flag.Parse()

	if len(*volumes) == 0 {
		log.Fatal("Need at least one volume server!")
	}

	db, err := leveldb.OpenFile(*index, nil)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	app := &Application{
		db:      db,
		volumes: strings.Split(*volumes, ","),
	}

	fmt.Printf("Listening on %s\n", *addr)
	log.Fatal(http.ListenAndServe(*addr, app))
}
