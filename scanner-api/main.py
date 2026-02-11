import os
import json
from datetime import datetime
from typing import Optional

import httpx
import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="DegenScope Scanner API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
ANALYZER_URL = os.getenv("ANALYZER_URL", "http://analyzer:8001")
GOPLUS_API = "https://api.gopluslabs.io/api/v1"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"

db_pool: Optional[asyncpg.Pool] = None
redis_client = None

@app.on_event("startup")
async def startup():
    global db_pool, redis_client
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

@app.on_event("shutdown")
async def shutdown():
    if db_pool: await db_pool.close()
    if redis_client: await redis_client.close()

class AnalyzeRequest(BaseModel):
    contract_address: str
    chain: str = "ethereum"

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/analyze")
async def analyze_token(req: AnalyzeRequest):
    address = req.contract_address.lower().strip()
    chain = req.chain.lower()

    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(400, "Indirizzo contratto non valido")

    cache_key = f"analysis:{chain}:{address}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    chain_id_map = {"ethereum": "1", "bsc": "56", "polygon": "137", "base": "8453"}
    chain_id = chain_id_map.get(chain, "1")

    async with httpx.AsyncClient(timeout=15.0) as client:
        goplus_data, dex_data, analyzer_data = {}, {}, {}
        try:
            r = await client.get(f"{GOPLUS_API}/token_security/{chain_id}?contract_addresses={address}")
            gp = r.json()
            goplus_data = gp.get("result", {}).get(address, {})
        except Exception: pass

        try:
            r = await client.get(f"{DEXSCREENER_API}/tokens/{address}")
            dx = r.json()
            pairs = dx.get("pairs", [])
            if pairs:
                dex_data = max(pairs, key=lambda x: x.get("liquidity", {}).get("usd", 0) or 0)
        except Exception: pass

        try:
            r = await client.post(f"{ANALYZER_URL}/analyze", json={"address": address, "chain": chain})
            analyzer_data = r.json()
        except Exception: pass

    risk = _calculate_risk(goplus_data, dex_data, analyzer_data)

    result = {
        "contract_address": address,
        "chain": chain,
        "risk_score": risk["score"],
        "risk_level": risk["level"],
        "contract_name": dex_data.get("baseToken", {}).get("name", "Unknown"),
        "symbol": dex_data.get("baseToken", {}).get("symbol", "???"),
        "price_usd": dex_data.get("priceUsd"),
        "liquidity_usd": dex_data.get("liquidity", {}).get("usd"),
        "volume_24h": dex_data.get("volume", {}).get("h24"),
        "flags": risk["flags"],
        "details": {
            "market_data": {
                "dex_id": dex_data.get("dexId"),
                "price_change_24h": dex_data.get("priceChange", {}).get("h24"),
                "fdv": dex_data.get("fdv"),
            },
            "on_chain": analyzer_data,
        },
        "analyzed_at": datetime.utcnow().isoformat(),
    }

    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO analyses (contract_address, chain, risk_score, risk_level, contract_name, symbol, analysis_data) VALUES ($1,$2,$3,$4,$5,$6,$7)",
                address, chain, risk["score"], risk["level"],
                result["contract_name"], result["symbol"], json.dumps(result)
            )
    except Exception: pass

    await redis_client.setex(cache_key, 86400, json.dumps(result))
    return result

def _calculate_risk(goplus, dex, analyzer):
    score = 0
    flags = []

    if goplus:
        if goplus.get("is_honeypot") == "1":
            score += 40; flags.append({"type": "critical", "msg": "⛔ HONEYPOT — impossibile vendere"})
        if goplus.get("is_open_source") == "0":
            score += 20; flags.append({"type": "high", "msg": "🔴 Codice sorgente non verificato"})
        if goplus.get("can_take_back_ownership") == "1":
            score += 15; flags.append({"type": "high", "msg": "🔴 Owner può riprendere la ownership"})
        if goplus.get("owner_change_balance") == "1":
            score += 20; flags.append({"type": "critical", "msg": "⛔ Owner può modificare i balance"})
        if goplus.get("hidden_owner") == "1":
            score += 15; flags.append({"type": "high", "msg": "🔴 Owner nascosto nel contratto"})
        if goplus.get("selfdestruct") == "1":
            score += 15; flags.append({"type": "high", "msg": "🔴 Funzione selfdestruct presente"})
        if goplus.get("is_blacklisted") == "1":
            score += 10; flags.append({"type": "medium", "msg": "🟡 Funzione blacklist presente"})
        if goplus.get("is_mintable") == "1":
            score += 10; flags.append({"type": "medium", "msg": "🟡 Il token è mintabile"})
        try:
            sell_tax = float(goplus.get("sell_tax", 0))
            buy_tax = float(goplus.get("buy_tax", 0))
            if sell_tax > 0.10:
                score += 15; flags.append({"type": "high", "msg": f"🔴 Sell tax alta: {sell_tax*100:.1f}%"})
            elif sell_tax > 0.05:
                score += 5; flags.append({"type": "medium", "msg": f"🟡 Sell tax: {sell_tax*100:.1f}%"})
            if buy_tax > 0.10:
                score += 10; flags.append({"type": "medium", "msg": f"🟡 Buy tax alta: {buy_tax*100:.1f}%"})
        except: pass
        holder_count = int(goplus.get("holder_count", 999))
        if holder_count < 100:
            score += 10; flags.append({"type": "medium", "msg": f"🟡 Pochissimi holder: {holder_count}"})

    if dex:
        liquidity = (dex.get("liquidity") or {}).get("usd", 0) or 0
        if liquidity < 10000:
            score += 15; flags.append({"type": "high", "msg": f"🔴 Liquidità molto bassa: ${liquidity:,.0f}"})
        elif liquidity < 50000:
            score += 5; flags.append({"type": "medium", "msg": f"🟡 Liquidità bassa: ${liquidity:,.0f}"})

    if analyzer and analyzer.get("concentrated_wallets"):
        score += 10; flags.append({"type": "high", "msg": f"🔴 Top 10 wallet detengono {analyzer.get('top10_pct', '?')}% del supply"})

    score = min(score, 100)
    if score >= 70: level = "DANGER"
    elif score >= 40: level = "RISKY"
    elif score >= 20: level = "MODERATE"
    else: level = "SAFE"

    return {"score": score, "level": level, "flags": flags}

@app.get("/api/history")
async def get_history(limit: int = 20):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT contract_address, chain, risk_score, risk_level, contract_name, symbol, created_at FROM analyses ORDER BY created_at DESC LIMIT $1", limit
        )
    return [dict(r) for r in rows]
