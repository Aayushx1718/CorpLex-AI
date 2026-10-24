import { useEffect, useState, type FormEvent } from 'react';

type Scores = { accuracy: number; macro_f1: number; multiclass_brier: number; log_loss: number; per_class: { label: string; precision: number; recall: number; f1: number; support: number }[]; confusion_matrix: number[][] };
type Status = { model_available: boolean; risk_model_available: boolean; status: string; message: string;
  dataset: { dataset: string; source_url: string; citation: string; license: { name: string; verified: boolean }; counts: Record<string, Record<string, number>> } | null;
  report: { selected_model: string; validation_scope: string; comparisons: Record<string, { validation: Scores; test_calibrated: Scores }>; limitations: string[] } | null;
};
type Prediction = { label: string | null; abstained: boolean; reason: string; probabilities: { label: string; probability: number }[];
  explanation: { available: boolean; output_unit: string; features: { feature: string; contribution: number }[]; note: string } | null;
};
const percentage = (value: number) => `${(value * 100).toFixed(1)}%`;

export default function ModelLab() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setError('');
    fetch('/api/ml/status', { signal: controller.signal }).then(async response => {
      if (!response.ok) throw new Error('Could not load model status.');
      const body = await response.json();
      if (body.task !== 'clause_type') throw new Error('Unexpected model status response.');
      if (!controller.signal.aborted) setStatus(body);
    }).catch(err => { if (err.name !== 'AbortError') setError(err.message); });
    return () => controller.abort();
  }, [refresh]);
  async function classify(event: FormEvent) {
    event.preventDefault(); setError(''); setPrediction(null); setBusy(true);
    try {
      const response = await fetch('/api/ml/classify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
      const body = await response.json();
      if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Classification unavailable.');
      setPrediction(body);
    } catch (err) { setError(err instanceof Error ? err.message : 'Classification failed.'); }
    finally { setBusy(false); }
  }
  const labels = status?.dataset?.counts ? [...new Set(Object.values(status.dataset.counts).flatMap(counts => Object.keys(counts)))].sort() : [];
  const selected = status?.report && status.report.comparisons[status.report.selected_model]?.test_calibrated;
  return <section id="models" className="model-lab">
    <div className="section-title"><h2>Machine learning lab</h2><button onClick={() => setRefresh(value => value + 1)}>Refresh model status</button></div>
    <p className="help-text">Clause-type classification and business-risk assessment are different tasks. No validated low/medium/high risk classifier is available.</p>
    {error && <p role="alert" className="error-message">{error}</p>}
    {!status ? <p>Loading model status…</p> : <>
      <div className="analytics-kpis"><div><span>Clause-type model</span><strong>{status.model_available ? 'Active' : 'Not active'}</strong></div><div><span>Dataset license</span><strong>{status.dataset?.license.verified ? 'Verified' : 'Pending'}</strong></div><div><span>Business-risk model</span><strong>Unavailable</strong></div></div>
      <p className="model-message" role="status">{status.message}</p>
      {status.dataset && <><h3>Dataset provenance and split support</h3><p className="help-text">{status.dataset.dataset} · {status.dataset.license.name}. <a href={status.dataset.source_url} target="_blank" rel="noreferrer">Source release</a></p><p className="help-text">{status.dataset.citation}</p>
        {labels.length > 0 && <div className="table-scroll"><table><caption>Positive annotated spans · grouped by agreement, issuer and lexical duplicates</caption><thead><tr><th>Clause category</th><th>Train</th><th>Validation</th><th>Calibration</th><th>Test</th></tr></thead><tbody>{labels.map(label => <tr key={label}><td>{label}</td>{['train', 'validation', 'calibration', 'test'].map(split => <td key={split}>{status.dataset!.counts[split]?.[label] || 0}</td>)}</tr>)}</tbody></table></div>}
        <p className="help-text">These are custom grouped splits of positive CUAD spans, not official benchmark results. Counts describe data availability; they do not demonstrate model accuracy.</p>
      </>}
      {status.report ? <><h3>Held-out model comparison</h3><p className="help-text">Selected by validation macro F1: {status.report.selected_model}. Scope: {status.report.validation_scope}. Calibration uses a separate held-out split.</p><div className="table-scroll"><table><caption>Real experiment metrics from the active reviewed artifact</caption><thead><tr><th>Model</th><th>Validation F1</th><th>Test macro F1</th><th>Test accuracy</th><th>Brier score</th><th>Log loss</th></tr></thead><tbody>{Object.entries(status.report.comparisons).map(([name, scores]) => <tr key={name}><td>{name}</td><td>{percentage(scores.validation.macro_f1)}</td><td>{percentage(scores.test_calibrated.macro_f1)}</td><td>{percentage(scores.test_calibrated.accuracy)}</td><td>{scores.test_calibrated.multiclass_brier.toFixed(4)}</td><td>{scores.test_calibrated.log_loss.toFixed(4)}</td></tr>)}</tbody></table></div>
        {selected && <div className="table-scroll"><table><caption>Selected model · held-out per-class performance</caption><thead><tr><th>Category</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr></thead><tbody>{selected.per_class.map(row => <tr key={row.label}><td>{row.label}</td><td>{percentage(row.precision)}</td><td>{percentage(row.recall)}</td><td>{percentage(row.f1)}</td><td>{row.support}</td></tr>)}</tbody></table></div>}
        <details><summary>Evaluation limitations and confusion matrix</summary><ul>{status.report.limitations.map(value => <li key={value}>{value}</li>)}</ul><p>Rows are true categories, columns are predicted categories, in the per-class table order.</p><pre>{JSON.stringify(selected?.confusion_matrix, null, 2)}</pre></details>
      </> : <div className="analytics-empty">No reviewed model results are available. Accuracy, F1, calibration and SHAP results are withheld until a real licensed-data experiment completes.</div>}
      <form className="classification-form" onSubmit={classify}><label>Clause text<textarea aria-label="Clause text" value={text} onChange={event => setText(event.target.value)} minLength={20} maxLength={20000} required rows={5} placeholder="Paste a synthetic clause after a reviewed clause-type model is active." disabled={!status.model_available || busy} /></label><button type="submit" disabled={!status.model_available || busy}>{busy ? 'Classifying…' : 'Classify clause type'}</button></form>
      {prediction && <div className="model-message"><h3>{prediction.abstained ? 'Abstained · manual review required' : `${prediction.label} · manual review required`}</h3><p>{prediction.reason}</p><ul>{prediction.probabilities.map(row => <li key={row.label}>{row.label}: {percentage(row.probability)} model probability</li>)}</ul>{prediction.explanation?.available && <><h3>SHAP · {prediction.explanation.output_unit}</h3><ul>{prediction.explanation.features.map(row => <li key={row.feature}>{row.feature}: {row.contribution.toFixed(4)}</li>)}</ul><p>{prediction.explanation.note}</p></>}</div>}
    </>}
  </section>;
}
