import React, { useState, useEffect, useCallback } from 'react';
import { getGenLayerClient } from './lib/client';
import { connectWallet } from './lib/wallet';
import { PACTGUARD_CONTRACT } from './lib/addresses';
import {
  Gavel,
  ExternalLink,
  PlusCircle,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Server,
  Scale,
  Clock,
} from 'lucide-react';

interface Program {
  program_id: string;
  provider: string;
  service_name: string;
  sla_terms_url: string;
  uptime_target_bp: number;
  bond: string;
  active: boolean;
}

interface Claim {
  claim_id: string;
  claimant: string;
  program_id: string;
  incident_window: string;
  description: string;
  evidence_urls: string[];
  claim_bond: string;
  state: string;
  verdict: string;
  severity: string;
  credit_bp: number;
  confidence: number;
  reason: string;
  challenge_deadline: number;
  challenger: string;
  challenge_bond: string;
  rebuttal_url: string;
  challenged_once: boolean;
  payout_done: boolean;
}

const EXPLORER = 'https://genlayer-explorer.vercel.app';
const toGen = (wei: string | number) => (Number(wei) / 1e18).toFixed(3);
const toPct = (bp: number) => (bp / 100).toFixed(2);
const short = (a: string) => (a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '—');
const nowSec = () => Math.floor(Date.now() / 1000);

const STATE_STYLES: Record<string, string> = {
  OPEN: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  UPHELD: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  REJECTED: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  CHALLENGED: 'bg-purple-500/10 text-purple-400 border-purple-500/20 animate-pulse',
  SETTLED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
};

export default function App() {
  const [account, setAccount] = useState<string | null>(null);
  const [balance, setBalance] = useState('0');
  const [tab, setTab] = useState<'programs' | 'claims' | 'detail' | 'about'>('programs');
  const [programs, setPrograms] = useState<Program[]>([]);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [filter, setFilter] = useState('ALL');
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [claim, setClaim] = useState<Claim | null>(null);
  const [program, setProgram] = useState<Program | null>(null);
  const [busy, setBusy] = useState(false);
  const [waitMsg, setWaitMsg] = useState('');
  const [txHash, setTxHash] = useState<string | null>(null);

  const [showRegister, setShowRegister] = useState(false);
  const [showFile, setShowFile] = useState(false);
  const [showChallenge, setShowChallenge] = useState(false);

  // register form
  const [rName, setRName] = useState('');
  const [rUrl, setRUrl] = useState('https://');
  const [rUptime, setRUptime] = useState('99.90');
  const [rBond, setRBond] = useState('0.5');
  // file-claim form
  const [fProgram, setFProgram] = useState('');
  const [fWindow, setFWindow] = useState('');
  const [fDesc, setFDesc] = useState('');
  const [fUrls, setFUrls] = useState('');
  const [fBond, setFBond] = useState('0.1');
  // challenge form
  const [cUrl, setCUrl] = useState('https://');
  const [cNote, setCNote] = useState('');

  const handleConnect = async () => {
    try {
      setBusy(true);
      const addr = await connectWallet();
      setAccount(addr);
      fetchBalance(addr);
    } catch (e: any) {
      alert(e.message || 'Connection failed');
    } finally {
      setBusy(false);
    }
  };

  const fetchBalance = async (addr: string) => {
    try {
      if (window.ethereum) {
        const res: any = await window.ethereum.request({ method: 'eth_getBalance', params: [addr, 'latest'] });
        if (res) setBalance((Number(BigInt(res)) / 1e18).toFixed(3));
      }
    } catch { /* ignore */ }
  };

  const fetchPrograms = useCallback(async () => {
    try {
      const raw: any = await getGenLayerClient().readContract({
        address: PACTGUARD_CONTRACT, functionName: 'list_programs', args: [0, 100],
      });
      if (raw) setPrograms(typeof raw === 'string' ? JSON.parse(raw) : raw);
    } catch (e) { console.error('programs', e); }
  }, []);

  const fetchClaims = useCallback(async () => {
    try {
      const raw: any = await getGenLayerClient().readContract({
        address: PACTGUARD_CONTRACT, functionName: 'list_claims', args: [filter, 0, 100],
      });
      if (raw) setClaims(typeof raw === 'string' ? JSON.parse(raw) : raw);
    } catch (e) { console.error('claims', e); }
  }, [filter]);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      setBusy(true);
      const raw: any = await getGenLayerClient().readContract({
        address: PACTGUARD_CONTRACT, functionName: 'get_claim', args: [id],
      });
      const c: Claim = typeof raw === 'string' ? JSON.parse(raw) : raw;
      setClaim(c);
      const praw: any = await getGenLayerClient().readContract({
        address: PACTGUARD_CONTRACT, functionName: 'get_program', args: [c.program_id],
      });
      setProgram(typeof praw === 'string' ? JSON.parse(praw) : praw);
    } catch (e) { console.error('detail', e); } finally { setBusy(false); }
  }, []);

  useEffect(() => { fetchPrograms(); }, [fetchPrograms]);
  useEffect(() => { if (tab === 'claims') fetchClaims(); }, [tab, fetchClaims]);
  useEffect(() => { if (tab === 'detail' && selectedClaimId) fetchDetail(selectedClaimId); }, [tab, selectedClaimId, fetchDetail]);

  const runWrite = async (functionName: string, args: any[], value: bigint, msg: string) => {
    if (!account) { alert('Connect your MetaMask wallet first'); return false; }
    try {
      setBusy(true); setWaitMsg(msg); setTxHash(null);
      const client = getGenLayerClient(account as `0x${string}`);
      const tx = await client.writeContract({ address: PACTGUARD_CONTRACT, functionName, args, value });
      setTxHash(tx as string);
      await (client as any).waitForTransactionReceipt({ hash: tx as any });
      fetchBalance(account);
      return true;
    } catch (e: any) {
      alert('Transaction error: ' + (e.shortMessage || e.message || String(e)));
      return false;
    } finally { setBusy(false); setWaitMsg(''); }
  };

  const doRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    const bp = Math.round(Number(rUptime) * 100);
    const bond = BigInt(Math.round(Number(rBond) * 1e18));
    const ok = await runWrite('register_program', [rName, rUrl, bp], bond, 'Registering SLA program & locking provider bond...');
    if (ok) { setShowRegister(false); setRName(''); setRUrl('https://'); fetchPrograms(); }
  };

  const doFile = async (e: React.FormEvent) => {
    e.preventDefault();
    const urls = fUrls.split('\n').map((u) => u.trim()).filter(Boolean).slice(0, 3);
    if (urls.length === 0) { alert('Add at least one evidence URL'); return; }
    const bond = BigInt(Math.round(Number(fBond) * 1e18));
    const ok = await runWrite('file_claim', [fProgram, fWindow, fDesc, urls], bond, 'Filing bonded breach claim...');
    if (ok) { setShowFile(false); setFWindow(''); setFDesc(''); setFUrls(''); setTab('claims'); fetchClaims(); }
  };

  const doTriage = async (id: string) => {
    const ok = await runWrite('triage', [id], 0n, 'AI jury reading SLA terms + status pages on-chain and reaching consensus...');
    if (ok) fetchDetail(id);
  };
  const doRetriage = async (id: string) => {
    const ok = await runWrite('retriage', [id], 0n, 'Re-adjudicating with the challenger rebuttal (final)...');
    if (ok) fetchDetail(id);
  };
  const doSettle = async (id: string) => {
    const ok = await runWrite('settle', [id], 0n, 'Executing on-chain settlement payout...');
    if (ok) fetchDetail(id);
  };
  const doChallenge = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!claim) return;
    const bond = BigInt(claim.claim_bond);
    const ok = await runWrite('challenge', [claim.claim_id, cUrl, cNote], bond, 'Posting bonded challenge...');
    if (ok) { setShowChallenge(false); setCNote(''); setCUrl('https://'); fetchDetail(claim.claim_id); }
  };

  // role helpers for the detail view
  const isProvider = claim && program && account && account.toLowerCase() === program.provider.toLowerCase();
  const isClaimant = claim && account && account.toLowerCase() === claim.claimant.toLowerCase();
  const windowOpen = claim && (claim.challenge_deadline === 0 || nowSec() < claim.challenge_deadline);
  const canChallenge = claim && !claim.challenged_once && windowOpen &&
    ((claim.state === 'UPHELD' && isProvider) || (claim.state === 'REJECTED' && isClaimant));
  const canSettle = claim && ['UPHELD', 'REJECTED'].includes(claim.state) && !claim.payout_done &&
    (claim.challenge_deadline === 0 || nowSec() >= claim.challenge_deadline);

  return (
    <div className="min-h-screen flex flex-col bg-[#070B14] text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#0B0F19]/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setTab('programs')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-sky-500/20">🛡️</div>
            <div>
              <div className="font-bold text-lg tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">PactGuard</div>
              <div className="text-[10px] text-sky-400 font-medium tracking-wide">GENLAYER STUDIONET · SLA ESCROW</div>
            </div>
          </div>
          <nav className="hidden md:flex items-center space-x-1 text-sm font-medium">
            {(['programs', 'claims', 'about'] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-3 py-1.5 rounded-lg transition capitalize ${tab === t ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'}`}>
                {t === 'about' ? 'How It Works' : t}
              </button>
            ))}
          </nav>
          <div>
            {account ? (
              <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-xl text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="font-mono text-gray-300">{short(account)}</span>
                <span className="text-sky-400 font-semibold pl-1 border-l border-gray-700">{balance} GEN</span>
              </div>
            ) : (
              <button onClick={handleConnect} disabled={busy}
                className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-lg shadow-sky-600/20">
                Connect Wallet
              </button>
            )}
          </div>
        </div>
      </header>

      {account && Number(balance) === 0 && (
        <div className="bg-amber-950/40 border-b border-amber-800/60 px-4 py-2 text-xs text-amber-200 flex items-center justify-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>Connected wallet has 0 GEN on studionet. Fund it from <a href="https://studio.genlayer.com" target="_blank" rel="noreferrer" className="underline font-bold text-amber-300 hover:text-white">GenLayer Studio → Accounts panel</a> (do NOT use the testnet faucet).</span>
        </div>
      )}

      {busy && waitMsg && (
        <div className="bg-indigo-950/80 border-b border-indigo-700/60 px-4 py-3 text-xs text-indigo-100 flex items-center justify-center space-x-3">
          <RefreshCw className="w-4 h-4 text-indigo-400 animate-spin" />
          <div className="text-center">
            <span className="font-bold text-indigo-300">{waitMsg}</span>{' '}
            <span>Non-deterministic consensus is slower than a normal tx — validators fetch the web and agree on the verdict.</span>
            {txHash && <a href={`${EXPLORER}/tx/${txHash}`} target="_blank" rel="noreferrer" className="ml-2 underline text-indigo-300 hover:text-white inline-flex items-center">Explorer <ExternalLink className="w-3 h-3 ml-1" /></a>}
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* PROGRAMS */}
        {tab === 'programs' && (
          <div>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-extrabold text-white tracking-tight">SLA Programs</h1>
                <p className="text-sm text-gray-400 mt-1 max-w-2xl">Providers post a collateral bond and pin their public SLA terms. When downtime is claimed, a GenLayer AI jury reads the terms + the status pages on-chain and rules whether a service credit is owed — no discretionary denials.</p>
              </div>
              <button onClick={() => setShowRegister(true)} className="bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition flex items-center space-x-2 shadow-lg shadow-sky-600/20 self-start">
                <PlusCircle className="w-4 h-4" /><span>Register Program</span>
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {programs.map((p) => (
                <div key={p.program_id} className="bg-gray-900/60 border border-gray-800 rounded-2xl p-5 flex flex-col">
                  <div className="flex items-center justify-between mb-3 text-xs">
                    <span className="font-mono text-gray-400">Program #{p.program_id}</span>
                    <span className={`px-2.5 py-0.5 rounded-full font-semibold text-[10px] border ${p.active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-gray-700/30 text-gray-400 border-gray-700'}`}>{p.active ? 'ACTIVE' : 'INACTIVE'}</span>
                  </div>
                  <h3 className="text-base font-bold text-gray-100 mb-2 flex items-center gap-2"><Server className="w-4 h-4 text-sky-400" />{p.service_name}</h3>
                  <div className="space-y-1.5 text-xs text-gray-400 border-t border-gray-800/80 pt-3 mt-2">
                    <div className="flex justify-between"><span>Uptime SLA:</span><span className="font-semibold text-sky-400">{toPct(p.uptime_target_bp)}%</span></div>
                    <div className="flex justify-between"><span>Provider bond:</span><span className="font-semibold text-emerald-400">{toGen(p.bond)} GEN</span></div>
                    <div className="flex justify-between items-center"><span>SLA terms:</span><a href={p.sla_terms_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline inline-flex items-center">pinned <ExternalLink className="w-3 h-3 ml-1" /></a></div>
                    <div className="flex justify-between"><span>Provider:</span><span className="font-mono text-gray-300">{short(p.provider)}</span></div>
                  </div>
                  <button onClick={() => { setFProgram(p.program_id); setShowFile(true); }} className="mt-4 w-full bg-gray-800 hover:bg-sky-600 text-gray-200 hover:text-white text-xs font-semibold py-2 rounded-xl transition">File a Breach Claim</button>
                </div>
              ))}
            </div>
            {programs.length === 0 && <Empty icon={<Server className="w-12 h-12 mx-auto text-gray-600 mb-3" />} title="No programs yet" sub="Register the first SLA-backed service." />}
          </div>
        )}

        {/* CLAIMS */}
        {tab === 'claims' && (
          <div>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-extrabold text-white tracking-tight">Breach Claims</h1>
                <p className="text-sm text-gray-400 mt-1">Bonded downtime claims adjudicated by decentralized AI consensus.</p>
              </div>
              <div className="flex items-center bg-gray-900 border border-gray-800 rounded-xl p-1 text-xs">
                {['ALL', 'OPEN', 'UPHELD', 'REJECTED', 'CHALLENGED', 'SETTLED'].map((f) => (
                  <button key={f} onClick={() => setFilter(f)} className={`px-3 py-1.5 rounded-lg font-medium transition ${filter === f ? 'bg-sky-600 text-white' : 'text-gray-400 hover:text-white'}`}>{f}</button>
                ))}
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {claims.map((c) => (
                <div key={c.claim_id} onClick={() => { setSelectedClaimId(c.claim_id); setTab('detail'); }} className="bg-gray-900/60 border border-gray-800 hover:border-sky-500/50 rounded-2xl p-5 cursor-pointer transition flex flex-col">
                  <div className="flex items-center justify-between mb-3 text-xs">
                    <span className="font-mono text-gray-400">Claim #{c.claim_id} · Prog #{c.program_id}</span>
                    <StateBadge state={c.state} />
                  </div>
                  <p className="text-sm text-gray-200 line-clamp-3 mb-3">{c.description}</p>
                  <div className="text-xs text-gray-400 border-t border-gray-800/80 pt-3 mt-auto space-y-1.5">
                    <div className="flex justify-between"><span>Window:</span><span className="text-gray-300">{c.incident_window}</span></div>
                    <div className="flex justify-between"><span>Bond:</span><span className="text-emerald-400 font-semibold">{toGen(c.claim_bond)} GEN</span></div>
                    {c.verdict && <div className="flex justify-between items-center"><span>Verdict:</span><VerdictTag verdict={c.verdict} severity={c.severity} confidence={c.confidence} /></div>}
                  </div>
                </div>
              ))}
            </div>
            {claims.length === 0 && <Empty icon={<Gavel className="w-12 h-12 mx-auto text-gray-600 mb-3" />} title="No claims in this filter" sub="File a claim from the Programs tab." />}
          </div>
        )}

        {/* DETAIL */}
        {tab === 'detail' && claim && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <button onClick={() => setTab('claims')} className="text-xs text-gray-400 hover:text-white">&larr; Back to claims</button>
            <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 sm:p-8">
              <div className="flex items-center gap-3 text-xs mb-4">
                <span className="font-mono text-gray-400">Claim #{claim.claim_id}</span>
                <StateBadge state={claim.state} />
                {claim.payout_done && <span className="bg-emerald-500/20 text-emerald-400 px-2.5 py-0.5 rounded-full font-bold flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Settled</span>}
              </div>
              {program && (
                <div className="bg-gray-950/60 border border-gray-800 rounded-2xl p-4 mb-5 text-xs grid grid-cols-2 gap-y-2">
                  <div><span className="text-gray-500">Service</span><div className="text-gray-200 font-semibold">{program.service_name}</div></div>
                  <div><span className="text-gray-500">Uptime SLA</span><div className="text-sky-400 font-semibold">{toPct(program.uptime_target_bp)}%</div></div>
                  <div><span className="text-gray-500">Incident window</span><div className="text-gray-200">{claim.incident_window}</div></div>
                  <div><span className="text-gray-500">SLA terms</span><div><a href={program.sla_terms_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:underline inline-flex items-center">pinned doc <ExternalLink className="w-3 h-3 ml-1" /></a></div></div>
                </div>
              )}
              <p className="text-sm text-gray-200 leading-relaxed mb-4">{claim.description}</p>
              <div className="flex flex-wrap gap-2 mb-2">
                <span className="text-[11px] text-gray-500 self-center">Evidence read on-chain:</span>
                {claim.evidence_urls.map((u, i) => (
                  <a key={i} href={u} target="_blank" rel="noreferrer" className="bg-gray-800/80 hover:bg-gray-700 px-2.5 py-1 rounded text-sky-400 flex items-center gap-1 text-xs"><span className="underline max-w-[240px] truncate">{u}</span><ExternalLink className="w-3 h-3" /></a>
                ))}
              </div>

              {claim.verdict && (
                <div className={`mt-6 rounded-2xl p-5 border ${claim.verdict === 'UPHELD' ? 'bg-emerald-950/30 border-emerald-500/30' : 'bg-rose-950/30 border-rose-500/30'}`}>
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2">
                      {claim.verdict === 'UPHELD' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <XCircle className="w-5 h-5 text-rose-400" />}
                      <h4 className={`font-bold text-base ${claim.verdict === 'UPHELD' ? 'text-emerald-300' : 'text-rose-300'}`}>AI Verdict: {claim.verdict}{claim.severity && claim.severity !== 'NONE' ? ` · ${claim.severity}` : ''}</h4>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-gray-400">Confidence</span>
                      <div className="w-24 bg-gray-800 rounded-full h-2 overflow-hidden"><div className="bg-sky-400 h-full" style={{ width: `${claim.confidence}%` }} /></div>
                      <span className="font-bold text-sky-400">{claim.confidence}%</span>
                    </div>
                  </div>
                  {claim.verdict === 'UPHELD' && claim.credit_bp > 0 && (
                    <div className="text-xs text-emerald-300/90 mb-2">Service credit owed: <b>{(claim.credit_bp / 100).toFixed(0)}%</b> of the provider bond.</div>
                  )}
                  <p className="text-sm text-gray-300 leading-relaxed italic">"{claim.reason}"</p>
                  {claim.challenge_deadline > 0 && !claim.payout_done && (
                    <div className="mt-3 text-[11px] text-gray-400 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" /> Challenge window {windowOpen ? 'open until' : 'closed at'} epoch {claim.challenge_deadline}.</div>
                  )}
                </div>
              )}

              {/* actions */}
              <div className="mt-6 flex flex-wrap gap-3">
                {claim.state === 'OPEN' && (
                  <button onClick={() => doTriage(claim.claim_id)} disabled={busy} className="bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition flex items-center gap-2"><Scale className="w-4 h-4" /> Run AI Triage</button>
                )}
                {canChallenge && (
                  <button onClick={() => setShowChallenge(true)} className="bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition flex items-center gap-2"><Gavel className="w-4 h-4" /> Challenge Verdict</button>
                )}
                {claim.state === 'CHALLENGED' && (
                  <button onClick={() => doRetriage(claim.claim_id)} disabled={busy} className="bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition flex items-center gap-2"><RefreshCw className="w-4 h-4" /> Re-triage (final)</button>
                )}
                {canSettle && (
                  <button onClick={() => doSettle(claim.claim_id)} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition flex items-center gap-2"><CheckCircle2 className="w-4 h-4" /> Settle & Pay Out</button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ABOUT */}
        {tab === 'about' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <h1 className="text-2xl font-extrabold text-white tracking-tight">How PactGuard Works</h1>
            <div className="text-sm text-gray-300 space-y-4 leading-relaxed">
              <p>PactGuard is an autonomous escrow for service-level agreements. A provider locks a collateral bond and pins its public SLA terms. When a customer claims downtime, the decision to pay a service credit is taken out of the provider's hands and given to GenLayer validator consensus.</p>
              <h3 className="text-lg font-bold text-white pt-2">Why it dies without GenLayer</h3>
              <ul className="list-disc pl-5 space-y-2">
                <li><b>On-chain web reading:</b> the contract runs <code>gl.nondet.web.render</code> to fetch the pinned SLA terms <i>and</i> the provider's public status / incident pages — no oracle.</li>
                <li><b>Subjective judgment:</b> an LLM jury decides whether the terms were actually breached (excludes scheduled maintenance? monthly vs per-incident budget? latency vs availability?) and grades severity MINOR / MAJOR / CRITICAL.</li>
                <li><b>Semantic consensus:</b> a custom <code>validator_fn</code> makes validators agree on the <i>verdict and severity tier</i>, not the wording — two nodes that disagree on the outcome cannot reach consensus.</li>
                <li><b>Bonded challenge:</b> the losing side can post a bonded rebuttal (a new URL) which triggers a final re-triage. Escrow pays out only after the window closes.</li>
              </ul>
              <p className="text-gray-400 text-xs pt-2">Contract on studionet: <a className="text-sky-400 hover:underline" href={`${EXPLORER}/address/${PACTGUARD_CONTRACT}`} target="_blank" rel="noreferrer">{PACTGUARD_CONTRACT}</a></p>
            </div>
          </div>
        )}
      </main>

      {/* REGISTER MODAL */}
      {showRegister && (
        <Modal title="Register SLA Program" onClose={() => setShowRegister(false)}>
          <form onSubmit={doRegister} className="space-y-4">
            <Field label="Service name"><input value={rName} onChange={(e) => setRName(e.target.value)} required placeholder="Acme Cloud API" className={inputCls} /></Field>
            <Field label="Pinned SLA terms URL (public https)"><input value={rUrl} onChange={(e) => setRUrl(e.target.value)} required type="url" className={inputCls} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Uptime SLA (%)"><input value={rUptime} onChange={(e) => setRUptime(e.target.value)} type="number" step="0.01" min="1" max="100" className={inputCls} /></Field>
              <Field label="Provider bond (GEN, min 0.5)"><input value={rBond} onChange={(e) => setRBond(e.target.value)} type="number" step="0.1" min="0.5" className={inputCls} /></Field>
            </div>
            <ModalButtons busy={busy} onCancel={() => setShowRegister(false)} label="Lock Bond & Register" />
          </form>
        </Modal>
      )}

      {/* FILE CLAIM MODAL */}
      {showFile && (
        <Modal title="File a Breach Claim" onClose={() => setShowFile(false)}>
          <form onSubmit={doFile} className="space-y-4">
            <Field label="Program">
              <select value={fProgram} onChange={(e) => setFProgram(e.target.value)} required className={inputCls}>
                <option value="">Select a program…</option>
                {programs.map((p) => <option key={p.program_id} value={p.program_id}>#{p.program_id} — {p.service_name} ({toPct(p.uptime_target_bp)}%)</option>)}
              </select>
            </Field>
            <Field label="Incident window"><input value={fWindow} onChange={(e) => setFWindow(e.target.value)} required placeholder="2026-09-12T02:00Z .. 06:30Z" className={inputCls} /></Field>
            <Field label="Description"><textarea value={fDesc} onChange={(e) => setFDesc(e.target.value)} required rows={3} placeholder="Full API outage 4h30m; all endpoints 503." className={inputCls} /></Field>
            <Field label="Evidence URLs (one per line, status / incident pages — up to 3)"><textarea value={fUrls} onChange={(e) => setFUrls(e.target.value)} required rows={3} placeholder={'https://status.acme.io/incidents/123\nhttps://downdetector.com/...'} className={inputCls} /></Field>
            <Field label="Claim bond (GEN, min 0.1)"><input value={fBond} onChange={(e) => setFBond(e.target.value)} type="number" step="0.1" min="0.1" className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowFile(false)} label="Post Bond & File Claim" />
          </form>
        </Modal>
      )}

      {/* CHALLENGE MODAL */}
      {showChallenge && claim && (
        <Modal title="Challenge the Verdict" onClose={() => setShowChallenge(false)}>
          <div className="bg-purple-950/30 border border-purple-800/40 rounded-xl p-3 text-xs text-purple-200 mb-4">Post a bond of at least {toGen(claim.claim_bond)} GEN. A new rebuttal URL will be read on-chain during a final re-triage.</div>
          <form onSubmit={doChallenge} className="space-y-4">
            <Field label="Rebuttal / evidence URL (https)"><input value={cUrl} onChange={(e) => setCUrl(e.target.value)} type="url" className={inputCls} /></Field>
            <Field label="Note"><textarea value={cNote} onChange={(e) => setCNote(e.target.value)} rows={2} required className={inputCls} /></Field>
            <ModalButtons busy={busy} onCancel={() => setShowChallenge(false)} label={`Post ${toGen(claim.claim_bond)} GEN & Challenge`} />
          </form>
        </Modal>
      )}

      <footer className="border-t border-gray-800 text-center py-4 text-[11px] text-gray-600">
        PactGuard · Intelligent Contract on GenLayer studionet · deployed at <span className="font-mono">{short(PACTGUARD_CONTRACT)}</span>
      </footer>
    </div>
  );
}

const inputCls = 'w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-sky-500';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (<div><label className="block text-xs font-semibold text-gray-300 mb-1">{label}</label>{children}</div>);
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
      <div className="bg-gray-900 border border-gray-800 rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between"><h3 className="text-lg font-bold text-white">{title}</h3><button onClick={onClose} className="text-gray-400 hover:text-white text-xl leading-none">&times;</button></div>
        {children}
      </div>
    </div>
  );
}

function ModalButtons({ busy, onCancel, label }: { busy: boolean; onCancel: () => void; label: string }) {
  return (
    <div className="pt-2 flex gap-3">
      <button type="button" onClick={onCancel} className="flex-1 bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold py-3 rounded-xl transition">Cancel</button>
      <button type="submit" disabled={busy} className="flex-1 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-bold py-3 rounded-xl transition">{busy ? 'Submitting…' : label}</button>
    </div>
  );
}

function StateBadge({ state }: { state: string }) {
  return <span className={`px-2.5 py-0.5 rounded-full font-semibold text-[10px] border ${STATE_STYLES[state] || 'bg-gray-700/30 text-gray-300 border-gray-700'}`}>{state}</span>;
}

function VerdictTag({ verdict, severity, confidence }: { verdict: string; severity: string; confidence: number }) {
  const up = verdict === 'UPHELD';
  return <span className={`font-bold flex items-center gap-1 ${up ? 'text-emerald-400' : 'text-rose-400'}`}>{up ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}{verdict}{severity && severity !== 'NONE' ? `/${severity}` : ''} ({confidence}%)</span>;
}

function Empty({ icon, title, sub }: { icon: React.ReactNode; title: string; sub: string }) {
  return (
    <div className="text-center py-16 bg-gray-900/30 rounded-2xl border border-gray-800/60">
      {icon}
      <h3 className="text-base font-semibold text-gray-300">{title}</h3>
      <p className="text-xs text-gray-500 mt-1">{sub}</p>
    </div>
  );
}
