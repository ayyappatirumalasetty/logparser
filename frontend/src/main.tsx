import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { AlertTriangle, FileSearch, Play, Download, Moon, Clock, CheckCircle2, LoaderCircle } from 'lucide-react';
import './styles.css';

type Event = { timestamp: string; source_file: string; severity: string; message: string };
type Result = { summary: Record<string, number>; report: string; timeline: Event[] };
type Progress = { stage: string; files_found: number; files_parsed: number; current_file?: string; percentage: number; elapsed_seconds: number; estimated_remaining_seconds?: number | null };
const API = 'http://localhost:8000';
const seconds = (value?: number | null) => value == null ? 'calculating...' : `${Math.ceil(value)}s`;

function App() {
  const [folder, setFolder] = useState('D:\\loganalyser\\temptes');
  const [target, setTarget] = useState('2026-07-18T05:55:36');
  const [windowSeconds, setWindowSeconds] = useState(15);
  const [patterns, setPatterns] = useState('*.log*, *.txt');
  const [result, setResult] = useState<Result | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false); const [error, setError] = useState('');

  async function investigate() {
    setLoading(true); setError(''); setResult(null); setProgress({stage:'Connecting',files_found:0,files_parsed:0,percentage:0,elapsed_seconds:0});
    try {
      const response = await fetch(`${API}/api/investigations/stream`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({folder_path:folder,target_timestamp:target,window_seconds:windowSeconds,file_patterns:patterns.split(',').map(item=>item.trim()).filter(Boolean)})});
      if (!response.ok || !response.body) throw new Error('Unable to start the investigation.');
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) { const next = await reader.read(); if (next.done) break; buffer += decoder.decode(next.value, {stream:true}); const lines = buffer.split('\n'); buffer = lines.pop() ?? ''; for (const line of lines) { if (!line) continue; const message = JSON.parse(line); if (message.type === 'progress') setProgress(message.data); if (message.type === 'result') setResult(message.data); if (message.type === 'error') throw new Error(message.detail); } }
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to reach backend'); } finally { setLoading(false); }
  }
  async function exportReport(format:string) { if (!result) return; const response=await fetch(`${API}/api/export/${format}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)}); if(!response.ok){setError('The export could not be created.');return;} const blob=await response.blob(); const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=format==='extracted-txt'?'extracted-log-entries.txt':`incident-report.${format}`;link.click();URL.revokeObjectURL(link.href); }
  return <main><header><div className="brand"><span className="logo"><FileSearch size={21}/></span><div><h1>Incident Investigator</h1><p>AI-assisted log correlation</p></div></div><button className="icon" aria-label="Dark mode"><Moon size={18}/></button></header>
  <section className="hero"><div><span className="eyebrow">INVESTIGATION WORKSPACE</span><h2>Turn dispersed logs into a clear incident narrative.</h2><p>Stream and correlate timestamped events across your log directory, then export shareable investigation evidence.</p></div><div className="health"><CheckCircle2/> Service ready<br/><small>FastAPI local analysis engine</small></div></section>
  <div className="grid"><section className="card setup"><h3>1. Configure investigation</h3><label>Log folder path<input value={folder} onChange={event=>setFolder(event.target.value)} placeholder="D:\\logs\\production"/></label><div className="twocol"><label>Target date and time<input type="datetime-local" step="1" value={target} onChange={event=>setTarget(event.target.value)}/></label><label>Window (seconds)<input type="number" min="0" value={windowSeconds} onChange={event=>setWindowSeconds(+event.target.value)}/></label></div><label>File patterns <span>comma-separated, recursive</span><input value={patterns} onChange={event=>setPatterns(event.target.value)} placeholder="*.log*, Backup*.log, WebService.log.*"/></label><p className="field-help">Examples: <code>*.log*</code>, <code>tomcat*.*</code>, <code>DataStoreService*.*</code>, <code>Apache.log</code>. <code>*.log*</code> includes rotated logs such as <code>WebService.log.10</code>.</p><button className="primary" onClick={investigate} disabled={!folder||!target||loading}><Play size={17}/>{loading?'Analysing logs...':'Start investigation'}</button>{error&&<p className="error"><AlertTriangle size={16}/>{error}</p>}{loading&&progress&&<div className="progress-panel"><div className="progress-top"><span><LoaderCircle size={15} className="spin"/>{progress.stage}</span><strong>{progress.percentage}%</strong></div><div className="progress-track"><i style={{width:`${progress.percentage}%`}}/></div><div className="progress-stats"><span>Parsed {progress.files_parsed} / {progress.files_found||'?'} files</span><span>Elapsed {seconds(progress.elapsed_seconds)} · ETA {seconds(progress.estimated_remaining_seconds)}</span></div>{progress.current_file&&<p className="current-file">Current file: <code>{progress.current_file}</code></p>}</div>}</section>
  <section className="card context"><h3>What the engine does</h3><ol><li><span>01</span>Recursively scans the selected patterns</li><li><span>02</span>Normalizes common timestamp formats</li><li><span>03</span>Joins multiline Java-style stack traces</li><li><span>04</span>Correlates events in the selected window</li></ol><p className="note"><Clock size={16}/> Large files are read line-by-line to limit memory use.</p></section></div>
  {result&&<><section className="metrics">{[['Files scanned','files_scanned'],['Events parsed','events_parsed'],['Window matches','matching_events'],['Errors','errors']].map(([name,key])=><div className="metric" key={key}><p>{name}</p><strong>{result.summary[key]}</strong></div>)}</section><div className="results"><section className="card report"><div className="section-title"><div><span className="eyebrow">INVESTIGATION</span><h3>Investigation report</h3></div><div className="exports">{['extracted-txt','pdf','md','html','txt'].map(format=><button key={format} onClick={()=>exportReport(format)}><Download size={14}/>{format==='extracted-txt'?'ENTRIES TXT':format.toUpperCase()}</button>)}</div></div><article>{result.report}</article></section><section className="card events"><h3>Correlated timeline</h3>{result.timeline.length?result.timeline.slice(0,100).map((event,index)=><div className="event" key={`${event.source_file}-${index}`}><time>{new Date(event.timestamp).toLocaleTimeString()}</time><span className={'badge '+event.severity.toLowerCase()}>{event.severity}</span><p>{event.message}</p><small>{event.source_file}</small></div>):<p className="empty">No events fell within this time window.</p>}</section></div></>}
  </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
