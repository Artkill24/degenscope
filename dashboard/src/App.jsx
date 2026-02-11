import { useState, useEffect } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";
const RISK = {
  SAFE:     { color: "#22c55e", bg: "#052e16", label: "SICURO" },
  MODERATE: { color: "#f59e0b", bg: "#1c1002", label: "MODERATO" },
  RISKY:    { color: "#f97316", bg: "#1c0a02", label: "RISCHIOSO" },
  DANGER:   { color: "#ef4444", bg: "#1c0202", label: "PERICOLO" },
};
const FLAG_COLORS = { critical: "#ef4444", high: "#f97316", medium: "#f59e0b" };

export default function App() {
  const [address, setAddress] = useState("");
  const [chain, setChain] = useState("ethereum");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => { fetchHistory(); }, []);

  async function fetchHistory() {
    try {
      const res = await fetch(`${API_URL}/api/history?limit=10`);
      setHistory(await res.json());
    } catch {}
  }

  async function analyze() {
    if (!address.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch(`${API_URL}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contract_address: address.trim(), chain }),
      });
      if (!res.ok) throw new Error("Errore durante l'analisi");
      const data = await res.json();
      setResult(data);
      fetchHistory();
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  const risk = result ? RISK[result.risk_level] || RISK.MODERATE : null;

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a0f", color: "#e2e8f0", fontFamily: "monospace" }}>
      <div style={{ borderBottom: "1px solid #1e293b", padding: "20px 32px", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 24 }}>🔍</span>
        <span style={{ fontSize: 20, fontWeight: 700, color: "#a78bfa" }}>DegenScope</span>
        <span style={{ fontSize: 12, color: "#64748b", marginLeft: 8 }}>Token Intelligence Terminal</span>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 20px" }}>
        <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 24, marginBottom: 32 }}>
          <div style={{ fontSize: 13, color: "#64748b", marginBottom: 12, letterSpacing: 1 }}>ANALIZZA TOKEN</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <input value={address} onChange={e => setAddress(e.target.value)} onKeyDown={e => e.key === "Enter" && analyze()}
              placeholder="0x... indirizzo contratto"
              style={{ flex: 1, minWidth: 280, background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "12px 16px", color: "#e2e8f0", fontSize: 14, outline: "none", fontFamily: "monospace" }} />
            <select value={chain} onChange={e => setChain(e.target.value)}
              style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, padding: "12px 16px", color: "#e2e8f0", fontSize: 13, cursor: "pointer" }}>
              <option value="ethereum">Ethereum</option>
              <option value="bsc">BSC</option>
              <option value="polygon">Polygon</option>
              <option value="base">Base</option>
            </select>
            <button onClick={analyze} disabled={loading}
              style={{ background: loading ? "#312e81" : "#6d28d9", color: "white", border: "none", borderRadius: 8, padding: "12px 24px", fontSize: 14, fontWeight: 600, cursor: loading ? "wait" : "pointer", fontFamily: "monospace" }}>
              {loading ? "Scansione..." : "SCANSIONA"}
            </button>
          </div>
          {error && <div style={{ marginTop: 12, color: "#ef4444", fontSize: 13 }}>⚠ {error}</div>}
        </div>

        {result && risk && (
          <div style={{ background: "#0f172a", border: `1px solid ${risk.color}33`, borderRadius: 12, padding: 24, marginBottom: 32 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16, marginBottom: 24 }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>{result.contract_name} <span style={{ color: "#64748b", fontSize: 16 }}>${result.symbol}</span></div>
                <div style={{ fontSize: 12, color: "#475569", marginTop: 4, wordBreak: "break-all" }}>{result.contract_address}</div>
              </div>
              <div style={{ background: risk.bg, border: `2px solid ${risk.color}`, borderRadius: 12, padding: "16px 24px", textAlign: "center", minWidth: 120 }}>
                <div style={{ fontSize: 36, fontWeight: 700, color: risk.color, lineHeight: 1 }}>{result.risk_score}</div>
                <div style={{ fontSize: 12, color: risk.color, marginTop: 4, letterSpacing: 2 }}>{risk.label}</div>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12, marginBottom: 24 }}>
              {[
                { label: "Prezzo", value: result.price_usd ? `$${parseFloat(result.price_usd).toFixed(8)}` : "N/A" },
                { label: "Liquidità", value: result.liquidity_usd ? `$${(result.liquidity_usd/1000).toFixed(1)}K` : "N/A" },
                { label: "Volume 24h", value: result.volume_24h ? `$${(result.volume_24h/1000).toFixed(1)}K` : "N/A" },
                { label: "DEX", value: result.details?.market_data?.dex_id || "N/A" },
              ].map(stat => (
                <div key={stat.label} style={{ background: "#1e293b", borderRadius: 8, padding: "12px 16px" }}>
                  <div style={{ fontSize: 11, color: "#64748b", marginBottom: 4 }}>{stat.label}</div>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>{stat.value}</div>
                </div>
              ))}
            </div>

            {result.flags?.length > 0 ? (
              <div>
                <div style={{ fontSize: 12, color: "#64748b", marginBottom: 10, letterSpacing: 1 }}>FLAGS RILEVATI</div>
                {result.flags.map((flag, i) => (
                  <div key={i} style={{ background: `${FLAG_COLORS[flag.type]}11`, border: `1px solid ${FLAG_COLORS[flag.type]}44`, borderRadius: 8, padding: "10px 14px", color: FLAG_COLORS[flag.type], fontSize: 13, marginBottom: 8 }}>
                    {flag.msg}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: "#22c55e", fontSize: 14, padding: 12, background: "#052e1622", borderRadius: 8, border: "1px solid #22c55e33" }}>
                ✅ Nessun flag critico — usa comunque il buon senso
              </div>
            )}
          </div>
        )}

        {history.length > 0 && (
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 24 }}>
            <div style={{ fontSize: 12, color: "#64748b", marginBottom: 16, letterSpacing: 1 }}>SCANSIONI RECENTI</div>
            {history.map((h, i) => {
              const rc = RISK[h.risk_level] || RISK.MODERATE;
              return (
                <div key={i} onClick={() => setAddress(h.contract_address)}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", background: "#1e293b", borderRadius: 8, cursor: "pointer", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <span style={{ fontWeight: 600 }}>{h.symbol || "???"}</span>
                    <span style={{ color: "#475569", fontSize: 12, marginLeft: 8 }}>{h.contract_address.slice(0, 12)}...</span>
                  </div>
                  <div style={{ color: rc.color, fontSize: 13, fontWeight: 600 }}>{h.risk_score}/100 — {rc.label}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
