# Ishaaq AI API (Vercel-safe)

This package avoids filesystem writes so it will not crash on Vercel with Internal Server Error.

Important:
- Temporary keys and daily usage are kept in memory only.
- On Vercel serverless, memory is not durable across cold starts or redeploys.
- To make keys and stats permanent, connect a real storage layer such as Vercel KV, Redis, Supabase, or MongoDB.

Files:
- app.py
- requirements.txt
- vercel.json
