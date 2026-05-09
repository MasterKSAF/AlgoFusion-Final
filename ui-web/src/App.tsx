import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
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

const TABS: Array<{ id: ViewId; label: string; hint: string }> = [
  { id: "overview", label: "Обзор", hint: "сводка" },
  { id: "documents", label: "Документы", hint: "136 файлов" },
  { id: "review", label: "Проверка", hint: "поля" },
  { id: "artifacts", label: "Артефакты", hint: "JSON/PDF/PNG" },
  { id: "events", label: "События", hint: "лог" }
];

type Theme = "light" | "dark";

function App() {
  const [view, setViewState] = useState<ViewId>(() => viewFromHash());
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("algofusion-theme") === "dark" ? "dark" : "light"));
  const [stats, setStats] = useState<Stats>(EMPTY_STATS);
  const [documents, setDocuments] = useState<DocumentCard[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [queue, setQueue] = useState<ExportQueue | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDocument, setSelectedDocument] = useState<DocumentDetail | null>(null);
  const [artifactTree, setArtifactTree] = useState<ArtifactTree | null>(null);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactFile | null>(null);
  const [artifactText, setArtifactText] = useState("");
  const [fieldDraft, setFieldDraft] = useState<Record<string, unknown>>({});
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [onlyProblems, setOnlyProblems] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
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
      setSelectedId((current) => current ?? docsData.documents[0]?.id ?? null);
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
      setError(null);
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
    if (!selectedId) {
      return;
    }
    setSaving(true);
    try {
      await api.saveReview(selectedId, fieldDraft);
      await loadDocument(selectedId);
      await loadDashboard();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    void loadDashboard();
    const handle = window.setInterval(() => void loadDashboard(), 20_000);
    return () => window.clearInterval(handle);
  }, []);

  useEffect(() => {
    const onHashChange = () => setViewState(viewFromHash());
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("algofusion-theme", theme);
  }, [theme]);

  useEffect(() => {
    if (selectedId) {
      void loadDocument(selectedId);
    }
  }, [selectedId]);

  const visibleDocuments = documents.filter((doc) => {
    const text = `${doc.filename} ${doc.document_type} ${doc.status}`.toLowerCase();
    const matchesQuery = !query.trim() || text.includes(query.trim().toLowerCase());
    const matchesType = typeFilter === "all" || doc.document_type === typeFilter;
    const matchesState =
      stateFilter === "all" ||
      doc.status === stateFilter ||
      (stateFilter === "attention" && !doc.ready_to_export) ||
      (stateFilter === "ready" && doc.ready_to_export);
    return matchesQuery && matchesType && matchesState;
  });

  const docTypes = Object.keys(stats.by_type).sort();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">AF</div>
          <div>
            <strong>AlgoFusion 2</strong>
            <span>Pipeline control room</span>
          </div>
        </div>

        <nav className="tab-nav" aria-label="Основные вкладки">
          {TABS.map((tab) => (
            <button key={tab.id} className={view === tab.id ? "active" : ""} onClick={() => setView(tab.id)}>
              <span>{tab.label}</span>
              <small>{tab.hint}</small>
            </button>
          ))}
        </nav>

        <div className="run-card">
          <span>Активный прогон</span>
          <strong title={stats.run_root}>{shortPath(stats.run_root)}</strong>
          <small>{stats.total || 0} документов в индексе</small>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AlgoFusion2 / OCR pipeline v2</p>
            <h1>{tabTitle(view)}</h1>
          </div>
          <div className="topbar-actions">
            {error && <span className="error-pill">{error}</span>}
            <button className="ghost-button theme-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
              {theme === "dark" ? "Светлая тема" : "Тёмная тема"}
            </button>
            <button className="ghost-button" onClick={() => void loadDashboard()}>
              Обновить
            </button>
          </div>
        </header>

        {loading ? (
          <div className="empty-state">Загружаю документы, метрики и артефакты пайплайна...</div>
        ) : (
          <>
            {view === "overview" && (
              <OverviewView
                stats={stats}
                documents={documents}
                events={events}
                queue={queue}
                onOpenReview={() => setView("review")}
                onOpenDocument={(id) => {
                  setSelectedId(id);
                  setView("documents");
                }}
              />
            )}

            {view === "documents" && (
              <DocumentsView
                stats={stats}
                documents={visibleDocuments}
                selectedDocument={selectedDocument}
                selectedId={selectedId}
                docTypes={docTypes}
                query={query}
                typeFilter={typeFilter}
                stateFilter={stateFilter}
                onQuery={setQuery}
                onTypeFilter={setTypeFilter}
                onStateFilter={setStateFilter}
                onSelect={setSelectedId}
                onOpenArtifacts={() => setView("artifacts")}
              />
            )}

            {view === "review" && (
              <ReviewView
                queue={queue}
                selectedId={selectedId}
                selectedDocument={selectedDocument}
                fieldDraft={fieldDraft}
                onlyProblems={onlyProblems}
                saving={saving}
                onOnlyProblems={setOnlyProblems}
                onSelect={setSelectedId}
                onDraft={setFieldDraft}
                onSave={() => void saveReviewDraft()}
              />
            )}

            {view === "artifacts" && (
              <ArtifactsView
                documents={visibleDocuments.length ? visibleDocuments : documents}
                selectedId={selectedId}
                selectedDocument={selectedDocument}
                artifactTree={artifactTree}
                selectedArtifact={selectedArtifact}
                artifactText={artifactText}
                query={query}
                onQuery={setQuery}
                onSelectDocument={setSelectedId}
                onSelectArtifact={(file) => void openArtifact(file)}
              />
            )}

            {view === "events" && <EventsView events={events} stats={stats} />}
          </>
        )}
      </main>
    </div>
  );
}

function setView(view: ViewId) {
  window.location.hash = view;
}

function viewFromHash(): ViewId {
  const raw = window.location.hash.replace(/^#\/?/, "");
  return TABS.some((tab) => tab.id === raw) ? (raw as ViewId) : "overview";
}

function OverviewView(props: {
  stats: Stats;
  documents: DocumentCard[];
  events: EventItem[];
  queue: ExportQueue | null;
  onOpenReview: () => void;
  onOpenDocument: (id: string) => void;
}) {
  const problemDocs = (props.queue?.requires_attention ?? props.documents.filter((doc) => !doc.ready_to_export)).slice(0, 8);
  const readyRatio = props.stats.total ? Math.round((props.stats.ready_to_export / props.stats.total) * 100) : 0;

  return (
    <section className="view-stack">
      <div className="metric-grid">
        <MetricCard label="Всего документов" value={props.stats.total} tone="neutral" />
        <MetricCard label="Финальный JSON" value={props.stats.completed} tone="success" />
        <MetricCard label="Готово к экспорту" value={props.stats.ready_to_export} tone="info" />
        <MetricCard label="Требуют проверки" value={props.stats.requires_attention} tone="warning" />
        <MetricCard label="Ошибки" value={props.stats.failed} tone="danger" />
      </div>

      <div className="overview-grid">
        <section className="panel hero-panel">
          <div>
            <p className="eyebrow">Готовность набора</p>
            <h2>{readyRatio}% документов без ручной проверки</h2>
            <p>
              UI читает актуальный run-root из `shared/files`, показывает итоговые JSON, проблемные поля и артефакты
              каждого документа.
            </p>
          </div>
          <div className="donut" style={{ "--value": `${readyRatio}%` } as CSSProperties}>
            <strong>{readyRatio}%</strong>
            <span>готово</span>
          </div>
        </section>

        <section className="panel type-panel">
          <PanelTitle title="Типы документов" subtitle="Распределение по текущему прогону" />
          <div className="type-list">
            {Object.entries(props.stats.by_type).map(([type, count]) => (
              <div key={type} className="type-row">
                <span>{documentTypeLabel(type)}</span>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel attention-panel">
          <div className="panel-head">
            <PanelTitle title="Что проверить первым" subtitle="Документы с null/review/invalid полями" />
            <button className="ghost-button" onClick={props.onOpenReview}>
              Открыть проверку
            </button>
          </div>
          <div className="compact-list">
            {problemDocs.map((doc) => (
              <button key={doc.id} onClick={() => props.onOpenDocument(doc.id)}>
                <strong title={doc.filename}>{displayDocumentName(doc.filename)}</strong>
                <span>{documentTypeLabel(doc.document_type)}</span>
                <Badge tone={doc.invalid_count ? "danger" : "warning"}>
                  {doc.null_count + doc.review_count + doc.invalid_count} полей
                </Badge>
              </button>
            ))}
            {!problemDocs.length && <div className="empty-inline">Нет документов, требующих проверки.</div>}
          </div>
        </section>

        <EventPanel events={props.events.slice(0, 8)} compact />
      </div>
    </section>
  );
}

function DocumentsView(props: {
  stats: Stats;
  documents: DocumentCard[];
  selectedDocument: DocumentDetail | null;
  selectedId: string | null;
  docTypes: string[];
  query: string;
  typeFilter: string;
  stateFilter: string;
  onQuery: (value: string) => void;
  onTypeFilter: (value: string) => void;
  onStateFilter: (value: string) => void;
  onSelect: (id: string) => void;
  onOpenArtifacts: () => void;
}) {
  return (
    <section className="documents-layout">
      <section className="panel">
        <div className="panel-head filters-head">
          <PanelTitle
            title="Документы"
            subtitle={`${props.documents.length} из ${props.stats.total} в текущем фильтре`}
            info="Здесь можно быстро найти документ, отфильтровать тип и открыть его итоговый JSON, поля и артефакты."
          />
          <div className="filters">
            <input
              value={props.query}
              placeholder="Поиск по имени, типу, статусу"
              onChange={(event) => props.onQuery(event.target.value)}
            />
            <select value={props.typeFilter} onChange={(event) => props.onTypeFilter(event.target.value)}>
              <option value="all">Все типы</option>
              {props.docTypes.map((type) => (
                <option key={type} value={type}>
                  {documentTypeLabel(type)}
                </option>
              ))}
            </select>
            <select value={props.stateFilter} onChange={(event) => props.onStateFilter(event.target.value)}>
              <option value="all">Все статусы</option>
              <option value="ready">Готовые</option>
              <option value="attention">Требуют проверки</option>
              <option value="completed">Завершённые</option>
              <option value="failed">С ошибкой</option>
              <option value="processing">В обработке</option>
            </select>
          </div>
        </div>
        <DocumentTable documents={props.documents} selectedId={props.selectedId} onSelect={props.onSelect} />
      </section>

      <DocumentSidePanel document={props.selectedDocument} onOpenArtifacts={props.onOpenArtifacts} />
    </section>
  );
}

function ReviewView(props: {
  queue: ExportQueue | null;
  selectedId: string | null;
  selectedDocument: DocumentDetail | null;
  fieldDraft: Record<string, unknown>;
  onlyProblems: boolean;
  saving: boolean;
  onOnlyProblems: (value: boolean) => void;
  onSelect: (id: string) => void;
  onDraft: (value: Record<string, unknown>) => void;
  onSave: () => void;
}) {
  const attention = props.queue?.requires_attention ?? [];
  const ready = props.queue?.ready ?? [];
  const queueDocs = [...attention, ...ready];

  return (
    <section className="review-layout">
      <section className="panel queue-panel">
        <div className="panel-head compact">
          <PanelTitle
            title="Очередь проверки"
            subtitle={`${attention.length} требуют внимания, ${ready.length} готовы`}
            info="Слева документы с проблемными полями. Справа можно внести ручную правку, она сохраняется как отдельный review override."
          />
        </div>
        <div className="queue-list">
          {queueDocs.map((doc) => (
            <button
              key={doc.id}
              className={`queue-item ${props.selectedId === doc.id ? "active" : ""}`}
              onClick={() => props.onSelect(doc.id)}
            >
              <strong title={doc.filename}>{displayDocumentName(doc.filename)}</strong>
              <span>{documentTypeLabel(doc.document_type)}</span>
              <div className="badge-row">
                {doc.ready_to_export ? <Badge tone="success">готов</Badge> : <Badge tone="warning">проверить</Badge>}
                {doc.null_count > 0 && <Badge tone="warning">пусто {doc.null_count}</Badge>}
                {doc.review_count > 0 && <Badge tone="danger">проверка {doc.review_count}</Badge>}
                {doc.invalid_count > 0 && <Badge tone="danger">ошибка {doc.invalid_count}</Badge>}
              </div>
            </button>
          ))}
        </div>
      </section>

      <FieldEditor
        document={props.selectedDocument}
        draft={props.fieldDraft}
        onlyProblems={props.onlyProblems}
        saving={props.saving}
        onOnlyProblems={props.onOnlyProblems}
        onDraft={props.onDraft}
        onSave={props.onSave}
      />
    </section>
  );
}

function ArtifactsView(props: {
  documents: DocumentCard[];
  selectedId: string | null;
  selectedDocument: DocumentDetail | null;
  artifactTree: ArtifactTree | null;
  selectedArtifact: ArtifactFile | null;
  artifactText: string;
  query: string;
  onQuery: (value: string) => void;
  onSelectDocument: (id: string) => void;
  onSelectArtifact: (file: ArtifactFile) => void;
}) {
  const artifactQuery = props.query.trim().toLowerCase();
  const files = (props.artifactTree?.files ?? []).filter(
    (file) =>
      !artifactQuery ||
      file.relative_path.toLowerCase().includes(artifactQuery) ||
      file.stage.toLowerCase().includes(artifactQuery)
  );

  return (
    <section className="artifacts-layout">
      <section className="panel artifact-document-panel">
        <div className="panel-head compact">
          <PanelTitle
            title="Документ"
            subtitle="Выбор источника артефактов"
            info="Артефакты читаются из папки выбранного документа: final JSON, OCR, изображения страниц, кропы и служебные файлы."
          />
        </div>
        <select
          className="wide-select"
          value={props.selectedId ?? ""}
          onChange={(event) => props.onSelectDocument(event.target.value)}
        >
          {props.documents.map((doc) => (
            <option key={doc.id} value={doc.id}>
              {displayDocumentName(doc.filename)}
            </option>
          ))}
        </select>
        {props.selectedDocument && (
          <div className="doc-card">
            <strong title={props.selectedDocument.filename}>{displayDocumentName(props.selectedDocument.filename)}</strong>
            <span>{props.selectedDocument.base_path}</span>
            <div className="badge-row">
              <Badge tone="info">{documentTypeLabel(props.selectedDocument.document_type)}</Badge>
              <Badge tone={props.selectedDocument.ready_to_export ? "success" : "warning"}>
                {props.selectedDocument.ready_to_export ? "готов" : "проверить"}
              </Badge>
              <Badge tone="neutral">{props.selectedDocument.field_count} полей</Badge>
            </div>
          </div>
        )}
      </section>

      <section className="panel artifact-list-panel">
        <div className="panel-head compact">
          <PanelTitle title="Файлы" subtitle={`${files.length} артефактов`} />
          <input value={props.query} placeholder="Фильтр: final_json, ocr, png..." onChange={(event) => props.onQuery(event.target.value)} />
        </div>
        <div className="artifact-table">
          {files.map((file) => (
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
          {!files.length && <div className="empty-inline">Для выбранного документа артефакты не найдены.</div>}
        </div>
      </section>

      <section className="panel preview-panel">
        <div className="panel-head compact">
          <PanelTitle title="Просмотр" subtitle={props.selectedArtifact?.relative_path ?? "Выберите файл"} />
        </div>
        <ArtifactPreview documentId={props.selectedId} artifact={props.selectedArtifact} artifactText={props.artifactText} />
      </section>
    </section>
  );
}

function EventsView(props: { events: EventItem[]; stats: Stats }) {
  return (
    <section className="events-layout">
      <div className="metric-grid compact">
        <MetricCard label="Завершены" value={props.stats.completed} tone="success" />
        <MetricCard label="В обработке" value={props.stats.processing} tone="warning" />
        <MetricCard label="Ошибки" value={props.stats.failed} tone="danger" />
        <MetricCard label="События" value={props.events.length} tone="info" />
      </div>
      <EventPanel events={props.events} />
    </section>
  );
}

function DocumentSidePanel(props: { document: DocumentDetail | null; onOpenArtifacts: () => void }) {
  if (!props.document) {
    return <aside className="panel side-panel empty-panel">Выберите документ, чтобы увидеть поля и путь к JSON.</aside>;
  }

  const problemFields = props.document.fields.filter((field) => field.effective_state !== "ok");
  const previewFields = problemFields.length ? problemFields.slice(0, 12) : props.document.fields.slice(0, 12);

  return (
    <aside className="panel side-panel">
      <div className="panel-head compact">
        <PanelTitle
          title={displayDocumentName(props.document.filename)}
          subtitle={props.document.base_path}
          info="Быстрая карточка выбранного документа: статус, путь к final JSON и первые проблемные поля."
        />
      </div>
      <div className="side-content">
        <div className="badge-row">
          <Badge tone="info">{documentTypeLabel(props.document.document_type)}</Badge>
          <Badge tone={props.document.ready_to_export ? "success" : "warning"}>
            {props.document.ready_to_export ? "готов" : "проверить"}
          </Badge>
          <Badge tone="neutral">{props.document.field_count} полей</Badge>
        </div>
        <div className="path-box">{props.document.final_json_path ?? "Final JSON не найден"}</div>
        <button className="primary-button" onClick={props.onOpenArtifacts}>
          Открыть артефакты
        </button>
        <div className="mini-fields">
          {previewFields.map((field) => (
            <div key={field.path}>
              <span title={field.path}>{fieldDisplayLabel(field)}</span>
              <strong>{valueToString(field.effective_value ?? field.value) || "пусто"}</strong>
              <Badge tone={fieldTone(field.effective_state)}>{fieldStateLabel(field.effective_state)}</Badge>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

function FieldEditor(props: {
  document: DocumentDetail | null;
  draft: Record<string, unknown>;
  onlyProblems: boolean;
  saving: boolean;
  onOnlyProblems: (value: boolean) => void;
  onDraft: (value: Record<string, unknown>) => void;
  onSave: () => void;
}) {
  if (!props.document) {
    return <section className="panel field-editor empty-panel">Выберите документ из очереди слева.</section>;
  }

  const problemFields = props.document.fields.filter((field) => field.effective_state !== "ok" || field.has_draft);
  const fields = props.onlyProblems ? problemFields : props.document.fields;

  return (
    <section className="panel field-editor">
      <div className="panel-head editor-head">
        <PanelTitle
          title={displayDocumentName(props.document.filename)}
          subtitle={`${documentTypeLabel(props.document.document_type)} / ${props.document.field_count} полей`}
          info="Русская строка показывает смысл поля, технический путь под ней нужен для разработчика и валидатора."
        />
        <div className="editor-actions">
          <label className="toggle">
            <input
              type="checkbox"
              checked={props.onlyProblems}
              onChange={(event) => props.onOnlyProblems(event.target.checked)}
            />
            только проблемные
          </label>
          <button className="primary-button" disabled={props.saving} onClick={props.onSave}>
            {props.saving ? "Сохраняю..." : "Сохранить ручные правки"}
          </button>
          <small className="editor-note">Правки пишутся в review override и не затирают исходный final JSON.</small>
        </div>
      </div>

      <div className="fields-table">
        <div className="field-row header">
          <span>Поле</span>
          <span>Текущее значение</span>
          <span>Правка оператора</span>
          <span>Статус</span>
        </div>
        {fields.map((field) => (
          <FieldRow key={field.path} field={field} draft={props.draft} onDraft={props.onDraft} />
        ))}
        {!fields.length && <div className="empty-inline">Проблемных полей нет.</div>}
      </div>
    </section>
  );
}

function FieldRow(props: {
  field: FieldValue;
  draft: Record<string, unknown>;
  onDraft: (value: Record<string, unknown>) => void;
}) {
  const currentDraft = props.draft[props.field.path] ?? props.field.draft_value ?? "";

  return (
    <div className={`field-row ${props.field.effective_state}`}>
      <div>
        <strong>{fieldDisplayLabel(props.field)}</strong>
        <small>{props.field.path}</small>
      </div>
      <span className="field-current">{valueToString(props.field.value) || "null"}</span>
      <input
        value={valueToString(currentDraft)}
        placeholder={valueToString(props.field.value)}
        onChange={(event) => props.onDraft({ ...props.draft, [props.field.path]: event.target.value })}
      />
      <div className="badge-row">
        <Badge tone={fieldTone(props.field.effective_state)}>{fieldStateLabel(props.field.effective_state)}</Badge>
        {props.field.has_draft && <Badge tone="success">правка</Badge>}
      </div>
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
      <div className="document-row header">
        <span>Файл</span>
        <span>Тип</span>
        <span>Статус</span>
        <span>Готовность</span>
        <span>Поля</span>
        <span>Обновлён</span>
      </div>
      {props.documents.map((doc) => (
        <button
          key={doc.id}
          className={`document-row ${props.selectedId === doc.id ? "selected" : ""}`}
          onClick={() => props.onSelect(doc.id)}
        >
          <strong title={doc.filename}>{displayDocumentName(doc.filename)}</strong>
          <span>{documentTypeLabel(doc.document_type)}</span>
          <Badge tone={statusTone(doc.status)}>{statusLabel(doc.status)}</Badge>
          <span className="progress-cell">
            <i style={{ width: `${Math.max(4, doc.progress)}%` }} />
            {doc.progress}%
          </span>
          <span>
            {doc.field_count}
            {!doc.ready_to_export ? ` / проверить ${doc.null_count + doc.review_count + doc.invalid_count}` : ""}
          </span>
          <span>{formatDate(doc.updated_at)}</span>
        </button>
      ))}
      {!props.documents.length && <div className="empty-inline">Документы по фильтру не найдены.</div>}
    </div>
  );
}

function EventPanel(props: { events: EventItem[]; compact?: boolean }) {
  return (
    <section className={`panel event-panel ${props.compact ? "compact" : ""}`}>
      <div className="panel-head compact">
        <PanelTitle
          title="События"
          subtitle="Последние сообщения пайплайна и API"
          info="Короткий технический журнал: статус, сообщение, документ и время. Подробные JSON-артефакты смотрите во вкладке «Артефакты»."
        />
      </div>
      <div className="event-list">
        {props.events.map((event, index) => (
          <div key={`${event.timestamp}-${index}`} className="event-item">
            <Badge tone={eventTone(event)}>{eventStatusLabel(event)}</Badge>
            <strong title={event.message ?? event.type ?? event.event ?? "event"}>{eventMessage(event)}</strong>
            <span title={event.document ?? event.filename ?? ""}>{displayDocumentName(event.document ?? event.filename ?? "")}</span>
            <time>{event.timestamp ? formatDate(event.timestamp) : ""}</time>
          </div>
        ))}
        {!props.events.length && <div className="empty-inline">Событий пока нет.</div>}
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
    return <div className="empty-state">Выберите JSON, PNG, PDF или TXT из списка слева.</div>;
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
    <a className="primary-button download-link" href={api.artifactUrl(props.documentId, props.artifact.relative_path)} target="_blank">
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

function PanelTitle(props: { title: string; subtitle?: string; info?: string }) {
  return (
    <div className="panel-title">
      <div className="title-line">
        <h2>{props.title}</h2>
        {props.info && <InfoDot text={props.info} />}
      </div>
      {props.subtitle && <p title={props.subtitle}>{props.subtitle}</p>}
    </div>
  );
}

function InfoDot(props: { text: string }) {
  return (
    <span className="info-dot" tabIndex={0} aria-label={props.text}>
      i
      <span className="info-tooltip">{props.text}</span>
    </span>
  );
}

function Badge(props: { tone: "neutral" | "success" | "warning" | "danger" | "info"; children: ReactNode }) {
  return <span className={`badge ${props.tone}`}>{props.children}</span>;
}

function tabTitle(view: ViewId): string {
  const titleByView: Record<ViewId, string> = {
    overview: "Рабочий обзор",
    documents: "Документы",
    review: "Проверка полей",
    artifacts: "Артефакты",
    events: "События"
  };
  return titleByView[view];
}

function documentTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    waybill: "Накладная",
    invoice: "Счёт",
    payment_order: "Платёжка",
    account_prot: "Акт/протокол",
    unknown: "Не определён"
  };
  return labels[type] ?? type;
}

const FIELD_SEGMENT_LABELS: Record<string, string> = {
  document: "Документ",
  doc: "Документ",
  header: "Шапка",
  footer: "Подвал",
  totals: "Итоги",
  total: "Итого",
  summary: "Итоги",
  amount: "сумма",
  total_amount: "итоговая сумма",
  amount_without_vat: "сумма без НДС",
  amount_with_vat: "сумма с НДС",
  vat: "НДС",
  vat_rate: "ставка НДС",
  vat_amount: "сумма НДС",
  vat_total: "итого НДС",
  vat_total_words: "НДС прописью",
  nds: "НДС",
  cost_with_vat: "стоимость с НДС",
  cost_with_vat_total: "итого с НДС",
  cost_with_vat_total_words: "итого с НДС прописью",
  currency: "валюта",
  number: "номер",
  no: "номер",
  date: "дата",
  document_type: "тип документа",
  document_series: "серия документа",
  document_number: "номер документа",
  contract: "договор",
  contract_number: "номер договора",
  contract_date: "дата договора",
  basis: "основание",
  invoice: "Счёт",
  waybill: "Накладная",
  payment_order: "Платёжное поручение",
  account_prot: "Акт / протокол",
  payer: "Плательщик",
  payee: "Получатель",
  buyer: "Покупатель",
  seller: "Поставщик",
  supplier: "Поставщик",
  customer: "Заказчик",
  consignee: "Грузополучатель",
  consignor: "Грузоотправитель",
  receiver: "Получатель",
  sender: "Отправитель",
  shipper: "Грузоотправитель",
  organization: "организация",
  company: "организация",
  name: "наименование",
  title: "название",
  full_name: "полное наименование",
  tax_id: "УНП",
  taxpayer_id: "УНП",
  unp: "УНП",
  address: "адрес",
  legal_address: "юридический адрес",
  bank: "банк",
  bank_name: "банк",
  account: "счёт",
  account_number: "номер счёта",
  iban: "IBAN",
  bic: "БИК",
  bik: "БИК",
  okpo: "ОКПО",
  items: "Товары",
  item: "Товар",
  goods: "Товары",
  products: "Товары",
  rows: "Строки",
  table: "Таблица",
  description: "описание",
  product_name: "наименование товара",
  quantity: "количество",
  qty: "количество",
  quantity_total: "итого количество",
  unit: "ед. изм.",
  unit_name: "ед. изм.",
  price: "цена",
  unit_price: "цена за единицу",
  cost: "стоимость",
  cost_total: "итого стоимость",
  sum: "сумма",
  line_number: "номер строки",
  country: "страна",
  origin_country: "страна происхождения",
  tnved: "ТН ВЭД",
  barcode: "штрихкод",
  pack: "упаковка",
  places: "мест",
  weight: "вес",
  gross_weight: "вес брутто",
  net_weight: "вес нетто",
  received_by: "получил",
  released_by: "отпустил",
  handed_by: "сдал",
  accepted_for_delivery: "принял к перевозке",
  documents_transferred: "документы переданы",
  approved_by: "утвердил",
  approvals: "Подписи и ответственные",
  signature: "подпись",
  signer: "подписант",
  position: "должность",
  comment: "комментарий",
  note: "примечание",
  warning: "предупреждение",
  confidence: "уверенность",
  source: "источник"
};

function fieldDisplayLabel(field: FieldValue): string {
  const rawPath = field.path || field.label;
  const segments = rawPath
    .replace(/\[(\d+)\]/g, ".$1")
    .split(/[./]/)
    .map((segment) => segment.trim())
    .filter(Boolean);

  if (!segments.length) {
    return humanizeSegment(field.label || rawPath);
  }

  const labels: string[] = [];
  for (const segment of segments) {
    if (/^\d+$/.test(segment)) {
      const index = Number(segment) + 1;
      const previous = labels.at(-1);
      if (previous === "Товары" || previous === "Строки" || previous === "Таблица") {
        labels[labels.length - 1] = `Товар ${index}`;
      } else {
        labels.push(`№ ${index}`);
      }
      continue;
    }
    labels.push(FIELD_SEGMENT_LABELS[segment.toLowerCase()] ?? humanizeSegment(segment));
  }

  return labels.join(" / ");
}

function humanizeSegment(segment: string): string {
  return segment
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    uploaded: "загружен",
    processing: "в работе",
    completed: "готов",
    exported: "экспорт",
    failed: "ошибка"
  };
  return labels[status] ?? status;
}

function fieldStateLabel(state: string): string {
  const labels: Record<string, string> = {
    ok: "ок",
    null: "пусто",
    empty: "пусто",
    review: "проверить",
    invalid: "ошибка"
  };
  return labels[state] ?? state;
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

function fieldTone(state: string): "neutral" | "success" | "warning" | "danger" | "info" {
  if (state === "ok") {
    return "success";
  }
  if (state === "null" || state === "empty") {
    return "warning";
  }
  if (state === "review" || state === "invalid") {
    return "danger";
  }
  return "neutral";
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

function eventStatusLabel(event: EventItem): string {
  const value = String(event.level ?? event.status ?? "info").toLowerCase();
  if (value.includes("error") || value.includes("failed")) {
    return "ошибка";
  }
  if (value.includes("warn")) {
    return "важно";
  }
  if (value.includes("ok") || value.includes("success") || value.includes("completed")) {
    return "ок";
  }
  return "инфо";
}

function eventMessage(event: EventItem): string {
  return event.message ?? event.type ?? event.event ?? "событие";
}

function displayDocumentName(path: string): string {
  if (!path) {
    return "";
  }
  const normalized = path.replaceAll("\\", "/");
  return normalized.split("/").filter(Boolean).at(-1) ?? path;
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
    return "run-root не найден";
  }
  const normalized = path.replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.slice(-2).join("/");
}

export default App;
