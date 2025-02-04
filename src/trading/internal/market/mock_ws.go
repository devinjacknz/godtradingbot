package market

import (
	"net/http"
	"net/http/httptest"

	"github.com/gorilla/websocket"
)

// MockWebSocketServer creates a test WebSocket server
func MockWebSocketServer() (*httptest.Server, string) {
	upgrader := websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()

		// Keep connection open until context is cancelled
		<-r.Context().Done()
	}))

	// Convert http to ws
	return server, "ws" + server.URL[4:]
}

// MockWebSocketClient creates a test WebSocket client
func MockWebSocketClient(url string) (*websocket.Conn, error) {
	conn, _, err := websocket.DefaultDialer.Dial(url, nil)
	if err != nil {
		return nil, err
	}
	return conn, nil
}
