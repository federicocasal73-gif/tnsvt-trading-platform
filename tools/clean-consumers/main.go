package main
import (
    "fmt"
    "log"
    "github.com/nats-io/nats.go"
)
func main() {
    nc, err := nats.Connect("nats://localhost:4222")
    if err != nil { log.Fatal(err) }
    defer nc.Close()
    js, err := nc.JetStream()
    if err != nil { log.Fatal(err) }
    consumers := []string{"copy-trading-created","copy-trading-validated","copy-trading-v1-created","copy-trading-v1-validated"}
    for _, c := range consumers {
        err := js.DeleteConsumer("TRADING_SIGNALS", c)
        if err != nil {
            fmt.Printf("Delete %s ERROR: %v\n", c, err)
        } else {
            fmt.Printf("Delete %s OK\n", c)
        }
    }
}
