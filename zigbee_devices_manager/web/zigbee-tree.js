/* Zigbee-Netz als Baum: liest die raw-Networkmap von Zigbee2MQTT und berechnet, wer an wem hängt.
 * Ohne DOM – läuft im Browser (globalThis.ZigbeeTree) und in Node (require) für die Tests.
 *
 * Das raw-Format (Zigbee2MQTT lib/extension/networkMap.ts):
 *  - nodes[]: ieeeAddr, friendlyName, type (Coordinator/Router/EndDevice), networkAddress, lastSeen (ms), failed (z. B. ["lqi"]),
 *    definition {model, vendor, description}, manufacturerName, modelID.
 *  - links[]: ein Eintrag aus der Nachbartabelle von `target` über den Nachbarn `source`.
 *    lqi/linkquality = wie gut target den Nachbarn empfängt; relationship = Rolle von source aus Sicht von target
 *    (0 = Parent, 1 = Kind, 2 = Geschwister, 3 = keine, 4 = früheres Kind); depth = Tiefe von source.
 *    Abgefragt werden nur Koordinator und Router – Endgeräte erscheinen nur in der Tabelle ihres Parents.
 *    A→B und B→A kommen getrennt (eigener LQI je Richtung) und werden hier zu einem Paar zusammengefasst.
 *
 * Echte Scans (siehe test/fixtures): LQI 0 bedeutet in vielen Tabellen „kein aktueller Messwert“ (z. B. Tuya-Steckdosen,
 * Koordinator über manche Router), obwohl die Gegenrichtung gut ist. depth ist oft 255 oder 15 = unbekannt.
 *
 * Baum (build):
 *  1. Router-Pfade: „breitester Pfad“ vom Koordinator über Koordinator/Router. Gewicht einer Verbindung ist der
 *     schwächere der beiden LQI-Werte; eine 0 zählt nur, wenn es keinen anderen Wert gibt (nur eine Richtung bekannt:
 *     dieser Wert). Gesucht ist der Pfad, dessen schwächste
 *     Verbindung am stärksten ist (Dijkstra-Variante: offener Knoten mit dem besten Label zuerst). Gleichstand:
 *     weniger Sprünge, dann geringere depth des Parents, dann kleinere IEEE (immer dasselbe Ergebnis).
 *  2. Endgeräte (und Geräte unbekannten Typs) hängen an dem Router/Koordinator, der sie als Kind führt
 *     (relationship 1); mehrere: höchster LQI. Ohne Kind-Eintrag: stärkster Router-Nachbar, als „vermutet“ markiert.
 *  3. Nicht erreichbare Router (mit ihren Kindern) und Geräte ohne Verbindung bilden die Gruppe „Nicht verbunden“.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.ZigbeeTree = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ZERO = "0x0000000000000000";
  const ROLE = {0: "parent", 1: "child", 2: "sibling", 3: "none"};
  const INVERSE = {parent: "child", child: "parent", sibling: "sibling", none: "none"};
  const TYPE_ORDER = {Coordinator: 0, Router: 1, EndDevice: 2, Unknown: 3};

  const ieeeOf = v => (typeof v === "string" ? v : (v && v.ieeeAddr) || "").toLowerCase();
  const num = v => (v === null || v === undefined || v === "" || !Number.isFinite(Number(v)) ? null : Number(v));

  function normType(t) {
    const s = String(t || "").toLowerCase().replace(/[^a-z]/g, "");
    return s === "coordinator" ? "Coordinator" : s === "router" ? "Router" : s === "enddevice" ? "EndDevice" : "Unknown";
  }
  function toTime(v) {
    if (v === null || v === undefined || v === "") return null;
    const t = typeof v === "number" ? v : Date.parse(v);
    return Number.isFinite(t) ? t : null;
  }

  /** Findet {nodes, links} in einer Z2M-Antwort ({data: {value}}), im value selbst, in HA-Attributen oder als JSON-Text. */
  function unwrap(raw) {
    let v = typeof raw === "string" ? JSON.parse(raw) : raw;
    for (let i = 0; i < 4 && v && !Array.isArray(v.nodes); i++) v = v.data ?? v.value ?? v.attributes;
    if (!v || !Array.isArray(v.nodes)) throw new Error("Keine Networkmap gefunden (nodes/links fehlen)");
    return v;
  }

  function placeholder(ieee, deviceType, nwk) {
    return {ieee, name: ieee, type: deviceType === 1 ? "Router" : deviceType === 2 ? "EndDevice" : "Unknown", nwk: num(nwk),
      lastSeen: null, failed: [], model: "", vendor: "", description: "", placeholder: true};
  }

  /** Liest die raw-Networkmap: Geräte nach IEEE und Verbindungs-Paare mit den Werten beider Richtungen. */
  function parse(raw) {
    const v = unwrap(raw);
    const nodes = new Map();
    for (const n of v.nodes) {
      const ieee = ieeeOf(n.ieeeAddr);
      if (!ieee) continue;
      const def = n.definition || {};
      nodes.set(ieee, {ieee, name: n.friendlyName || n.friendly_name || ieee, type: normType(n.type), nwk: num(n.networkAddress),
        lastSeen: toTime(n.lastSeen), failed: Array.isArray(n.failed) ? n.failed : [], model: def.model || n.modelID || "",
        vendor: def.vendor || n.manufacturerName || "", description: def.description || "", placeholder: false});
    }
    const byNwk = new Map();
    for (const n of nodes.values()) if (n.nwk !== null) byNwk.set(n.nwk, n.ieee);

    const pairs = new Map();
    let skipped = 0;
    for (const l of v.links || []) {
      const srcNwk = num(l.source && l.source.networkAddress) ?? num(l.sourceNwkAddr);
      let src = ieeeOf(l.source) || ieeeOf(l.sourceIeeeAddr);
      if ((!src || src === ZERO) && srcNwk !== null && byNwk.has(srcNwk)) src = byNwk.get(srcNwk); // manche Xiaomi melden 0x00…
      const tgt = ieeeOf(l.target) || ieeeOf(l.targetIeeeAddr);
      const rel = num(l.relationship);
      const lqi = num(l.lqi ?? l.linkquality);
      if (!src || !tgt || src === ZERO || src === tgt || lqi === null || (rel !== null && rel > 3)) { skipped++; continue; }
      if (!nodes.has(src)) nodes.set(src, placeholder(src, num(l.deviceType), srcNwk));
      if (!nodes.has(tgt)) nodes.set(tgt, placeholder(tgt, null, l.target && l.target.networkAddress));
      const [a, b] = src < tgt ? [src, tgt] : [tgt, src];
      const key = a + "|" + b;
      const p = pairs.get(key) || {a, b, seen: {}};
      const prev = p.seen[tgt]; // Eintrag in der Tabelle von tgt über src
      const depth = num(l.depth);
      if (!prev || lqi > prev.lqi) p.seen[tgt] = {lqi, role: ROLE[rel ?? 3] || "none", depth: depth !== null && depth < 15 ? depth : null};
      pairs.set(key, p);
    }
    return {nodes, pairs: [...pairs.values()], skipped};
  }

  /** Nachbar-Sicht für `me`: wie gut me den anderen hört (lqiIn), wie gut der andere me hört (lqiOut), Rolle des anderen. */
  function neighborOf(p, me) {
    const other = p.a === me ? p.b : p.a;
    const mine = p.seen[me], theirs = p.seen[other];
    const role = mine ? mine.role : theirs ? INVERSE[theirs.role] : "none";
    const measured = [mine && mine.lqi, theirs && theirs.lqi].filter(x => x > 0); // 0 = kein Messwert, wenn es einen anderen gibt
    return {ieee: other, lqiIn: mine ? mine.lqi : null, lqiOut: theirs ? theirs.lqi : null, lqi: measured.length ? Math.min(...measured) : 0, role};
  }

  const isRouting = n => !!n && !n.placeholder && (n.type === "Coordinator" || n.type === "Router");
  const cmpStr = (x, y) => (x < y ? -1 : x > y ? 1 : 0);

  /** Baut den Baum. Liefert {coordinator, unconnected, all, stats}. */
  function build(raw) {
    const {nodes, pairs, skipped} = parse(raw);
    const nb = new Map([...nodes.keys()].map(k => [k, []]));
    const depth = new Map();
    for (const p of pairs) {
      nb.get(p.a).push(neighborOf(p, p.a));
      nb.get(p.b).push(neighborOf(p, p.b));
      for (const [owner, other] of [[p.a, p.b], [p.b, p.a]]) { // depth gehört zum Nachbarn (source)
        const e = p.seen[owner];
        if (e && e.depth !== null) depth.set(other, Math.min(depth.has(other) ? depth.get(other) : Infinity, e.depth));
      }
    }
    const coord = [...nodes.values()].find(n => n.type === "Coordinator" && !n.placeholder) || null;
    if (coord) depth.set(coord.ieee, 0);
    const depthOf = k => (depth.has(k) ? depth.get(k) : Infinity);

    // 1. Breitester Pfad vom Koordinator über Router
    const label = new Map();
    // a besser als b? Erst stärkste schwächste Verbindung, dann weniger Sprünge, dann flacherer Parent, dann IEEE
    const better = (a, b) => a.b !== b.b ? a.b > b.b : a.hops !== b.hops ? a.hops < b.hops
      : depthOf(a.parent) !== depthOf(b.parent) ? depthOf(a.parent) < depthOf(b.parent) : cmpStr(a.parent, b.parent) < 0;
    if (coord) {
      label.set(coord.ieee, {b: Infinity, hops: 0, parent: null, link: null});
      const open = new Set([coord.ieee]), done = new Set();
      while (open.size) {
        let cur = null;
        for (const k of open) {
          const lk = label.get(k), lc = cur && label.get(cur);
          if (!cur || lk.b > lc.b || (lk.b === lc.b && (lk.hops < lc.hops || (lk.hops === lc.hops && cmpStr(k, cur) < 0)))) cur = k;
        }
        open.delete(cur);
        done.add(cur);
        const lc = label.get(cur);
        for (const e of nb.get(cur)) {
          if (done.has(e.ieee) || !isRouting(nodes.get(e.ieee))) continue;
          const cand = {b: Math.min(lc.b, e.lqi), hops: lc.hops + 1, parent: cur, link: e};
          const old = label.get(e.ieee);
          if (!old || better(cand, old)) { label.set(e.ieee, cand); open.add(e.ieee); }
        }
      }
    }

    // Baumknoten
    const all = new Map();
    for (const n of nodes.values()) {
      const neighbors = nb.get(n.ieee).slice().sort((x, y) => y.lqi - x.lqi || cmpStr(x.ieee, y.ieee));
      all.set(n.ieee, {ieee: n.ieee, node: n, parent: null, link: null, bottleneck: null, hops: null, guessed: false, children: [], neighbors, descendants: 0});
    }
    // Verbindung aus Sicht des Kindes zum Parent: lqiIn = Kind hört Parent, lqiOut = Parent hört Kind
    const attach = (child, parent, guessed) => {
      const t = all.get(child), pt = all.get(parent);
      t.parent = parent;
      t.link = t.neighbors.find(e => e.ieee === parent) || null;
      t.guessed = guessed;
      pt.children.push(t);
    };
    for (const [k, l] of label) if (l.parent) attach(k, l.parent, false);

    // 2. Endgeräte und Geräte unbekannten Typs
    for (const n of nodes.values()) {
      if (isRouting(n)) continue;
      const routers = all.get(n.ieee).neighbors.filter(e => isRouting(nodes.get(e.ieee)));
      const reach = e => (label.has(e.ieee) ? label.get(e.ieee).b : -1);
      const pick = list => list.slice().sort((x, y) => y.lqi - x.lqi || reach(y) - reach(x) || cmpStr(x.ieee, y.ieee))[0];
      const parents = routers.filter(e => e.role === "parent");
      if (parents.length) attach(n.ieee, pick(parents).ieee, false);
      else if (routers.length) attach(n.ieee, pick(routers).ieee, true);
    }

    // Pfadwerte, Sortierung, Zählung (von oben nach unten)
    const sortKids = t => t.children.sort((x, y) => (TYPE_ORDER[x.node.type] - TYPE_ORDER[y.node.type]) || x.node.name.localeCompare(y.node.name, "de"));
    const walk = (t, hops, b) => {
      t.hops = hops;
      t.bottleneck = b;
      sortKids(t);
      t.descendants = 0;
      for (const c of t.children) {
        walk(c, hops === null ? null : hops + 1, b === null || !c.link ? null : Math.min(b, c.link.lqi));
        t.descendants += 1 + c.descendants;
      }
    };
    const coordinator = coord ? all.get(coord.ieee) : null;
    if (coordinator) walk(coordinator, 0, Infinity);
    const unconnected = [...all.values()].filter(t => t !== coordinator && !t.parent)
      .sort((x, y) => (TYPE_ORDER[x.node.type] - TYPE_ORDER[y.node.type]) || x.node.name.localeCompare(y.node.name, "de"));
    for (const t of unconnected) walk(t, null, null);

    const list = [...nodes.values()];
    return {coordinator, unconnected, all, stats: {
      devices: list.filter(n => !n.placeholder).length, routers: list.filter(n => n.type === "Router" && !n.placeholder).length,
      endDevices: list.filter(n => n.type === "EndDevice" && !n.placeholder).length, links: pairs.length,
      unconnected: unconnected.reduce((s, t) => s + 1 + t.descendants, 0), skipped}};
  }

  /** Farbklasse für einen LQI-Wert: bad < t0 ≤ weak < t1 ≤ ok < t2 ≤ good (Standard 30/80/150). */
  function lqiClass(lqi, thresholds) {
    const [t0, t1, t2] = thresholds && thresholds.length === 3 ? thresholds : [30, 80, 150];
    if (lqi === null || lqi === undefined || !Number.isFinite(lqi)) return "none";
    return lqi < t0 ? "bad" : lqi < t1 ? "weak" : lqi < t2 ? "ok" : "good";
  }

  /** Weg vom Koordinator (bzw. der obersten Stelle) bis zum Gerät, als Liste von IEEE-Adressen. */
  function pathTo(tree, ieee) {
    const out = [];
    for (let t = tree.all.get(ieee), guard = 0; t && guard < 1000; t = t.parent ? tree.all.get(t.parent) : null, guard++) out.unshift(t.ieee);
    return out;
  }

  return {parse, build, lqiClass, pathTo, unwrap};
});
