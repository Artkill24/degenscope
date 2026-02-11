import os
from fastapi import FastAPI
from pydantic import BaseModel
import httpx

app = FastAPI(title="DegenScope Analyzer", version="1.0.0")
GOPLUS_API = "https://api.gopluslabs.io/api/v1"

class AnalyzeRequest(BaseModel):
    address: str
    chain: str = "ethereum"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    address = req.address.lower()
    chain_id_map = {"ethereum": "1", "bsc": "56", "polygon": "137", "base": "8453"}
    chain_id = chain_id_map.get(req.chain, "1")

    result = {"concentrated_wallets": False, "top10_pct": None, "locked_liquidity_pct": 0, "suspicious_patterns": []}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{GOPLUS_API}/token_security/{chain_id}?contract_addresses={address}")
            data = resp.json()
            token_data = data.get("result", {}).get(address, {})

            holders = token_data.get("holders", [])
            if holders:
                top10_total = sum(float(h.get("percent", 0)) for h in holders[:10])
                result["top10_pct"] = round(top10_total * 100, 2)
                result["concentrated_wallets"] = top10_total > 0.50
                suspicious = [h for h in holders[:10] if not h.get("is_contract") and not h.get("is_locked") and float(h.get("percent", 0)) > 0.05]
                if len(suspicious) >= 3:
                    result["suspicious_patterns"].append("multiple_large_wallets")

            lp_holders = token_data.get("lp_holders", [])
            locked_lp = sum(float(lp.get("percent", 0)) for lp in lp_holders if lp.get("is_locked"))
            result["locked_liquidity_pct"] = round(locked_lp * 100, 2)
            if locked_lp < 0.80 and lp_holders:
                result["suspicious_patterns"].append("low_locked_liquidity")
    except Exception as e:
        result["error"] = str(e)

    return result
