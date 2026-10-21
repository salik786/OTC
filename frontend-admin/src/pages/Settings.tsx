import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../AuthContext";
import {
  api,
  ApiError,
  type Product,
  type RagConfig,
  type RagFieldMeta,
  type RagRegressionResult,
  type RagSettingsOverview,
  type RagTestResult,
  type RagVersion,
} from "../lib/api";

type Draft = { [K in keyof RagConfig]: RagConfig[K] | "" };
type Key = keyof RagConfig;

const GROUP_ORDER = ["Retrieval", "Generation", "Prompt", "Chunking & embedding"];

const FIELD_LABELS: Record<Key, string> = {
  top_k: "Chunks per question (top-k)",
  core_info_top_k: "Chunks for the medicine summary",
  history_turns: "Conversation memory (turns)",
  generation_model: "Generation model",
  temperature: "Temperature",
  max_tokens: "Max answer length (tokens)",
  core_info_max_tokens: "Max summary length (tokens)",
  fallback_text: "Out-of-scope reply",
  system_prompt: "System prompt",
  chunking_strategy: "Chunking strategy",
  chunk_size_chars: "Chunk size (characters)",
  chunk_overlap_chars: "Chunk overlap (characters)",
  embedding_model: "Embedding model",
};

function errorMessage(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    try {
      const parsed = JSON.parse(e.message);
      if (typeof parsed.detail === "string") return parsed.detail;
      if (typeof parsed.error === "string") return parsed.error;
    } catch {
      /* not JSON */
    }
    return e.message || fallback;
  }
  return fallback;
}

function fmtValue(v: unknown): string {
  const s = String(v);
  return s.length > 60 ? s.slice(0, 57) + "..." : s;
}

export function Settings() {
  const { credentials } = useAuth();
  const [overview, setOverview] = useState<RagSettingsOverview | null>(null);
  const [versions, setVersions] = useState<RagVersion[]>([]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState<{ kind: "success" | "error"; text: string } | null>(null);

  const [products, setProducts] = useState<Product[]>([]);
  const [productSlug, setProductSlug] = useState("");
  const [question, setQuestion] = useState("");
  const [testResult, setTestResult] = useState<RagTestResult | null>(null);
  const [regression, setRegression] = useState<RagRegressionResult | null>(null);

  const load = useCallback(async () => {
    if (!credentials) return;
    const [ov, vs] = await Promise.all([api.getRagSettings(credentials), api.listRagVersions(credentials)]);
    setOverview(ov);
    setVersions(vs);
    setDraft({ ...ov.active.config });
  }, [credentials]);

  useEffect(() => {
    load().catch((e) => setMessage({ kind: "error", text: errorMessage(e, "Could not load settings.") }));
    if (credentials) {
      api.listProducts(credentials).then((p) => {
        setProducts(p);
        if (p.length > 0) setProductSlug((cur) => cur || p[0].slug);
      });
    }
  }, [credentials, load]);

  const active = overview?.active.config;

  const changedKeys = useMemo(() => {
    if (!draft || !active) return [] as Key[];
    return (Object.keys(active) as Key[]).filter((k) => draft[k] !== active[k]);
  }, [draft, active]);

  const changedConfig = useMemo(() => {
    const out: Record<string, unknown> = {};
    if (draft) for (const k of changedKeys) out[k] = draft[k];
    return out as Partial<RagConfig>;
  }, [draft, changedKeys]);

  if (!overview || !draft || !active) {
    return (
      <section>
        <h2>RAG Settings</h2>
        {message ? <p className={message.kind}>{message.text}</p> : <p className="muted">Loading...</p>}
      </section>
    );
  }

  function setField(key: Key, raw: string | number) {
    setDraft((d) => (d ? { ...d, [key]: raw } : d));
  }

  async function run<T>(label: string, fn: () => Promise<T>, onOk: (r: T) => string | void | Promise<string | void>) {
    setBusy(label);
    setMessage(null);
    try {
      const r = await fn();
      const text = await onOk(r);
      if (text) setMessage({ kind: "success", text });
    } catch (e) {
      setMessage({ kind: "error", text: errorMessage(e, `${label} failed.`) });
    } finally {
      setBusy(null);
    }
  }

  const save = () =>
    run(
      "Save",
      () => api.saveRagSettings(credentials!, changedConfig, note),
      async (r) => {
        setNote("");
        await load();
        return (
          `Saved as version ${r.version.version}; it is live now.` +
          (r.needs_reindex.length ? ` Re-index to apply: ${r.needs_reindex.join(", ")}.` : "")
        );
      }
    );

  const restore = (v: RagVersion) => {
    if (changedKeys.length > 0 && !window.confirm("You have unsaved changes in the editor - restoring discards them. Continue?")) return;
    if (!window.confirm(`Make version ${v.version} the live configuration?`)) return;
    return run(
      "Restore",
      () => api.restoreRagVersion(credentials!, v.version),
      async (r) => {
        await load();
        return `Version ${r.version.version} is live again.` + (r.needs_reindex.length ? ` Re-index to apply: ${r.needs_reindex.join(", ")}.` : "");
      }
    );
  };

  const reindex = () => {
    if (!window.confirm("Re-chunk and re-embed every leaflet now? This takes a few seconds. If it fails, nothing is changed.")) return;
    return run(
      "Re-index",
      () => api.reindexRag(credentials!),
      async (r) => {
        await load();
        return `Re-indexed ${r.documents} leaflets into ${r.chunks} chunks in ${r.seconds}s.`;
      }
    );
  };

  const ask = () => {
    if (!question.trim() || !productSlug) return;
    setRegression(null);
    return run(
      "Test",
      () => api.testRagQuestion(credentials!, productSlug, question, changedConfig),
      (r) => {
        setTestResult(r);
      }
    );
  };

  const suite = () => {
    setTestResult(null);
    return run(
      "Boundary suite",
      () => api.runRagRegression(credentials!, productSlug, changedConfig),
      (r) => {
        setRegression(r);
      }
    );
  };

  const fieldsByGroup = GROUP_ORDER.map((g) => ({
    group: g,
    keys: (Object.keys(overview.fields) as Key[]).filter((k) => overview.fields[k].group === g),
  }));

  function renderInput(key: Key, meta: RagFieldMeta) {
    const v = draft![key];
    if (meta.type === "choice") {
      return (
        <select value={String(v)} onChange={(e) => setField(key, e.target.value)}>
          {meta.choices!.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      );
    }
    if (meta.type === "int" || meta.type === "float") {
      return (
        <input
          type="number"
          value={v as number | ""}
          min={meta.min}
          max={meta.max}
          step={meta.type === "float" ? 0.1 : 1}
          style={{ width: "8rem" }}
          onChange={(e) => setField(key, e.target.value === "" ? "" : Number(e.target.value))}
        />
      );
    }
    if (meta.type === "prompt") {
      const text = String(v);
      const missing = ["{product_display_name}", "{fallback_text}"].filter((p) => !text.includes(p));
      return (
        <div>
          <textarea
            value={text}
            rows={20}
            spellCheck={false}
            className="mono"
            style={{ width: "100%", boxSizing: "border-box" }}
            onChange={(e) => setField(key, e.target.value)}
          />
          <div className="muted">
            {text.length.toLocaleString()} characters ·{" "}
            {missing.length === 0 ? (
              <span className="success">both required placeholders present</span>
            ) : (
              <span className="error">missing {missing.join(" and ")}</span>
            )}
            {" · "}
            <button
              type="button"
              className="link-button"
              onClick={() => setField(key, overview!.defaults.system_prompt)}
              disabled={text === overview!.defaults.system_prompt}
            >
              Reset to built-in default
            </button>
          </div>
        </div>
      );
    }
    return <input type="text" value={String(v)} style={{ width: "100%", boxSizing: "border-box" }} onChange={(e) => setField(key, e.target.value)} />;
  }

  const lockedByBusy = busy !== null;

  return (
    <section>
      <h2>RAG Settings</h2>
      <p className="muted">
        Change how answers are produced without touching code. Every save creates a new numbered version, and every logged
        turn records the version it used, so results can always be traced to the exact settings.
      </p>

      <div className="panel">
        <strong>Live version {overview.active.version}</strong>{" "}
        <span className="muted">
          · {overview.active.created_by || "unknown"} · {new Date(overview.active.created_at).toLocaleString()}
          {overview.active.note ? ` · "${overview.active.note}"` : ""}
        </span>
      </div>

      {message && <p className={message.kind}>{message.text}</p>}

      {overview.pending_reindex.length > 0 && (
        <div className="banner banner-warn">
          <strong>Search index is out of date.</strong> These saved settings are not applied until you re-index:{" "}
          <span className="mono">{overview.pending_reindex.join(", ")}</span>. Searching keeps working with the old index meanwhile.{" "}
          <button disabled={lockedByBusy} onClick={reindex}>
            {busy === "Re-index" ? "Re-indexing..." : "Re-index now"}
          </button>
        </div>
      )}

      {fieldsByGroup.map(({ group, keys }) => (
        <div className="panel" key={group}>
          <h3 style={{ marginTop: 0 }}>{group}</h3>
          {group === "Chunking & embedding" && (
            <p className="muted">
              Saved as a new version straight away, but only take effect after a re-index (which re-splits and re-embeds every leaflet).
              Live index: <span className="mono">{overview.index.embedding_model}</span>, {overview.index.chunking_strategy}, {overview.index.chunk_count} chunks
              {overview.index.built_at ? `, built ${new Date(overview.index.built_at).toLocaleString()}` : ""}.
              {overview.index.documents.some((d) => d.source_reconstructed) && (
                <>
                  {" "}
                  <span className="error">
                    {overview.index.documents.filter((d) => d.source_reconstructed).map((d) => d.filename).join(", ")} was rebuilt from stored chunks (the original file wasn't kept), so re-chunking it is approximate - re-upload it for exact results.
                  </span>
                </>
              )}
            </p>
          )}
          {keys.map((key) => {
            const meta = overview.fields[key];
            const changed = changedKeys.includes(key);
            return (
              <div className={`setting-row${changed ? " setting-changed" : ""}`} key={key}>
                <label>
                  <strong>{FIELD_LABELS[key]}</strong>
                  {meta.reindex && <span className="tag">needs re-index</span>}
                  {changed && <span className="tag tag-changed">edited</span>}
                </label>
                {renderInput(key, meta)}
                <div className="muted">
                  {meta.help}
                  {key === "chunking_strategy" && ` ${overview.chunking_strategies[String(draft[key])] ?? ""}`}
                  {meta.type !== "prompt" && (
                    <>
                      {" "}
                      <span className="mono">
                        (built-in default: {fmtValue(overview.defaults[key])}
                        {meta.min !== undefined ? `; allowed ${meta.min}-${meta.max}` : ""})
                      </span>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}

      <div className="panel form-row">
        <input
          type="text"
          className="grow"
          placeholder="What is this change for? (recorded with the version)"
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
        />
        <button disabled={lockedByBusy || changedKeys.length === 0} onClick={save}>
          {busy === "Save" ? "Saving..." : changedKeys.length === 0 ? "No changes" : `Save ${changedKeys.length} change${changedKeys.length === 1 ? "" : "s"} as new version`}
        </button>
        <button className="link-button" disabled={changedKeys.length === 0} onClick={() => setDraft({ ...active })}>
          Discard edits
        </button>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Try these settings</h3>
        <p className="muted">
          Uses the live version plus your unsaved edits above. Nothing is saved and no session or turn is logged, so trying settings
          never touches research data. Chunking/embedding edits are not applied here until re-indexed.
        </p>
        <div className="form-row">
          <select value={productSlug} onChange={(e) => setProductSlug(e.target.value)}>
            {products.map((p) => (
              <option key={p.id} value={p.slug}>
                {p.display_name}
              </option>
            ))}
          </select>
          <input
            type="text"
            className="grow"
            placeholder="Type a question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
          />
          <button disabled={lockedByBusy || !question.trim()} onClick={ask}>
            {busy === "Test" ? "Asking..." : "Ask"}
          </button>
          <button disabled={lockedByBusy} onClick={suite}>
            {busy === "Boundary suite" ? "Running..." : "Run boundary suite"}
          </button>
        </div>

        {testResult && (
          <div style={{ marginTop: "0.75rem" }}>
            <p>
              <strong>Answer{!testResult.in_scope ? " (deflected)" : ""}:</strong> {testResult.answer_text}
            </p>
            {testResult.note && <p className="muted">{testResult.note}</p>}
            <details>
              <summary className="muted">
                Retrieved {testResult.retrieved_chunks.length} chunks ({Math.round(testResult.latency_ms)}ms):{" "}
                {testResult.retrieved_chunks.map((c) => `${c.section_label ?? "?"} (${c.score.toFixed(2)})`).join(" · ")}
              </summary>
              {testResult.retrieved_chunks.map((c, i) => (
                <div className="chunk-card" key={i}>
                  <div className="muted mono">
                    #{i + 1} · {c.section_label ?? "no section"} · score {c.score.toFixed(3)}
                  </div>
                  <pre style={{ whiteSpace: "pre-wrap", margin: "4px 0 0 0" }}>{c.text}</pre>
                </div>
              ))}
            </details>
          </div>
        )}

        {regression && (
          <div style={{ marginTop: "0.75rem" }}>
            <p className={regression.passed === regression.total ? "success" : "error"}>
              <strong>
                Boundary suite: {regression.passed}/{regression.total} as expected
              </strong>
              {regression.passed === regression.total
                ? " - every must-answer question was answered and every must-refuse question was refused."
                : " - do not save a prompt that fails cases that passed before."}
            </p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th></th>
                    <th>Question</th>
                    <th>Should be</th>
                    <th>Reply</th>
                  </tr>
                </thead>
                <tbody>
                  {regression.results.map((r, i) => (
                    <tr key={i}>
                      <td className={r.passed ? "success" : "error"}>{r.passed ? "pass" : "FAIL"}</td>
                      <td>{r.query}</td>
                      <td className="nowrap">{r.expected_in_scope ? "answered" : "refused"}</td>
                      <td>{r.answer_text.length > 140 ? r.answer_text.slice(0, 137) + "..." : r.answer_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>Version history</h3>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>When</th>
                <th>By</th>
                <th>Note</th>
                <th>Changed</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v, i) => {
                const older = versions[i + 1];
                const diff = older ? (Object.keys(v.config) as Key[]).filter((k) => v.config[k] !== older.config[k]) : [];
                return (
                  <tr key={v.version}>
                    <td className="nowrap">
                      <strong>v{v.version}</strong> {v.is_active && <span className="tag tag-live">live</span>}
                    </td>
                    <td className="nowrap">{new Date(v.created_at).toLocaleString()}</td>
                    <td>{v.created_by}</td>
                    <td>{v.note}</td>
                    <td className="muted">{older ? (diff.length ? diff.map((k) => FIELD_LABELS[k]).join(", ") : "-") : "initial"}</td>
                    <td>
                      {!v.is_active && (
                        <button disabled={lockedByBusy} onClick={() => restore(v)}>
                          Restore
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
