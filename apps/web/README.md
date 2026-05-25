# web

Next.js 15 App Router frontend. Uses **bun** for installation and runtime.

```bash
bun install
NEXT_PUBLIC_CHAT_API_URL=http://localhost:8000 bun run dev
```

Pages:
- `/` — new chat (creates a conversation on first send)
- `/c/[id]` — chat view with full message history (**resume**)
- `/conversations` — list all conversations

The streaming chat reads SSE frames from `POST /chat`. **Cancel** calls
`POST /conversations/:id/cancel` (which sets a Redis flag the backend reads
between tokens) and aborts the local `fetch` controller so the UI stops
immediately.
