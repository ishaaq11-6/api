# Ishaaq AI API (Vercel-safe)

This zip avoids filesystem writes so it won't crash on Vercel with Internal Server Error.

Important:
- Temporary keys and usage stats are stored in memory only.
- On Vercel serverless, memory can reset on cold starts or redeploys.
- For permanent storage, connect a database or Vercel KV later.
