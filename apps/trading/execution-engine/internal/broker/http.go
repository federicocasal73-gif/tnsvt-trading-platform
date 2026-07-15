package broker

import (
	"bytes"
	"encoding/json"
	"io"
)

// jsonReader implementación simple de io.Reader que serializa JSON on read
type jsonReader struct {
	data []byte
	pos  int
}

func newJSONReader(v any) *jsonReader {
	data, _ := json.Marshal(v)
	return &jsonReader{data: data}
}

func (r *jsonReader) Read(p []byte) (int, error) {
	if r.pos >= len(r.data) {
		return 0, io.EOF
	}
	n := copy(p, r.data[r.pos:])
	r.pos += n
	return n, nil
}

func readAll(r io.Reader) ([]byte, error) {
	buf := new(bytes.Buffer)
	_, err := io.Copy(buf, r)
	return buf.Bytes(), err
}