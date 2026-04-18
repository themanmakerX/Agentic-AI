const state = {
  rootPath: "",
  buildJobId: null,
  buildState: "idle",
  repoInfo: null,
  graph: null,
  selection: null,
  currentView: "overview",
  currentSearchFocus: "",
  zoom: 1,
  panDrag: null,
  nodePositions: new Map(),
};

const els = {
  rootPath: document.getElementById("root-path"),
  heroRoot: document.getElementById("hero-root"),
  buildForm: document.getElementById("build-form"),
  refreshButton: document.getElementById("refresh-button"),
  statusText: document.getElementById("status-text"),
  statusMeta: document.getElementById("status-meta"),
  statusWebLink: document.getElementById("status-web-link"),
  statusApiLink: document.getElementById("status-api-link"),
  progressBar: document.getElementById("progress-bar"),
  metricState: document.getElementById("metric-state"),
  metricDirectories: document.getElementById("metric-directories"),
  metricFiles: document.getElementById("metric-files"),
  metricSymbols: document.getElementById("metric-symbols"),
  metricEdges: document.getElementById("metric-edges"),
  metricRegions: document.getElementById("metric-regions"),
  leftRail: document.getElementById("left-rail"),
  rightRail: document.getElementById("right-rail"),
  toggleLeft: document.getElementById("toggle-left"),
  toggleRight: document.getElementById("toggle-right"),
  toggleLeftInline: document.getElementById("toggle-left-inline"),
  toggleRightInline: document.getElementById("toggle-right-inline"),
  graphMeta: document.getElementById("graph-meta"),
  graphScroll: document.getElementById("graph-scroll"),
  graphCanvas: document.getElementById("graph-canvas"),
  graphSvg: document.getElementById("graph-svg"),
  minimap: document.getElementById("minimap"),
  centerSelectionButton: document.getElementById("center-selection-button"),
  zoomInButton: document.getElementById("zoom-in-button"),
  zoomOutButton: document.getElementById("zoom-out-button"),
  fitButton: document.getElementById("fit-button"),
  resetButton: document.getElementById("reset-button"),
  showOverviewButton: document.getElementById("show-overview-button"),
  showFullButton: document.getElementById("show-full-button"),
  searchInput: document.getElementById("search-input"),
  searchResults: document.getElementById("search-results"),
  moduleGroups: document.getElementById("module-groups"),
  fileList: document.getElementById("file-list"),
  selectionEmpty: document.getElementById("selection-empty"),
  selectionCard: document.getElementById("selection-card"),
  selectionLanguage: document.getElementById("selection-language"),
  selectionTitle: document.getElementById("selection-title"),
  selectionSubtitle: document.getElementById("selection-subtitle"),
  selectionCounts: document.getElementById("selection-counts"),
  selectionSymbols: document.getElementById("selection-symbols"),
  selectionOutgoing: document.getElementById("selection-outgoing"),
  selectionIncoming: document.getElementById("selection-incoming"),
  pathResults: document.getElementById("path-results"),
  focusNeighborsButton: document.getElementById("focus-neighbors-button"),
  findPathsButton: document.getElementById("find-paths-button"),
  askAboutFileButton: document.getElementById("ask-about-file-button"),
  questionInput: document.getElementById("question-input"),
  askButton: document.getElementById("ask-button"),
  answerBox: document.getElementById("answer-box"),
};

function formatCount(value) {
  return Number(value || 0).toLocaleString();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function topDirectory(filePath) {
  const normalized = String(filePath || "").replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.length > 1 ? parts[0] : ".";
}

function shortLabel(filePath) {
  const normalized = String(filePath || "").replaceAll("\\", "/");
  const parts = normalized.split("/");
  return parts.slice(-2).join("/");
}

function languageClass(languageId) {
  const language = String(languageId || "").toLowerCase();
  if (language.includes("python")) return "language-python";
  if (language.includes("systemverilog") || language.includes("uvm")) return "language-systemverilog";
  if (language.includes("javascript") || language.includes("typescript") || language.includes("tsx")) return "language-javascript";
  return "language-default";
}

function edgeClass(edgeKind) {
  const kind = String(edgeKind || "").toLowerCase();
  if (kind.includes("call")) return "kind-calls";
  if (kind.includes("reference")) return "kind-references";
  return "kind-imports";
}

function edgeSummary(edge) {
  if (edge.label) return edge.label;
  const parts = Object.entries(edge.kind_counts || {}).map(([kind, count]) => `${kind} x${count}`);
  return parts.join(", ") || edge.primary_kind || "imports";
}

function setStatus(text, meta = "", progress = 0) {
  els.statusText.textContent = text;
  els.statusMeta.textContent = meta;
  els.progressBar.style.width = `${Math.max(0, Math.min(progress, 100))}%`;
}

function setStatusLinks(status) {
  if (status?.web_url) {
    els.statusWebLink.href = status.web_url;
    els.statusWebLink.classList.remove("hidden");
  } else {
    els.statusWebLink.classList.add("hidden");
  }
  if (status?.api_url) {
    els.statusApiLink.href = status.api_url;
    els.statusApiLink.classList.remove("hidden");
  } else {
    els.statusApiLink.classList.add("hidden");
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json();
}

function updateMetrics(info, status = null) {
  state.repoInfo = info;
  const counts = info?.counts || {};
  els.heroRoot.textContent = info?.root_path || state.rootPath || "No codebase selected";
  els.metricState.textContent = status?.state || state.buildState || "ready";
  els.metricDirectories.textContent = formatCount(counts.directories);
  els.metricFiles.textContent = formatCount(counts.files);
  els.metricSymbols.textContent = formatCount(counts.symbols);
  els.metricEdges.textContent = formatCount(counts.edges);
  els.metricRegions.textContent = formatCount(info?.top_hubs ? Math.max(1, Math.ceil((counts.files || 0) / 25)) : 0);
}

function renderModuleGroups(nodes) {
  const grouped = new Map();
  nodes.forEach((node) => {
    const key = topDirectory(node.path);
    if (!grouped.has(key)) {
      grouped.set(key, { count: 0, symbols: 0 });
    }
    const bucket = grouped.get(key);
    bucket.count += 1;
    bucket.symbols += Number(node.symbol_count || 0);
  });
  const items = Array.from(grouped.entries())
    .sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0]))
    .slice(0, 12);
  els.moduleGroups.innerHTML = items
    .map(
      ([name, bucket]) => `
        <button type="button" class="chip" data-group="${escapeHtml(name)}">
          ${escapeHtml(name)}
          <small>${bucket.count} files</small>
        </button>`
    )
    .join("") || '<div class="muted">No module groups yet.</div>';
  els.moduleGroups.querySelectorAll(".chip").forEach((button) => {
    button.addEventListener("click", async () => {
      const group = button.dataset.group;
      if (!group) return;
      state.currentSearchFocus = group;
      const graphResponse = await api(
        `/api/graph_entities?root_path=${encodeURIComponent(state.rootPath)}&target=${encodeURIComponent(group)}&depth=1&limit=200`
      );
      state.currentView = "module";
      renderGraph(graphResponse.graph);
      renderFileList(graphResponse.graph.nodes);
    });
  });
}

function renderFileList(nodes) {
  els.fileList.innerHTML = nodes
    .slice(0, 140)
    .map(
      (node) => `
        <div class="file-item" data-path="${escapeHtml(node.path)}" title="${escapeHtml(node.path)}">
          <strong>${escapeHtml(shortLabel(node.path))}</strong>
          <small>${escapeHtml(node.directory)} | ${escapeHtml(node.language_id)} | symbols ${node.symbol_count}</small>
        </div>`
    )
    .join("") || '<div class="muted">No indexed files yet.</div>';
  els.fileList.querySelectorAll(".file-item").forEach((item) => {
    item.addEventListener("click", async () => {
      const filePath = item.dataset.path;
      if (!filePath) return;
      await loadFocusedGraph(filePath, 1, 220);
      await loadFileDetails(filePath);
    });
  });
}

function renderGraph(graph) {
  state.graph = graph;
  state.nodePositions = new Map();
  const totalCount = Number(graph.total_count || 0);
  const visibleCount = Number(graph.visible_count || 0);
  const graphModeLabel = state.currentView === "overview" ? "overview" : state.currentView;
  els.graphMeta.textContent = graph.truncated
    ? `Showing ${visibleCount} of ${totalCount} files in ${graphModeLabel} mode. Select a node or search to focus deeper.`
    : `Showing ${visibleCount} files in ${graphModeLabel} mode.`;

  const svg = els.graphSvg;
  svg.innerHTML = "";
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  defs.innerHTML = `
    <marker id="arrow-imports" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(13, 107, 255, 0.55)"></path>
    </marker>
    <marker id="arrow-references" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255, 107, 26, 0.6)"></path>
    </marker>
    <marker id="arrow-calls" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(17, 155, 111, 0.62)"></path>
    </marker>`;
  svg.appendChild(defs);
  const edgeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  edgeLayer.setAttribute("id", "edge-layer");
  const nodeLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
  nodeLayer.setAttribute("id", "node-layer");
  svg.append(edgeLayer, nodeLayer);

  const nodes = graph.nodes.slice();
  const edges = graph.edges.slice();
  const grouped = groupBy(nodes, (node) => topDirectory(node.path));
  const groupKeys = Array.from(grouped.keys()).sort();
  const xGap = 300;
  const yGap = 114;
  const maxHeight = 1600;

  groupKeys.forEach((groupKey, groupIndex) => {
    const items = grouped.get(groupKey).sort((a, b) => b.degree - a.degree || b.symbol_count - a.symbol_count || a.path.localeCompare(b.path));
    items.forEach((node, rowIndex) => {
      const x = 180 + groupIndex * xGap;
      const y = 130 + (rowIndex % Math.floor(maxHeight / yGap)) * yGap + Math.floor(rowIndex / Math.floor(maxHeight / yGap)) * 90;
      state.nodePositions.set(String(node.id), { x, y, node });
    });
  });

  edges.forEach((edge) => {
    const source = state.nodePositions.get(String(edge.source_file_id));
    const target = state.nodePositions.get(String(edge.target_file_id));
    if (!source || !target) return;
    const curve = Math.max(40, Math.abs(target.x - source.x) * 0.35);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const kindClass = edgeClass(edge.primary_kind || edge.edge_kind);
    const marker = kindClass === "kind-calls" ? "arrow-calls" : kindClass === "kind-references" ? "arrow-references" : "arrow-imports";
    path.setAttribute("class", `edge-line ${kindClass}`);
    path.dataset.sourcePath = source.node.path;
    path.dataset.targetPath = target.node.path;
    path.dataset.edgeSummary = edgeSummary(edge);
    path.setAttribute("marker-end", `url(#${marker})`);
    path.setAttribute(
      "d",
      `M ${source.x} ${source.y} C ${source.x + curve} ${source.y}, ${target.x - curve} ${target.y}, ${target.x} ${target.y}`
    );
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${edge.source_path} -> ${edge.target_path}\n${edgeSummary(edge)}`;
    path.appendChild(title);
    path.addEventListener("click", async (event) => {
      event.stopPropagation();
      if (edge.source_path) {
        await loadFileDetails(edge.source_path);
      }
      els.pathResults.innerHTML = [
        `<div class="token"><strong>${escapeHtml(edge.source_path || "unknown")}</strong> -> <strong>${escapeHtml(edge.target_path || "unknown")}</strong></div>`,
        `<div class="token">${escapeHtml(edgeSummary(edge))}</div>`,
        ...(edge.sample_refs || []).map((ref) => `<div class="token">${escapeHtml(ref)}</div>`),
      ].join("");
    });
    edgeLayer.appendChild(path);

    if (Number(edge.weight || 0) > 1) {
      const midX = (source.x + target.x) / 2;
      const midY = (source.y + target.y) / 2;
      const edgeBadge = document.createElementNS("http://www.w3.org/2000/svg", "text");
      edgeBadge.setAttribute("class", "node-label");
      edgeBadge.setAttribute("x", String(midX));
      edgeBadge.setAttribute("y", String(midY - 4));
      edgeBadge.setAttribute("text-anchor", "middle");
      edgeBadge.textContent = `${edge.weight}`;
      edgeLayer.appendChild(edgeBadge);
    }
  });

  nodes.forEach((node) => {
    const point = state.nodePositions.get(String(node.id));
    if (!point) return;
    const width = Math.max(150, Math.min(260, 132 + Number(node.symbol_count || 0) * 6 + Number(node.degree || 0) * 5));
    const height = Math.max(54, Math.min(84, 54 + Math.floor(Number(node.symbol_count || 0) / 4)));
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.dataset.path = node.path;
    group.dataset.language = node.language_id || "";
    group.setAttribute("title", node.path);

    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", `graph-node ${languageClass(node.language_id)}`);
    rect.setAttribute("x", String(point.x - width / 2));
    rect.setAttribute("y", String(point.y - height / 2));
    rect.setAttribute("width", String(width));
    rect.setAttribute("height", String(height));
    rect.setAttribute("rx", "18");

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${node.path}\n${node.language_id || "unknown"}\nSymbols: ${node.symbol_count}\nDegree: ${node.degree}`;

    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("class", "node-label");
    label.setAttribute("x", String(point.x - width / 2 + 14));
    label.setAttribute("y", String(point.y - 6));
    label.textContent = shortLabel(node.path);

    const meta = document.createElementNS("http://www.w3.org/2000/svg", "text");
    meta.setAttribute("class", "node-label");
    meta.setAttribute("x", String(point.x - width / 2 + 14));
    meta.setAttribute("y", String(point.y + 15));
    meta.textContent = `${node.language_id || "unknown"} | sym ${node.symbol_count} | deg ${node.degree}`;

    group.append(rect, title, label, meta);
    group.addEventListener("click", async () => {
      await loadFileDetails(node.path);
    });
    nodeLayer.appendChild(group);
  });

  applyZoom();
  fitGraph();
  renderMinimap(nodes);
  if (state.selection?.file?.path) {
    highlightSelection(state.selection.file.path);
  }
}

function applyZoom() {
  els.graphCanvas.style.transform = `scale(${state.zoom})`;
}

function fitGraph() {
  state.zoom = 1;
  applyZoom();
  els.graphScroll.scrollLeft = 0;
  els.graphScroll.scrollTop = 0;
  updateMinimapViewport();
}

function resetGraphView() {
  state.currentView = "overview";
  state.currentSearchFocus = "";
  state.selection = null;
  els.selectionCard.classList.add("hidden");
  els.selectionEmpty.classList.remove("hidden");
  els.pathResults.innerHTML = "";
  fitGraph();
}

function renderMinimap(nodes) {
  const positions = Array.from(state.nodePositions.values());
  if (!positions.length) {
    els.minimap.innerHTML = '<div class="muted" style="padding:12px;">No overview yet.</div>';
    return;
  }
  const width = els.minimap.clientWidth || 300;
  const height = els.minimap.clientHeight || 180;
  const maxX = Math.max(...positions.map((item) => item.x), 1);
  const maxY = Math.max(...positions.map((item) => item.y), 1);
  els.minimap.innerHTML = "";
  positions.forEach((item) => {
    const dot = document.createElement("div");
    dot.className = "minimap-node";
    dot.style.width = "8px";
    dot.style.height = "8px";
    dot.style.left = `${(item.x / maxX) * (width - 10)}px`;
    dot.style.top = `${(item.y / maxY) * (height - 10)}px`;
    dot.style.background = resolveLanguageColor(item.node.language_id);
    els.minimap.appendChild(dot);
  });
  const viewport = document.createElement("div");
  viewport.id = "minimap-viewport";
  viewport.className = "minimap-viewport";
  els.minimap.appendChild(viewport);
  updateMinimapViewport();
}

function updateMinimapViewport() {
  const viewport = document.getElementById("minimap-viewport");
  if (!viewport || !state.graph) return;
  const fullWidth = els.graphCanvas.offsetWidth;
  const fullHeight = els.graphCanvas.offsetHeight;
  const visibleWidth = els.graphScroll.clientWidth;
  const visibleHeight = els.graphScroll.clientHeight;
  const miniWidth = els.minimap.clientWidth || 300;
  const miniHeight = els.minimap.clientHeight || 180;
  viewport.style.width = `${Math.max(26, (visibleWidth / Math.max(fullWidth, 1)) * miniWidth)}px`;
  viewport.style.height = `${Math.max(22, (visibleHeight / Math.max(fullHeight, 1)) * miniHeight)}px`;
  viewport.style.left = `${(els.graphScroll.scrollLeft / Math.max(fullWidth, 1)) * miniWidth}px`;
  viewport.style.top = `${(els.graphScroll.scrollTop / Math.max(fullHeight, 1)) * miniHeight}px`;
}

function resolveLanguageColor(languageId) {
  const name = String(languageId || "").toLowerCase();
  if (name.includes("python")) return "var(--python)";
  if (name.includes("systemverilog") || name.includes("uvm")) return "var(--systemverilog)";
  if (name.includes("javascript") || name.includes("typescript") || name.includes("tsx")) return "var(--javascript)";
  return "var(--neutral)";
}

function groupBy(items, selector) {
  const groups = new Map();
  items.forEach((item) => {
    const key = selector(item);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(item);
  });
  return groups;
}

async function loadRepoInfo() {
  if (!state.rootPath) return;
  const info = await api(`/api/repo_info?root_path=${encodeURIComponent(state.rootPath)}`);
  updateMetrics(info);
  const graphResponse = await api(`/api/graph_entities?root_path=${encodeURIComponent(state.rootPath)}&limit=180`);
  state.currentView = "overview";
  renderGraph(graphResponse.graph);
  renderFileList(graphResponse.graph.nodes);
  renderModuleGroups(graphResponse.graph.nodes);
}

async function loadFocusedGraph(target, depth = 1, limit = 220) {
  const graphResponse = await api(
    `/api/graph_entities?root_path=${encodeURIComponent(state.rootPath)}&target=${encodeURIComponent(target)}&depth=${depth}&limit=${limit}`
  );
  renderGraph(graphResponse.graph);
  renderFileList(graphResponse.graph.nodes);
}

function setSelection(details) {
  state.selection = details;
  els.selectionEmpty.classList.add("hidden");
  els.selectionCard.classList.remove("hidden");
  els.selectionLanguage.textContent = details.file.language_id || "unknown";
  els.selectionTitle.textContent = shortLabel(details.file.path);
  els.selectionSubtitle.textContent = details.file.path;
  els.selectionCounts.innerHTML = [
    `<span>symbols ${details.symbols.length}</span>`,
    `<span>incoming ${details.incoming.length}</span>`,
    `<span>outgoing ${details.outgoing.length}</span>`,
  ].join("");
  els.selectionSymbols.innerHTML = details.symbols
    .map((item) => `<div class="chip" title="${escapeHtml(item.qualified_name || item.name)}">${escapeHtml(item.name)} <small>${escapeHtml(item.kind)}</small></div>`)
    .join("") || '<div class="muted">No symbols detected.</div>';
  els.selectionOutgoing.innerHTML = details.outgoing
    .map((item) => `<div class="token"><strong>${escapeHtml(item.target_path || "unknown")}</strong><br>${escapeHtml(edgeSummary(item))}</div>`)
    .join("") || '<div class="muted">No outgoing dependencies.</div>';
  els.selectionIncoming.innerHTML = details.incoming
    .map((item) => `<div class="token"><strong>${escapeHtml(item.source_path || "unknown")}</strong><br>${escapeHtml(edgeSummary(item))}</div>`)
    .join("") || '<div class="muted">No incoming dependencies.</div>';
  highlightSelection(details.file.path);
}

async function loadFileDetails(filePath) {
  const details = await api(
    `/api/file_details?root_path=${encodeURIComponent(state.rootPath)}&file_path=${encodeURIComponent(filePath)}`
  );
  setSelection(details);
  centerOnFile(filePath);
}

function highlightSelection(filePath) {
  const neighborPaths = new Set();
  if (state.selection) {
    state.selection.outgoing.forEach((item) => {
      if (item.target_path) neighborPaths.add(item.target_path);
    });
    state.selection.incoming.forEach((item) => {
      if (item.source_path) neighborPaths.add(item.source_path);
    });
  }

  els.graphSvg.querySelectorAll(".graph-node").forEach((node) => {
    node.classList.remove("active", "neighbor", "dimmed");
  });
  els.graphSvg.querySelectorAll(".node-label, .edge-line").forEach((item) => item.classList.remove("dimmed"));

  els.graphSvg.querySelectorAll("g[data-path]").forEach((group) => {
    const nodePath = group.dataset.path;
    const rect = group.querySelector(".graph-node");
    const labels = group.querySelectorAll(".node-label");
    if (!rect || !nodePath) return;
    if (nodePath === filePath) {
      rect.classList.add("active");
    } else if (neighborPaths.has(nodePath)) {
      rect.classList.add("neighbor");
    } else {
      rect.classList.add("dimmed");
      labels.forEach((label) => label.classList.add("dimmed"));
    }
  });

  els.graphSvg.querySelectorAll(".edge-line").forEach((edge) => {
    if (edge.dataset.sourcePath === filePath || edge.dataset.targetPath === filePath || neighborPaths.has(edge.dataset.sourcePath) || neighborPaths.has(edge.dataset.targetPath)) {
      return;
    }
    edge.classList.add("dimmed");
  });
}

function centerOnFile(filePath) {
  const target = Array.from(state.nodePositions.values()).find((item) => item.node.path === filePath);
  if (!target) return;
  const canvasWidth = els.graphCanvas.offsetWidth;
  const canvasHeight = els.graphCanvas.offsetHeight;
  const left = Math.max(0, target.x * state.zoom - els.graphScroll.clientWidth / 2);
  const top = Math.max(0, target.y * state.zoom - els.graphScroll.clientHeight / 2);
  els.graphScroll.scrollLeft = Math.min(left, Math.max(0, canvasWidth - els.graphScroll.clientWidth));
  els.graphScroll.scrollTop = Math.min(top, Math.max(0, canvasHeight - els.graphScroll.clientHeight));
  updateMinimapViewport();
}

async function startBuild(event) {
  event.preventDefault();
  state.rootPath = els.rootPath.value.trim();
  if (!state.rootPath) {
    setStatus("Enter a codebase path first.");
    return;
  }
  const status = await api("/api/build", {
    method: "POST",
    body: JSON.stringify({ root_path: state.rootPath, incremental: false }),
  });
  state.buildJobId = status.job_id;
  state.buildState = status.state;
  els.heroRoot.textContent = state.rootPath;
  setStatusLinks(status);
  const meta = `${status.state} | ${status.current}/${status.total}`;
  setStatus(status.message || "Build queued", meta, 6);
  pollBuild();
}

async function pollBuild() {
  if (!state.buildJobId) return;
  const status = await api(`/api/builds/${state.buildJobId}`);
  state.buildState = status.state;
  setStatusLinks(status);
  const progress = status.total > 0 ? (status.current / status.total) * 100 : status.state === "done" ? 100 : 8;
  setStatus(status.message || status.state, `${status.state} | ${status.current}/${status.total}`, progress);
  if (status.state === "done") {
    await loadRepoInfo();
    updateMetrics(state.repoInfo, status);
    return;
  }
  if (status.state === "error" || status.state === "cancelled") {
    updateMetrics(state.repoInfo || { counts: {} }, status);
    return;
  }
  window.setTimeout(() => pollBuild().catch((error) => setStatus(error.message)), 1000);
}

async function refreshAll() {
  state.rootPath = els.rootPath.value.trim() || state.rootPath;
  if (!state.rootPath) return;
  await loadRepoInfo();
}

async function runSearch() {
  const prefix = els.searchInput.value.trim();
  if (!prefix || !state.rootPath) {
    els.searchResults.innerHTML = "";
    return;
  }
  const payload = await api("/api/auto_complete", {
    method: "POST",
    body: JSON.stringify({ root_path: state.rootPath, prefix, limit: 20 }),
  });
  els.searchResults.innerHTML = payload.results
    .map(
      (item) => `
        <div class="result-item" data-path="${escapeHtml(item.path || item.label)}" title="${escapeHtml(item.path || item.label)}">
          <strong>${escapeHtml(item.label)}</strong>
          <small>${escapeHtml(item.type)}${item.path ? ` | ${escapeHtml(item.path)}` : ""}</small>
        </div>`
    )
    .join("");
  els.searchResults.querySelectorAll(".result-item").forEach((item) => {
    item.addEventListener("click", async () => {
      const path = item.dataset.path;
      if (!path) return;
      state.currentView = "search";
      await loadFocusedGraph(path, 2, 240);
      const node = state.graph?.nodes?.find((entry) => entry.path === path);
      if (node) {
        await loadFileDetails(path);
      }
    });
  });
}

async function askGraph(promptText = null) {
  if (!state.rootPath) return;
  const question = promptText || els.questionInput.value.trim();
  if (!question) return;
  els.askButton.disabled = true;
  els.answerBox.textContent = "Searching graph...";
  try {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 8000);
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ root_path: state.rootPath, question, limit: 6, depth: 1 }),
      signal: controller.signal,
    });
    window.clearTimeout(timer);
    if (!response.ok) {
      throw new Error("Ask graph request failed");
    }
    const answer = await response.json();
    els.answerBox.textContent = `${answer.answer}\n\nSuggested follow-ups:\n- ${answer.suggested_followups.join("\n- ")}`;
  } catch (error) {
    const message = error.name === "AbortError" ? "The query took too long. Try naming a file, module, or symbol directly." : error.message;
    els.answerBox.textContent = message;
  } finally {
    els.askButton.disabled = false;
  }
}

async function focusNeighbors() {
  if (!state.selection) return;
  state.currentView = "neighbors";
  await loadFocusedGraph(state.selection.file.path, 2, 220);
  centerOnFile(state.selection.file.path);
}

async function findPathsForSelection() {
  if (!state.selection || !state.rootPath) return;
  const outgoing = state.selection.outgoing.find((item) => item.target_path);
  if (!outgoing) {
    els.pathResults.innerHTML = '<div class="muted">No outgoing dependency path available for this file.</div>';
    return;
  }
  els.pathResults.innerHTML = '<div class="muted">Finding dependency path...</div>';
  const result = await api("/api/find_paths", {
    method: "POST",
    body: JSON.stringify({
      root_path: state.rootPath,
      source: state.selection.file.path,
      sink: outgoing.target_path,
      max_depth: 4,
    }),
  });
  els.pathResults.innerHTML = result.paths?.length
    ? result.paths.map((item) => `<div class="token">${escapeHtml(item)}</div>`).join("")
    : `<div class="muted">${escapeHtml(result.reason || "No path found.")}</div>`;
}

function toggleRail(element) {
  element.classList.toggle("collapsed");
}

function setZoom(nextZoom) {
  state.zoom = Math.max(0.6, Math.min(1.8, nextZoom));
  applyZoom();
  updateMinimapViewport();
}

function wireScrollDrag() {
  els.graphScroll.addEventListener("mousedown", (event) => {
    if (event.target.closest("g[data-path]")) return;
    state.panDrag = {
      x: event.clientX,
      y: event.clientY,
      left: els.graphScroll.scrollLeft,
      top: els.graphScroll.scrollTop,
    };
    els.graphScroll.classList.add("is-dragging");
  });
  window.addEventListener("mousemove", (event) => {
    if (!state.panDrag) return;
    const dx = event.clientX - state.panDrag.x;
    const dy = event.clientY - state.panDrag.y;
    els.graphScroll.scrollLeft = state.panDrag.left - dx;
    els.graphScroll.scrollTop = state.panDrag.top - dy;
    updateMinimapViewport();
  });
  window.addEventListener("mouseup", () => {
    state.panDrag = null;
    els.graphScroll.classList.remove("is-dragging");
  });
  els.graphScroll.addEventListener("scroll", updateMinimapViewport);
}

els.buildForm.addEventListener("submit", (event) => startBuild(event).catch((error) => setStatus(error.message)));
els.refreshButton.addEventListener("click", () => refreshAll().catch((error) => setStatus(error.message)));
els.searchInput.addEventListener("input", () => {
  window.clearTimeout(els.searchInput._debounce);
  els.searchInput._debounce = window.setTimeout(() => runSearch().catch((error) => setStatus(error.message)), 220);
});
els.askButton.addEventListener("click", () => askGraph().catch((error) => setStatus(error.message)));
els.focusNeighborsButton.addEventListener("click", () => focusNeighbors().catch((error) => setStatus(error.message)));
els.findPathsButton.addEventListener("click", () => findPathsForSelection().catch((error) => setStatus(error.message)));
els.askAboutFileButton.addEventListener("click", () => {
  if (!state.selection) return;
  const prompt = `Explain the role of ${state.selection.file.path} and its main dependencies`;
  els.questionInput.value = prompt;
  askGraph(prompt).catch((error) => setStatus(error.message));
});
els.toggleLeft.addEventListener("click", () => toggleRail(els.leftRail));
els.toggleRight.addEventListener("click", () => toggleRail(els.rightRail));
els.toggleLeftInline.addEventListener("click", () => toggleRail(els.leftRail));
els.toggleRightInline.addEventListener("click", () => toggleRail(els.rightRail));
els.zoomInButton.addEventListener("click", () => setZoom(state.zoom + 0.15));
els.zoomOutButton.addEventListener("click", () => setZoom(state.zoom - 0.15));
els.fitButton.addEventListener("click", fitGraph);
els.resetButton.addEventListener("click", () => {
  resetGraphView();
  refreshAll().catch((error) => setStatus(error.message));
});
els.showOverviewButton.addEventListener("click", () => {
  state.currentView = "overview";
  refreshAll().catch((error) => setStatus(error.message));
});
els.showFullButton.addEventListener("click", async () => {
  if (!state.rootPath) return;
  state.currentView = "full";
  const response = await api(`/api/graph_entities?root_path=${encodeURIComponent(state.rootPath)}&limit=800`);
  renderGraph(response.graph);
  renderFileList(response.graph.nodes);
});
els.centerSelectionButton.addEventListener("click", () => {
  if (state.selection) centerOnFile(state.selection.file.path);
});

wireScrollDrag();

const query = new URLSearchParams(window.location.search);
const initialPath = query.get("root_path");
const initialJobId = query.get("job_id");
if (initialPath) {
  els.rootPath.value = initialPath;
  state.rootPath = initialPath;
  els.heroRoot.textContent = initialPath;
  if (initialJobId) {
    state.buildJobId = initialJobId;
    setStatus("Connecting to build job...", "Polling live build status");
    pollBuild().catch((error) => setStatus(error.message));
  } else {
    setStatus("Loading indexed graph...", "Fetching repository overview");
    loadRepoInfo().catch((error) => setStatus(error.message));
  }
}
