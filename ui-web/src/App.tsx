import { type ReactNode, useEffect, useState } from "react";
import { api } from "./api";
import type {
  ArtifactFile,
  ArtifactTree,
  DocumentCard,
  DocumentDetail,
  EventItem,
  ExportQueue,
  FieldValue,
  Stats,
  ViewId
} from "./types";

const EMPTY_STATS: Stats = {
  total: 0,
  completed: 0,
  processing: 0,
  failed: 0,
  ready_to_export: 0,
  requires_attention: 0,
  null_fields: 0,
  review_fields: 0,
  invalid_fields: 0,
  success_rate: 0,
  by_type: {},
  run_root: ""
};

function App() {
  const [view, setView] = useState<ViewId>("monitoring");
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [documents, setDocuments] = useState<DocumentCard[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [queue, setQueue] = useState<ExportQueue | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetail | null>(null);
  const [artifactTree, setArtifactTree] = useState<ArtifactTree | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactFile | null>(null);
  const [artifactText, setArtifactText] = useState<string>("");
  const [fieldDraft, setFieldDraft] = useState<Record<string, unknown>>({});
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboard() {
    try {
      const [statsData, docsData, eventsData, queueData] = await Promise.all([
        api.stats(),
        api.documents(),
        api.events(),
        api.exportQueue()
      ]);
      setStats(statsData);
      setDocuments(docsData.documents);
      setEvents(eventsData.events);
      setQueue(queueData);
      if (!selectedId && docsData.documents.length) {
        setSelectedId(docsData.documents[0].id);
      }
      setError(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setLoading(false);
    }
  }

  async function loadDocument(id: string) {
    try {
      const [detail, artifacts] = await Promise.all([api.document(id), api.artifacts(id)]);
      setSelectedDocument(detail);
      setArtifactTree(artifacts);
      setSelectedArtifact(null);
      setArtifactText("");
      setFieldDraft(detail.review_draft?.fields ?? {});
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function openArtifact(file: ArtifactFile) {
    setSelectedArtifact(file);
    setArtifactText("");
    if (!selectedId || file.preview_type !== "text") {
      return;
    }
    try {
      const preview = await api.artifactText(selectedId, file.relative_path);
      setArtifactText(preview.error ? preview.error : preview.text);
    } catch (exc) {
      setArtifactText(exc instanceof Error ? exc.message : String(exc));
    }
  }

  async function saveReviewDraft() {
    if (!selectedId || Object.keys(fieldDraft).length === 0) {
      return;
    }
    await api.saveReview(selectedId, fieldDraft);
    await loadDocument(selectedId);
    await loadDashboard();
  }

  useEffect(() => {
    void loadDashboard();
    const handle = window.setInterval(() => void loadDashboard(), 15_000);
    return () => window.clearInterval(handle);
  }, []);

  useEffect(() => {
    if (selectedId) {
      void loadDocument(selectedId);
    }
  }, [selectedId]);

  const visibleDocuments = documents.filter((doc) => {
    if (filter === "all") {
      return true;
    }
    if (filter === "attention") {
      return !doc.ready_to_export;
    }
    return doc.document_type === filter || doc.status === filter;
  });

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AF</div>
          <div>
            <strong>Algofusion UI</strong>
            <span>production console</span>
          </div>
        </div>
        <nav className="nav">
          <button className={view === "monitoring" ? "active" : ""} onClick={() => setView("monitoring")}>
            <span>01</span> Мониторинг
          </button>
          <button className={view === "export" ? "active" : ""} onClick={() => setView("export")}>
            <span>1C</span> Экспорт 1С
          </button>
          <button className={view === "developer" ? "active" : ""} onClick={() => setView("developer")}>
            <span>DV</span> Developer
          </button>
        </nav>
        <div className="sidebar-footer">
          <span>run root</span>
          <strong title={stats.run_root}>{shortPath(stats.run_root)}</strong>
          <small>v0.1.0-ui-web</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AlgoFusion2 / OCR pipeline v2</p>
            <h1>{view === "monitoring" ? "Мониторинг" : view === "export" ? "Экспорт 1С" : "Developer Explorer"}</h1>
          </div>
          <div className="topbar-actions">
            {error && <span className="error-pill">{error}</span>}
            <button className="ghost-button" onClick={() => void loadDashboard()}>
              Обновить
            </button>
          </div>
        </header>

        {loading ? (
          <div className="loading-card">Загружаю артефакты пайплайна...</div>
        ) : (
          <>
            {view === "monitoring" && (
              <MonitoringView
                stats={stats}
                documents={visibleDocuments}
                events={events}
                filter={filter}
                onFilter={setFilter}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            )}
            {view === "export" && (
              <ExportView
                stats={stats}
                queue={queue}
                selectedDocument={selectedDocument}
                selectedId={selectedId}
                fieldDraft={fieldDraft}
                onDraft={setFieldDraft}
                onSelect={setSelectedId}
                onSave={() => void saveReviewDraft()}
              />
            )}
            {view === "developer" && (
              <DeveloperView
                documents={documents}
                selectedId={selectedId}
                selectedDocument={selectedDocument}
                artifactTree={artifactTree}
                selectedArtifact={selectedArtifact}
                artifactText={artifactText}
                onSelectDocument={setSelectedId}
                onSelectArtifact={(file) => void openArtifact(file)}
              />
            )}
          </>
        )}
      </main>
    </div>
  );
}

function MonitoringView(props: {
  stats: Stats;
  documents: DocumentCard[];
  events: EventItem[];
  filter: string;
  selectedId: string | null;
  onFilter: (value: string) => void;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="page-grid">
      <div className="metrics-row">
        <MetricCard label="Всего" value={props.stats.total} tone="neutral" />
        <MetricCard label="В обработке" value={props.stats.processing} tone="warning" />
        <MetricCard label="Завершено" value={props.stats.completed} tone="success" />
        <MetricCard label="Ошибки" value={props.stats.failed} tone="danger" />
        <MetricCard label="Готово к экспорту" value={props.stats.ready_to_export} tone="info" />
      </div>

      <section className="panel documents-panel">
        <div className="panel-head">
          <div>
            <h2>Документы</h2>
            <p>Последние загруженные и пересобранные документы</p>
          </div>
          <select value={props.filter} onChange={(event) => props.onFilter(event.target.value)}>
            <option value="all">Все статусы</option>
            <option value="attention">Требуют внимания</option>
            <option value="waybill">Накладные</option>
            <option value="invoice">Счета</option>
            <option value="payment_order">Платежки</option>
            <option value="account_prot">Account prot</option>
          </select>
        </div>
        <DocumentTable documents={props.documents} selectedId={props.selectedId} onSelect={props.onSelect} />
      </section>

      <EventPanel events={props.events} />
    </section>
  );
}

function ExportView(props: {
  stats: Stats;
  queue: ExportQueue | null;
  selectedDocument: DocumentDetail | null;
  selectedId: string | null;
  fieldDraft: Record<string, unknown>;
  onDraft: (value: Record<string, unknown>) => void;
  onSelect: (id: string) => void;
  onSave: () => void;
}) {
  const attention = props.queue?.requires_attention ?? [];
  const ready = props.queue?.ready ?? [];
  return (
    <section className="export-layout">
      <div className="metrics-row">
        <MetricCard label="Готово 100%" value={props.stats.ready_to_export} tone="success" />
        <MetricCard label="Пустые поля" value={props.stats.null_fields} tone="warning" />
        <MetricCard label="Проверить поле" value={props.stats.review_fields} tone="danger" />
        <MetricCard label="Уже собрано" value={props.stats.completed} tone="info" />
      </div>

      <div className="split">
        <section className="panel queue-panel">
          <div className="tabs">
            <span className="active">Требуют внимания ({attention.length})</span>
            <span>Готовы к экспорту ({ready.length})</span>
          </div>
          <div className="queue-list">
            {[...attention, ...ready].slice(0, 80).map((doc) => (
              <button
                key={doc.id}
                className={`queue-item ${props.selectedId === doc.id ? "active" : ""}`}
                onClick={() => props.onSelect(doc.id)}
              >
                <strong>{doc.filename}</strong>
                <div className="queue-badges">
                  {doc.null_count > 0 && <Badge tone="warning">Null: {doc.null_count}</Badge>}
                  {doc.review_count > 0 && <Badge tone="danger">Review: {doc.review_count}</Badge>}
                  {doc.ready_to_export && <Badge tone="success">Ready</Badge>}
                </div>
              </button>
            ))}
          </div>
        </section>

        <FieldEditor
          document={props.selectedDocument}
          draft={props.fieldDraft}
          onDraft={props.onDraft}
          onSave={props.onSave}
        />
      </div>
    </section>
  );
}

function DeveloperView(props: {
  documents: DocumentCard[];
  selectedId: string | null;
  selectedDocument: DocumentDetail | null;
  artifactTree: ArtifactTree | null;
  selectedArtifact: ArtifactFile | null;
  artifactText: string;
  onSelectDocument: (id: string) => void;
  onSelectArtifact: (file: ArtifactFile) => void;
}) {
  return (
    <section className="developer-layout">
      <section className="panel document-picker">
        <div className="panel-head compact">
          <h2>Документ</h2>
          <select value={props.selectedId ?? ""} onChange={(event) => props.onSelectDocument(event.target.value)}>
            {props.documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename}
              </option>
            ))}
          </select>
        </div>
        {props.selectedDocument && (
          <div className="doc-summary">
            <h3>{props.selectedDocument.filename}</h3>
            <p>{props.selectedDocument.base_path}</p>
            <div className="summary-grid">
              <Badge tone="info">{props.selectedDocument.document_type}</Badge>
              <Badge tone={props.selectedDocument.ready_to_export ? "success" : "warning"}>
                {props.selectedDocument.ready_to_export ? "ready" : "attention"}
              </Badge>
              <Badge tone="neutral">{props.selectedDocument.field_count} fields</Badge>
            </div>
          </div>
        )}
      </section>

      <section className="panel artifact-list">
        <div className="panel-head compact">
          <h2>Артефакты</h2>
          <p>{props.artifactTree?.files.length ?? 0} files</p>
        </div>
        <div className="artifact-table">
          {props.artifactTree?.files.map((file) => (
            <button
              key={file.relative_path}
              className={props.selectedArtifact?.relative_path === file.relative_path ? "active" : ""}
              onClick={() => props.onSelectArtifact(file)}
            >
              <span>{file.stage}</span>
              <strong>{file.relative_path}</strong>
              <em>{formatBytes(file.size_bytes)}</em>
            </button>
          ))}
        </div>
      </section>

      <section className="panel preview-panel">
        <div className="panel-head compact">
          <h2>Preview</h2>
          <p>{props.selectedArtifact?.relative_path ?? "Выберите артефакт"}</p>
        </div>
        <ArtifactPreview
          documentId={props.selectedId}
          artifact={props.selectedArtifact}
          artifactText={props.artifactText}
        />
      </section>
    </section>
  );
}

function FieldEditor(props: {
  document: DocumentDetail | null;
  draft: Record<string, unknown>;
  onDraft: (value: Record<string, unknown>) => void;
  onSave: () => void;
}) {
  if (!props.document) {
    return <section className="panel field-editor empty">Выберите документ для проверки полей.</section>;
  }
  const problemFields = props.document.fields.filter((field) => field.state !== "ok" || field.has_draft);
  const visibleFields = problemFields.length ? problemFields : props.document.fields.slice(0, 80);
  return (
    <section className="panel field-editor">
      <div className="editor-title">
        <div>
          <h2>{props.document.filename}</h2>
          <p>
            {props.document.document_type} / {props.document.field_count} fields
          </p>
        </div>
        <button className="primary-button" disabled={Object.keys(props.draft).length === 0} onClick={props.onSave}>
          Сохранить изменения
        </button>
      </div>
      <div className="fields-table">
        <div className="field-row header">
          <span>Поле</span>
          <span>Текущее значение</span>
          <span>Новое значение</span>
          <span>Каталог</span>
        </div>
        {visibleFields.map((field) => (
          <FieldRow key={field.path} field={field} draft={props.draft} onDraft={props.onDraft} />
        ))}
      </div>
    </section>
  );
}

function FieldRow(props: {
  field: FieldValue;
  draft: Record<string, unknown>;
  onDraft: (value: Record<string, unknown>) => void;
}) {
  const value = props.draft[props.field.path] ?? props.field.draft_value ?? props.field.value ?? "";
  return (
    <div className={`field-row ${props.field.effective_state}`}>
      <div>
        <strong>{props.field.label}</strong>
        <small>{props.field.path}</small>
      </div>
      <span className="field-current">{valueToString(props.field.value)}</span>
      <input
        value={valueToString(value)}
        onChange={(event) => props.onDraft({ ...props.draft, [props.field.path]: event.target.value })}
      />
      <span>
        {props.field.has_draft && <Badge tone="success">draft</Badge>}
        {!props.field.has_draft && props.field.catalog ? <Badge tone="info">{props.field.catalog}</Badge> : null}
        {!props.field.has_draft && !props.field.catalog ? "-" : null}
      </span>
    </div>
  );
}

function DocumentTable(props: {
  documents: DocumentCard[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="document-table">
      <div className="table-row header">
        <span>Файл</span>
        <span>Тип</span>
        <span>Статус</span>
        <span>Прогресс</span>
        <span>Поля</span>
        <span>Обновлен</span>
      </div>
      {props.documents.map((doc) => (
        <button
          key={doc.id}
          className={`table-row ${props.selectedId === doc.id ? "selected" : ""}`}
          onClick={() => props.onSelect(doc.id)}
        >
          <strong>{doc.filename}</strong>
          <span>{doc.document_type}</span>
          <Badge tone={statusTone(doc.status)}>{doc.status}</Badge>
          <span className="progress-cell">
            <i style={{ width: `${doc.progress}%` }} />
            {doc.progress}%
          </span>
          <span>
            {doc.field_count}
            {!doc.ready_to_export && ` / ${doc.null_count + doc.review_count} check`}
          </span>
          <span>{formatDate(doc.updated_at)}</span>
        </button>
      ))}
    </div>
  );
}

function EventPanel(props: { events: EventItem[] }) {
  return (
    <section className="panel event-panel">
      <div className="panel-head compact">
        <div>
          <h2>Логи событий</h2>
          <p>Последние события системы</p>
        </div>
      </div>
      <div className="event-list">
        {props.events.slice(0, 60).map((event, index) => (
          <div key={`${event.timestamp}-${index}`} className="event-item">
            <Badge tone={eventTone(event)}>{event.level ?? event.status ?? "INFO"}</Badge>
            <strong>{event.message ?? event.type ?? event.event ?? "event"}</strong>
            <span>{event.document ?? event.filename ?? ""}</span>
            <time>{event.timestamp ? formatDate(event.timestamp) : ""}</time>
          </div>
        ))}
      </div>
    </section>
  );
}

function ArtifactPreview(props: {
  documentId: string | null;
  artifact: ArtifactFile | null;
  artifactText: string;
}) {
  if (!props.documentId || !props.artifact) {
    return <div className="empty-preview">Здесь будет preview выбранного файла.</div>;
  }
  if (props.artifact.preview_type === "image") {
    return <img className="image-preview" src={api.artifactUrl(props.documentId, props.artifact.relative_path)} alt="" />;
  }
  if (props.artifact.preview_type === "pdf") {
    return (
      <iframe
        className="pdf-preview"
        src={api.artifactUrl(props.documentId, props.artifact.relative_path)}
        title={props.artifact.relative_path}
      />
    );
  }
  if (props.artifact.preview_type === "text") {
    return <pre className="text-preview">{props.artifactText || "Загружаю preview..."}</pre>;
  }
  return (
    <a className="primary-button" href={api.artifactUrl(props.documentId, props.artifact.relative_path)} target="_blank">
      Открыть файл
    </a>
  );
}

function MetricCard(props: { label: string; value: number | string; tone: "neutral" | "success" | "warning" | "danger" | "info" }) {
  return (
    <article className={`metric-card ${props.tone}`}>
      <span>{props.label}</span>
      <strong>{props.value}</strong>
    </article>
  );
}

function Badge(props: { tone: "neutral" | "success" | "warning" | "danger" | "info"; children: ReactNode }) {
  return <span className={`badge ${props.tone}`}>{props.children}</span>;
}

function statusTone(status: string): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "completed" || status === "exported") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "processing") {
    return "warning";
  }
  return "info";
}

function eventTone(event: EventItem): "neutral" | "success" | "warning" | "danger" | "info" {
  const value = String(event.level ?? event.status ?? "").toLowerCase();
  if (value.includes("error") || value.includes("failed")) {
    return "danger";
  }
  if (value.includes("warn")) {
    return "warning";
  }
  if (value.includes("ok") || value.includes("success")) {
    return "success";
  }
  return "info";
}

function valueToString(value: unknown): string {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function formatDate(value: string): string {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function shortPath(path: string): string {
  if (!path) {
    return "not detected";
  }
  const normalized = path.replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.slice(-2).join("/");
}

export default App;
