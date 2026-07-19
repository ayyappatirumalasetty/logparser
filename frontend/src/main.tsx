import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { 
  AlertTriangle, 
  FileSearch, 
  Play, 
  Download, 
  Moon, 
  Clock, 
  CheckCircle2, 
  LoaderCircle, 
  Search, 
  SlidersHorizontal,
  Filter,
  Bot,
  Send
} from 'lucide-react';
import './styles.css';

type Event = { 
  timestamp: string; 
  source_file: string; 
  line_number: number;
  severity: string; 
  message: string; 
  exception?: string | null;
  stack_trace?: string | null;
};

type Result = { 
  incident: { target_time: string; window_seconds: number };
  summary: Record<string, number>; 
  report: string; 
  timeline: Event[]; 
  affected_files: string[];
};

type Progress = { 
  stage: string; 
  files_found: number; 
  files_parsed: number; 
  current_file?: string; 
  percentage: number; 
  elapsed_seconds: number; 
  estimated_remaining_seconds?: number | null; 
};

const API = 'http://localhost:8000';
const formatSeconds = (value?: number | null) => value == null ? 'calculating...' : `${Math.ceil(value)}s`;

const FILTER_OPTIONS = ['ERROR', 'WARN', 'INFO', 'Warning', 'Failed', 'Corrupt'];

function App() {
  const [folder, setFolder] = useState('D:\\loganalyser\\demo\\generated');
  const [target, setTarget] = useState('2026-07-19 14:08:15');
  const [windowSeconds, setWindowSeconds] = useState(65);
  const [patterns, setPatterns] = useState('*.log*, Backup*.log, WebService.log.*');
  
  const [checkedKeywords, setCheckedKeywords] = useState<string[]>([]);
  const [timelineSearch, setTimelineSearch] = useState('');
  
  const [result, setResult] = useState<Result | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loading, setLoading] = useState(false); 
  const [error, setError] = useState('');
  const [issueContext, setIssueContext] = useState('');
  const [supportAdvice, setSupportAdvice] = useState('');
  const [supportLoading, setSupportLoading] = useState(false);
  const [supportError, setSupportError] = useState('');
  const [supportModel, setSupportModel] = useState('');

  async function investigate() {
    setLoading(true); 
    setError(''); 
    setResult(null); 
    setSupportAdvice('');
    setSupportError('');
    setSupportModel('');
    setProgress({ stage: 'Connecting', files_found: 0, files_parsed: 0, percentage: 0, elapsed_seconds: 0 });
    
    try {
      const response = await fetch(`${API}/api/investigations/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          folder_path: folder,
          target_timestamp: target,
          window_seconds: windowSeconds,
          file_patterns: patterns.split(',').map(item => item.trim()).filter(Boolean),
          filter_keywords: [] // Backend keywords filter is handled dynamically on client side now
        })
      });
      
      if (!response.ok || !response.body) throw new Error('Unable to start the investigation.');
      
      const reader = response.body.getReader(); 
      const decoder = new TextDecoder(); 
      let buffer = '';
      
      while (true) { 
        const next = await reader.read(); 
        if (next.done) break; 
        buffer += decoder.decode(next.value, { stream: true }); 
        const lines = buffer.split('\n'); 
        buffer = lines.pop() ?? ''; 
        
        for (const line of lines) { 
          if (!line) continue; 
          const message = JSON.parse(line); 
          if (message.type === 'progress') setProgress(message.data); 
          if (message.type === 'result') setResult(message.data); 
          if (message.type === 'error') throw new Error(message.detail); 
        } 
      }
    } catch (reason) { 
      setError(reason instanceof Error ? reason.message : 'Unable to reach backend'); 
    } finally { 
      setLoading(false); 
    }
  }

  function entriesTxt(events: Event[]) {
    const groups = new Map<string, Event[]>();
    events.forEach(event => groups.set(event.source_file, [...(groups.get(event.source_file) ?? []), event]));
    return [...groups.entries()].map(([source, entries]) =>
      `${source.split('\\').pop() ?? source}\n${'='.repeat(42)}\n${entries.map(event =>
        `${event.timestamp} [${event.severity}] ${event.message}${event.stack_trace ? `\n${event.stack_trace}` : ''}`
      ).join('\n')}`
    ).join('\n\n');
  }

  async function getTroubleshooting() {
    if (!result) return;
    const entries = entriesTxt(filteredTimeline);
    if (!entries) {
      setSupportError('Select at least one matching log entry before asking the support engineer.');
      return;
    }
    setSupportLoading(true);
    setSupportError('');
    setSupportAdvice('');
    try {
      const response = await fetch(`${API}/api/support/troubleshoot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries_txt: entries, issue_context: issueContext })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? 'The support agent could not analyse these entries.');
      setSupportAdvice(data.troubleshooting_steps);
      setSupportModel(data.model || 'gpt-5.4-mini');
    } catch (reason) {
      setSupportError(reason instanceof Error ? reason.message : 'Unable to reach the AI support agent.');
    } finally {
      setSupportLoading(false);
    }
  }

  function downloadSupportAdvice(format: 'txt' | 'md') {
    if (!supportAdvice) return;
    const blob = new Blob([supportAdvice], { type: 'text/plain;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    
    const formattedTime = target.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '');
    const modelSuffix = supportModel ? `_${supportModel.replace(/[^a-zA-Z0-9]/g, '_')}` : '';
    
    link.download = `support_analysis_${formattedTime}${modelSuffix}.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function exportReport(format: string) { 
    if (!result) return; 

    // Construct dynamically filtered timeline based on selected checkboxes
    const activeTimeline = result.timeline.filter(event => {
      if (checkedKeywords.length > 0) {
        return checkedKeywords.some(kw => 
          event.message.toLowerCase().includes(kw.toLowerCase())
        );
      }
      return true;
    });

    const filteredResult = {
      ...result,
      timeline: activeTimeline,
      summary: {
        ...result.summary,
        matching_events: activeTimeline.length,
        errors: activeTimeline.filter(e => e.severity === 'ERROR').length,
        warnings: activeTimeline.filter(e => e.severity === 'WARN').length,
      }
    };

    const response = await fetch(`${API}/api/export/${format}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filteredResult)
    }); 
    
    if (!response.ok) {
      setError('The export could not be created.');
      return;
    } 
    const blob = await response.blob(); 
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    
    const formattedTime = target.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '');
    const filterSuffix = checkedKeywords.length > 0 ? `_filter_${checkedKeywords.join('_')}` : '';
    const baseName = `log_entries_${formattedTime}_win_${windowSeconds}s${filterSuffix}`;
    const reportName = `incident_report_${formattedTime}_win_${windowSeconds}s${filterSuffix}`;
    
    link.download = format === 'extracted-txt' ? `${baseName}.txt` : `${reportName}.${format}`;
    link.click();
    URL.revokeObjectURL(link.href); 
  }

  const filteredTimeline = result?.timeline.filter(event => {
    // 1. Keyword checkboxes filter
    if (checkedKeywords.length > 0) {
      const match = checkedKeywords.some(kw => 
        event.message.toLowerCase().includes(kw.toLowerCase())
      );
      if (!match) return false;
    }
    // 2. Search bar filter
    if (timelineSearch) {
      const term = timelineSearch.toLowerCase();
      return event.message.toLowerCase().includes(term) || 
             event.severity.toLowerCase().includes(term) ||
             event.source_file.toLowerCase().includes(term);
    }
    return true;
  }) ?? [];

  // Filtered counts for summary display when filters are active
  const filteredErrorsCount = filteredTimeline.filter(e => e.severity === 'ERROR').length;
  const filteredWarningsCount = filteredTimeline.filter(e => e.severity === 'WARN').length;

  return (
    <main>
      <header>
        <div className="brand">
          <span className="logo">
            <FileSearch size={24} />
          </span>
          <div>
            <h1>Incident Investigator</h1>
            <p>AI-assisted log correlation & incident narrative builder</p>
          </div>
        </div>
        <button className="icon-theme" aria-label="Dark mode">
          <Moon size={18} />
        </button>
      </header>

      <section className="hero">
        <div className="hero-text">
          <span className="eyebrow">INVESTIGATION WORKSPACE</span>
          <h2>Turn dispersed logs into a clear incident narrative.</h2>
          <p>Stream and correlate timestamped events across your log directory, then export shareable investigation evidence.</p>
        </div>
        <div className="health">
          <span className="status-indicator">
            <CheckCircle2 size={16} /> Service ready
          </span>
          <small>FastAPI local analysis engine</small>
        </div>
      </section>

      <div className="grid">
        <section className="card setup">
          <div className="card-header-with-icon">
            <SlidersHorizontal size={18} className="header-icon" />
            <h3>1. Configure investigation</h3>
          </div>
          
          <div className="form-group">
            <label>Log folder path</label>
            <input 
              value={folder} 
              onChange={event => setFolder(event.target.value)} 
              placeholder="D:\logs\production"
            />
          </div>

          <div className="twocol">
            <div className="form-group">
              <label>Target date and time</label>
              <div className="datetime-container">
                <input 
                  type="text" 
                  value={target} 
                  onChange={event => setTarget(event.target.value)}
                  placeholder="YYYY-MM-DD HH:mm:ss"
                />
                <span className="datetime-picker-trigger">
                  <Clock size={16} />
                </span>
                <input 
                  type="datetime-local" 
                  step="1" 
                  className="hidden-datetime-picker"
                  onChange={event => {
                    if (event.target.value) {
                      setTarget(event.target.value.replace('T', ' '));
                    }
                  }}
                />
              </div>
              <span className="input-hint">Type/paste timestamp or click clock icon to select</span>
            </div>
            
            <div className="form-group">
              <label>Window (seconds)</label>
              <input 
                type="number" 
                min="0" 
                value={windowSeconds} 
                onChange={event => setWindowSeconds(+event.target.value)}
              />
              <span className="input-hint">0 means exact second match</span>
            </div>
          </div>

          <div className="form-group">
            <label>File patterns <span className="label-sub">comma-separated, recursive</span></label>
            <input 
              value={patterns} 
              onChange={event => setPatterns(event.target.value)} 
              placeholder="*.log*, Backup*.log, WebService.log.*"
            />
            <span className="input-hint">Examples: <code>*.log*</code>, <code>tomcat*.*</code>, <code>WebService*.* , Backup-*.log</code></span>
          </div>

          <button className="primary" onClick={investigate} disabled={!folder || !target || loading}>
            {loading ? <LoaderCircle size={18} className="spin" /> : <Play size={18} />}
            {loading ? 'Analysing logs...' : 'Start investigation'}
          </button>

          {error && (
            <p className="error">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </p>
          )}

          {loading && progress && (
            <div className="progress-panel">
              <div className="progress-top">
                <span><LoaderCircle size={14} className="spin" /> {progress.stage}</span>
                <strong>{progress.percentage}%</strong>
              </div>
              <div className="progress-track">
                <i style={{ width: `${progress.percentage}%` }} />
              </div>
              <div className="progress-stats">
                <span>Parsed {progress.files_parsed} / {progress.files_found || '?'} files</span>
                <span>Elapsed {formatSeconds(progress.elapsed_seconds)} · ETA {formatSeconds(progress.estimated_remaining_seconds)}</span>
              </div>
              {progress.current_file && (
                <p className="current-file">
                  Current file: <code>{progress.current_file.split('\\').pop()}</code>
                </p>
              )}
            </div>
          )}
        </section>

        <section className="card context">
          <h3>Investigation Pipeline</h3>
          <ol>
            <li>
              <span>01</span>
              <div>
                <strong>Scan & Correlate</strong>
                <p>Recursively scans folders, normalizes timestamps, reconstructs stack traces, and correlates events in a time window</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Interactive Timeline</strong>
                <p>Combines events chronologically across all logs into a single, searchable, unified chronological timeline</p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Dynamic Filtering</strong>
                <p>Filters log entries instantly by level (ERROR, WARN, INFO) or custom keywords to isolate critical failures</p>
              </div>
            </li>
            <li>
              <span>04</span>
              <div>
                <strong>AI Support Agent</strong>
                <p>Analyzes the filtered logs alongside user context to generate safe, actionable troubleshooting advice</p>
              </div>
            </li>
          </ol>
          <p className="note">
            <Clock size={16} /> Large files are read line-by-line to limit memory use.
          </p>
        </section>
      </div>

      {result && (
        <>
          <section className="metrics">
            {[
              ['Files scanned', result.summary.files_scanned],
              ['Events parsed', result.summary.events_parsed],
              ['Window matches', checkedKeywords.length > 0 ? filteredTimeline.length : result.summary.matching_events],
              ['Errors', checkedKeywords.length > 0 ? filteredErrorsCount : result.summary.errors]
            ].map(([name, val]) => (
              <div className="metric" key={name}>
                <p>{name}</p>
                <strong>{val}</strong>
              </div>
            ))}
          </section>

          {/* Interactive Filtering Card */}
          <section className="card filter-controls">
            <div className="card-header-with-icon">
              <Filter size={18} className="header-icon" />
              <h3>2. Filter Log Output dynamically</h3>
            </div>
            <p className="filter-description">Select log levels or terms to narrow down the report summary and event downloads. The downloaded reports will dynamically adjust to your selection.</p>
            <div className="filter-badge-group">
              {FILTER_OPTIONS.map(kw => {
                const isSelected = checkedKeywords.includes(kw);
                return (
                  <button 
                    key={kw} 
                    className={`filter-pill ${isSelected ? 'selected' : ''}`}
                    onClick={() => {
                      setCheckedKeywords(prev => 
                        prev.includes(kw) ? prev.filter(k => k !== kw) : [...prev, kw]
                      );
                    }}
                  >
                    <span className="dot"></span>
                    {kw}
                  </button>
                );
              })}
              {checkedKeywords.length > 0 && (
                <button className="clear-filters-btn" onClick={() => setCheckedKeywords([])}>
                  Clear filters
                </button>
              )}
            </div>
          </section>

          <div className="results">
            <section className="card report">
              <div className="section-title">
                <div>
                  <span className="eyebrow">INVESTIGATION REPORT</span>
                  <h3>Executive Summary</h3>
                </div>
                <div className="exports">
                  {['extracted-txt', 'md'].map(format => (
                    <button key={format} onClick={() => exportReport(format)}>
                      <Download size={13} />
                      {format === 'extracted-txt' ? 'ENTRIES TXT' : format.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>
              <article className="report-content">
                {checkedKeywords.length > 0 ? (
                  `# Incident Investigation Report (Filtered)

## Executive Summary
Analysed ${filteredTimeline.length} matching events from ${result.summary.files_scanned} discovered files around ${result.incident.target_time}. ${filteredErrorsCount} error-level and ${filteredWarningsCount} warning-level events were observed.

## Filter Criteria
Currently filtering by keywords: ${checkedKeywords.join(', ')}.

## Timeline Summary
Events containing your keyword criteria are presented in the interactive timeline on the right. Download the report formats above to obtain a copy matching these keywords.
`
                ) : (
                  result.report
                )}
              </article>
            </section>

            <section className="card events-panel">
              <div className="section-title">
                <div>
                  <span className="eyebrow">CORRELATED EVENTS</span>
                  <h3>Interactive Timeline</h3>
                </div>
              </div>

              <div className="search-bar">
                <Search size={16} className="search-icon" />
                <input 
                  type="text" 
                  placeholder="Live search timeline by keyword, file name, severity..." 
                  value={timelineSearch}
                  onChange={e => setTimelineSearch(e.target.value)}
                />
                {timelineSearch && (
                  <button className="clear-search" onClick={() => setTimelineSearch('')}>×</button>
                )}
              </div>

              <div className="timeline-container">
                {filteredTimeline.length ? (
                  filteredTimeline.map((event, index) => {
                    const sev = event.severity.toLowerCase();
                    return (
                      <div className={`timeline-item border-${sev}`} key={`${event.source_file}-${index}`}>
                        <div className="timeline-meta">
                          <span className="time">{event.timestamp.split('T')[1]?.split('+')[0] ?? event.timestamp}</span>
                          <span className={`badge ${sev}`}>{event.severity}</span>
                          <span className="file-info" title={event.source_file}>
                            {event.source_file.split('\\').pop()}:{event.line_number}
                          </span>
                        </div>
                        <p className="message">{event.message}</p>
                        {event.stack_trace && (
                          <details className="stack-details">
                            <summary>View Stack Trace</summary>
                            <pre><code>{event.stack_trace}</code></pre>
                          </details>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="empty-timeline">
                    <p>No timeline events matched the filter.</p>
                  </div>
                )}
              </div>
            </section>
          </div>

          <section className="card support-engineer">
            <div className="card-header-with-icon">
              <Bot size={18} className="header-icon" />
              <h3>3. Ask the AI Support Engineer</h3>
            </div>
            <p className="filter-description">The agent receives the filtered Entries TXT content plus your optional issue context and returns safe troubleshooting steps.</p>
            <div className="form-group">
              <label htmlFor="issue-context">Issue context <span className="label-sub">optional</span></label>
              <textarea
                id="issue-context"
                value={issueContext}
                onChange={event => setIssueContext(event.target.value)}
                placeholder="What did the user experience? Include expected behavior, environment, recent changes, and symptoms."
                rows={5}
              />
            </div>
            <button className="primary support-button" onClick={getTroubleshooting} disabled={supportLoading || filteredTimeline.length === 0}>
              {supportLoading ? <LoaderCircle size={18} className="spin" /> : <Send size={18} />}
              {supportLoading ? 'Analysing entries...' : 'Get troubleshooting steps'}
            </button>
            {supportError && <p className="error"><AlertTriangle size={18} /><span>{supportError}</span></p>}
            {supportAdvice && (
              <article className="support-advice">
                <div className="support-header">
                  <span className="eyebrow">{supportModel ? `${supportModel.toUpperCase()} SUPPORT ANALYSIS` : 'SUPPORT ANALYSIS'}</span>
                  <div className="exports">
                    <button onClick={() => downloadSupportAdvice('txt')}>
                      <Download size={12} /> TXT
                    </button>
                    <button onClick={() => downloadSupportAdvice('md')}>
                      <Download size={12} /> MD
                    </button>
                  </div>
                </div>
                <pre>{supportAdvice}</pre>
              </article>
            )}
          </section>
        </>
      )}
    </main>
  );
}

createRoot(document.getElementById('root')!).render(<App />);
