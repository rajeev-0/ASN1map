(async function () {
  const [nodes, edges] = await Promise.all([
    fetch("data/nodes.json").then(r => r.json()),
    fetch("data/edges.json").then(r => r.json()),
  ]);
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const STD = ["CMS", "X.509", "CMP", "CRMF", "External"];
  const COLORS = {"CMS": "#4c8bf5", "X.509": "#2eaa6b", "CMP": "#e8833a", "CRMF": "#a05ccf", "External": "#999"};
  const enabled = new Set(STD);
  const $ = id => document.getElementById(id);
  let current = null;

  cytoscape.use(cytoscapeDagre);
  const cy = cytoscape({
    container: $("cy"), wheelSensitivity: 0.3,
    style: [
      {selector: "node", style: {label: "data(label)", "background-color": "data(color)", color: "#1d2330",
        "font-size": 11, "text-valign": "bottom", "text-margin-y": 3, width: 22, height: 22}},
      {selector: "node.cur", style: {width: 34, height: 34, "border-width": 3, "border-color": "#111", "font-weight": "bold"}},
      {selector: "edge", style: {width: 1.2, "line-color": "#aab", "target-arrow-color": "#aab",
        "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": .8}},
      {selector: "edge[?optional]", style: {"line-style": "dashed"}},
      {selector: "edge[?implicit]", style: {"line-style": "dotted", "line-color": "#c66", "target-arrow-color": "#c66"}},
      {selector: "edge.hl", style: {"line-color": "#222", "target-arrow-color": "#222", width: 2}},
    ],
  });
  cy.on("tap", "node", e => select(e.target.id()));
  cy.on("mouseover", "node", e => e.target.connectedEdges().addClass("hl"));
  cy.on("mouseout", "node", () => cy.edges().removeClass("hl"));

  // filters
  $("filters").innerHTML = STD.map(s =>
    `<label><input type="checkbox" data-s="${s}" checked><span style="color:${COLORS[s]}">&#9679;</span> ${s}</label>`).join("");
  $("filters").addEventListener("change", e => {
    e.target.checked ? enabled.add(e.target.dataset.s) : enabled.delete(e.target.dataset.s);
    render(); renderResults();
  });
  $("depth").onchange = $("showAll").onchange = render;

  const visible = n => enabled.has(n.standard);

  function neighborhood(id, depth) {
    const seen = new Set([id]); let frontier = [id];
    for (let d = 0; d < depth; d++) {
      const next = [];
      for (const e of edges) {
        for (const [a, b] of [[e.source, e.target], [e.target, e.source]]) {
          if (frontier.includes(a) && !seen.has(b) && byId[b] && visible(byId[b])) { seen.add(b); next.push(b); }
        }
      }
      frontier = next;
    }
    return seen;
  }

  function render() {
    let ids;
    if ($("showAll").checked || !current) ids = new Set(nodes.filter(visible).map(n => n.id));
    else ids = neighborhood(current, +$("depth").value);
    const els = [];
    ids.forEach(id => els.push({data: {id, label: byId[id].name, color: COLORS[byId[id].standard] || "#999"}}));
    edges.forEach(e => { if (ids.has(e.source) && ids.has(e.target))
      els.push({data: {source: e.source, target: e.target, optional: e.optional, implicit: !!e.implicit, label: e.field}}); });
    cy.elements().remove(); cy.add(els);
    cy.layout({name: "dagre", rankDir: "LR", nodeSep: 14, rankSep: 80, animate: false}).run();
    if (current && ids.has(current)) { cy.$id(current).addClass("cur"); }
    if (current && !$("showAll").checked) cy.fit(undefined, 40);
  }

  const esc = s => String(s).replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c]));
  const link = id => byId[id] ? `<span class="link" data-go="${esc(id)}">${esc(byId[id].name)}</span>` : esc(id);
  function typeCell(f) {
    let t = esc(f.type);
    (f.targets || []).forEach(id => { const n = byId[id].name; t = t.replace(new RegExp("\\b" + n.replace(/[-.]/g, "\\$&") + "\\b"), link(id)); });
    return t;
  }
  function rows(fields, depth) {
    return fields.map(f => `<tr><td class="${depth ? "inl" : ""}">${esc(f.name)}</td><td>${typeCell(f)}</td>
      <td>${f.tag ? `<span class="badge">${esc(f.tag)}</span>` : ""}${f.optional ? '<span class="badge opt">OPTIONAL</span>' : ""}${f.default != null ? `<span class="badge def">DEFAULT ${esc(f.default)}</span>` : ""}</td></tr>`
      + (f.inline ? rows(f.inline, depth + 1) : "")).join("");
  }

  function select(id, noHash) {
    const n = byId[id]; if (!n) return;
    current = id;
    if (!noHash) history.replaceState(null, "", "#" + encodeURIComponent(id));
    render();
    const rfc = n.rfc ? `<a target="_blank" rel="noopener" href="https://www.rfc-editor.org/rfc/rfc${n.rfc}.html#section-${n.section}">RFC ${n.rfc} section ${n.section}</a>` : "external (not in scope)";
    $("right").innerHTML = `<h2>${esc(n.name)}</h2>
      <span class="badge">${esc(n.kind)}</span><span class="badge" style="background:${COLORS[n.standard]}33">${esc(n.standard)}</span>
      ${n.tag ? `<span class="badge">${esc(n.tag)}</span>` : ""}
      <div>Module: ${esc(n.module || "?")}<br>Source: ${rfc}</div>
      <h3>Fields</h3>${n.fields.length ? `<table>${rows(n.fields, 0)}</table>` : '<span class="hint">none</span>'}
      <h3>Used by (${n.usedBy.length})</h3>${n.usedBy.map(link).join(", ") || '<span class="hint">nothing in scope</span>'}
      <h3>ASN.1 source</h3>${n.source ? `<pre>${esc(n.source)}</pre>` : '<span class="hint">not available</span>'}`;
  }
  document.body.addEventListener("click", e => { const g = e.target.closest("[data-go]"); if (g) select(g.dataset.go); });

  function renderResults() {
    const q = $("search").value.trim().toLowerCase();
    const list = nodes.filter(n => visible(n) && (!q ||
      [n.name, n.module, n.rfc && "rfc" + n.rfc, n.rfc && "rfc " + n.rfc, n.standard].some(x => x && String(x).toLowerCase().includes(q))))
      .sort((a, b) => a.name.localeCompare(b.name)).slice(0, 300);
    $("results").innerHTML = list.map(n => `<li data-go="${esc(n.id)}">${esc(n.name)}<small>${esc(n.standard)}</small></li>`).join("");
  }
  $("search").oninput = renderResults;
  window.onhashchange = () => select(decodeURIComponent(location.hash.slice(1)), true);

  renderResults();
  select(byId[decodeURIComponent(location.hash.slice(1))] ? decodeURIComponent(location.hash.slice(1)) : "ContentInfo", true);
})();
