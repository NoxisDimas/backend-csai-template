# Frontend Examples

Koleksi cuplikan kode integrasi ringan dalam JavaScript murni.

## 1. Vanilla JS WebSocket Client

Kerangka sederhana untuk mengatur logika koneksi obrolan di halaman depan situs web.

```javascript
// 1. Dapatkan / Hasilkan Conversation ID
let conversationId = localStorage.getItem("chat_id");
if (!conversationId) {
    conversationId = crypto.randomUUID();
    localStorage.setItem("chat_id", conversationId);
}

// 2. Deklarasikan Koneksi
const wsUrl = `wss://api.domain.com/api/v1/chat/ws/${conversationId}`;
let ws;

function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("Koneksi terbuka. Silakan sapa pengguna.");
        updateUIState('Active');
    };

    ws.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        
        if (payload.type === "typing") {
            showTypingIndicator();
        } else if (payload.type === "escalation") {
            hideTypingIndicator();
            renderSystemBanner("Meminta bantuan staf...");
        } else if (payload.type === "message") {
            hideTypingIndicator();
            renderBubble(payload.sender, payload.text);
        }
    };

    ws.onclose = (e) => {
        console.log("Koneksi tertutup", e.code, e.reason);
        updateUIState('Disconnected');
        
        // Auto-reconnect jika bukan karena ditutup normal
        if (e.code !== 1000) {
            setTimeout(connect, 3000);
        }
    };
}

// Mulai koneksi
connect();

// 3. Mengirim Pesan
function sendMessage(text) {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: "message",
            sender: "customer",
            text: text
        }));
        renderBubble("customer", text);
        updateUIState('Processing');
    }
}
```

---

## 2. React Hook Sederhana (`useChat`)

Jika Anda menggunakan React, pisahkan logika WebSocket ke dalam *custom hook*:

```javascript
import { useEffect, useState, useRef } from 'react';

export function useChat(conversationId) {
  const [messages, setMessages] = useState([]);
  const [isTyping, setIsTyping] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const ws = useRef(null);

  useEffect(() => {
    ws.current = new WebSocket(`wss://api.domain.com/api/v1/chat/ws/${conversationId}`);
    
    ws.current.onopen = () => setIsConnected(true);
    ws.current.onclose = () => setIsConnected(false);
    
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'typing') {
        setIsTyping(true);
      } else if (data.type === 'message') {
        setIsTyping(false);
        setMessages(prev => [...prev, data]);
      }
    };

    return () => {
      ws.current.close(1000);
    };
  }, [conversationId]);

  const sendMessage = (text) => {
    ws.current.send(JSON.stringify({ type: 'message', sender: 'customer', text }));
    setMessages(prev => [...prev, { type: 'message', sender: 'customer', text }]);
  };

  return { messages, isTyping, isConnected, sendMessage };
}
```
