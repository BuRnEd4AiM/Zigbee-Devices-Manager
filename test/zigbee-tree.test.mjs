// Tests für Parser und Baum-Algorithmus (node --test test/). Keine Abhängigkeiten nötig.
import {test} from "node:test";
import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {readdirSync, readFileSync} from "node:fs";

const require = createRequire(import.meta.url);
const T = require("../zigbee_devices_manager/web/zigbee-tree.js");
const fixtures = new URL("./fixtures/", import.meta.url);
const load = name => JSON.parse(readFileSync(new URL(name, fixtures), "utf8"));

// ---------- kleines Netz zum Bauen eigener Fälle ----------
const C = "0xc000000000000000";
const node = (ieee, type, name = ieee, extra = {}) => ({ieeeAddr: ieee, friendlyName: name, type, networkAddress: parseInt(ieee.slice(-4), 16), ...extra});
/** Eintrag in der Tabelle von `owner` über `other` (so liefert Z2M die Links). */
const link = (owner, other, lqi, relationship = 2, depth = 1, extra = {}) => ({
  source: {ieeeAddr: other, networkAddress: parseInt(other.slice(-4), 16)}, target: {ieeeAddr: owner, networkAddress: parseInt(owner.slice(-4), 16)},
  lqi, linkquality: lqi, relationship, depth, routes: [], ...extra});
const parentOf = (tree, ieee) => tree.all.get(ieee).parent;

test("Formate: Z2M-Antwort, value, HA-Attribute, JSON-Text, alte Feldnamen", () => {
  const value = {nodes: [node(C, "Coordinator"), node("0x0000000000000a01", "Router")],
    links: [{sourceIeeeAddr: "0x0000000000000A01", targetIeeeAddr: C, linkquality: 120, relationship: 2, depth: 1}]};
  for (const raw of [value, {data: {type: "raw", value}, status: "ok"}, {attributes: {friendly_name: "x", ...value}}, JSON.stringify({value})]) {
    const t = T.build(raw);
    assert.equal(parentOf(t, "0x0000000000000a01"), C);
    assert.equal(t.all.get("0x0000000000000a01").link.lqi, 120);
  }
  assert.throws(() => T.build({foo: 1}), /Keine Networkmap/);
});

test("A→B und B→A werden ein Paar mit beiden Werten; Gewicht ist der schwächere", () => {
  const R = "0x0000000000000a01";
  const t = T.build({nodes: [node(C, "Coordinator"), node(R, "Router")], links: [link(C, R, 200), link(R, C, 90, 0)]});
  const l = t.all.get(R).link;
  assert.deepEqual([l.lqiIn, l.lqiOut, l.lqi], [90, 200, 90]); // R hört C mit 90, C hört R mit 200
  assert.equal(t.stats.links, 1);
});

test("LQI 0 zählt nur, wenn es keinen anderen Wert gibt", () => {
  const R1 = "0x0000000000000a01", R2 = "0x0000000000000a02";
  const t = T.build({nodes: [node(C, "Coordinator"), node(R1, "Router"), node(R2, "Router")],
    links: [link(C, R1, 0), link(R1, C, 40, 0), link(C, R2, 0)]});
  assert.equal(t.all.get(R1).link.lqi, 40);
  assert.equal(t.all.get(R2).link.lqi, 0);
  assert.equal(T.lqiClass(0), "bad");
});

test("Router: breitester Pfad statt direkter schwacher Verbindung", () => {
  const A = "0x0000000000000a01", B = "0x0000000000000a02", X = "0x0000000000000a03";
  const t = T.build({nodes: [node(C, "Coordinator"), node(A, "Router"), node(B, "Router"), node(X, "Router")],
    links: [link(C, A, 190), link(A, C, 200), link(A, X, 150), link(X, A, 160), link(C, X, 40), link(X, C, 45), link(C, B, 100)]});
  assert.equal(parentOf(t, X), A);              // min(190,150) = 150 schlägt direkt 40
  assert.equal(t.all.get(X).bottleneck, 150);
  assert.deepEqual(T.pathTo(t, X), [C, A, X]);
  assert.equal(t.coordinator.descendants, 3);
});

test("Gleichstand: erst weniger Sprünge, dann flacherer Parent, dann kleinere IEEE", () => {
  const A = "0x0000000000000a01", B = "0x0000000000000a02", X = "0x0000000000000a03", Y = "0x0000000000000a04";
  // X: direkt 100 oder über A min(200,100) = 100 → direkt (1 Sprung)
  // Y: über A oder B, beide 120, beide 2 Sprünge; B ist flacher (depth 1 statt 2) → B
  const t = T.build({nodes: [C, A, B, X, Y].map(k => node(k, k === C ? "Coordinator" : "Router")),
    links: [link(C, A, 200, 2, 2), link(C, B, 200, 2, 1), link(C, X, 100), link(A, X, 100), link(A, Y, 120), link(B, Y, 120)]});
  assert.equal(parentOf(t, X), C);
  assert.equal(parentOf(t, Y), B);
  // ohne depth entscheidet die kleinere IEEE
  const u = T.build({nodes: [C, A, B, Y].map(k => node(k, k === C ? "Coordinator" : "Router")),
    links: [link(C, A, 200), link(C, B, 200), link(A, Y, 120), link(B, Y, 120)].map(l => ({...l, depth: 255}))});
  assert.equal(parentOf(u, Y), A);
});

test("Endgeräte: Parent laut relationship, mehrere → höchster LQI, sonst vermutet", () => {
  const R1 = "0x0000000000000a01", R2 = "0x0000000000000a02", E1 = "0x0000000000000e01", E2 = "0x0000000000000e02", E3 = "0x0000000000000e03";
  const t = T.build({nodes: [node(C, "Coordinator"), node(R1, "Router"), node(R2, "Router"), node(E1, "EndDevice"), node(E2, "EndDevice"), node(E3, "EndDevice")],
    links: [link(C, R1, 200), link(C, R2, 200),
      link(R1, E1, 60, 1), link(R2, E1, 140, 1),  // E1 von beiden als Kind geführt → R2 (140)
      link(R1, E2, 200, 2), link(R2, E2, 90, 1),  // E2: Kind nur bei R2, auch wenn R1 lauter ist
      link(R1, E3, 70, 2)]});                     // E3: kein Kind-Eintrag → vermutet bei R1
  assert.equal(parentOf(t, E1), R2);
  assert.equal(parentOf(t, E2), R2);
  assert.equal(parentOf(t, E3), R1);
  assert.equal(t.all.get(E3).guessed, true);
  assert.equal(t.all.get(E2).guessed, false);
  assert.equal(t.all.get(R2).children.length, 2);
});

test("Nicht verbunden: Geräte ohne Links und unerreichbare Router samt Kindern", () => {
  const R1 = "0x0000000000000a01", R9 = "0x0000000000000a09", E1 = "0x0000000000000e01", E9 = "0x0000000000000e09";
  const t = T.build({nodes: [node(C, "Coordinator"), node(R1, "Router"), node(R9, "Router", "Insel"), node(E1, "EndDevice"), node(E9, "EndDevice")],
    links: [link(C, R1, 200), link(R9, E9, 80, 1)]});
  assert.deepEqual(t.unconnected.map(u => u.ieee), [R9, E1]); // Router vor Endgeräten
  assert.equal(parentOf(t, E9), R9);
  assert.equal(t.stats.unconnected, 3);
});

test("Xiaomi 0x0000…-Nachbar über die Netzwerkadresse, fremde Geräte als Platzhalter, früheres Kind ignoriert", () => {
  const R = "0x0000000000000a01", E = "0x0000000000006002";
  const t = T.build({nodes: [node(C, "Coordinator"), node(R, "Router"), node(E, "EndDevice", "Aqara", {networkAddress: 0x6002})],
    links: [link(C, R, 200),
      {source: {ieeeAddr: "0x0000000000000000", networkAddress: 0x6002}, target: {ieeeAddr: R, networkAddress: 0x0a01}, lqi: 110, relationship: 1, depth: 2},
      link(R, "0x00000000000000ff", 33, 1, 2, {deviceType: 2}),
      link(R, "0x00000000000000ee", 99, 4)]});
  assert.equal(parentOf(t, E), R);
  const ph = t.all.get("0x00000000000000ff");
  assert.equal(ph.node.placeholder, true);
  assert.equal(ph.node.type, "EndDevice");
  assert.equal(ph.parent, R);
  assert.equal(t.all.has("0x00000000000000ee"), false);
  assert.equal(t.stats.skipped, 1);
});

test("Ohne Koordinator: alles nicht verbunden, kein Absturz", () => {
  const t = T.build({nodes: [node("0x0000000000000a01", "Router")], links: []});
  assert.equal(t.coordinator, null);
  assert.equal(t.unconnected.length, 1);
});

test("LQI-Farben mit Standard- und eigenen Schwellen", () => {
  assert.deepEqual([0, 29, 30, 79, 80, 149, 150, 255].map(v => T.lqiClass(v)), ["bad", "bad", "weak", "weak", "ok", "ok", "good", "good"]);
  assert.equal(T.lqiClass(100, [50, 120, 200]), "weak");
  assert.equal(T.lqiClass(null), "none");
});

// ---------- echter Scan (anonymisiert) ----------
test("Echter Scan Instanz 1: Baum wie erwartet", () => {
  const t = T.build(load("real-instanz1.json"));
  const by = name => [...t.all.values()].find(x => x.node.name === name);
  const parentName = name => t.all.get(by(name).parent)?.node.name;
  assert.equal(t.coordinator.node.name, "Coordinator");
  assert.deepEqual([t.stats.devices, t.stats.routers, t.stats.endDevices, t.stats.unconnected], [25, 8, 16, 9]);
  // Repeater: Koordinator meldet 0, der Repeater hört den Koordinator mit 39 → direkt, Pfad 39
  assert.equal(parentName("Router-02"), "Coordinator");
  assert.equal(by("Router-02").bottleneck, 39);
  // Spots laufen über den stärksten Router (90) statt über ihre schwächeren Direktverbindungen
  assert.equal(parentName("Router-05"), "Coordinator");
  for (const r of ["Router-03", "Router-06"]) assert.equal(parentName(r), "Router-05");
  assert.equal(parentName("Router-04"), "Router-06");
  // Steckdose mit drei Thermostaten (und einem Gerät, das Z2M nicht mehr kennt)
  assert.equal(parentName("Router-01"), "Router-04");
  assert.equal(by("Router-01").bottleneck, 43);
  assert.equal(by("Router-01").children.length, 4);
  assert.equal(by("Router-01").children.filter(c => c.node.placeholder).length, 1);
  // Batterie-Sensoren ohne aktuellen Eintrag
  assert.ok(t.unconnected.every(u => u.node.type === "EndDevice"));
});

// ---------- Eigenschaften, die für jeden Scan gelten müssen (auch für neue echte Fixtures) ----------
for (const file of readdirSync(fixtures).filter(f => f.endsWith(".json"))) {
  test(`Grundregeln: ${file}`, () => {
    const t = T.build(load(file));
    const seen = new Set();
    const visit = (n, parent) => {
      assert.ok(!seen.has(n.ieee), "jedes Gerät genau einmal");
      seen.add(n.ieee);
      if (parent) {
        assert.equal(n.parent, parent.ieee);
        assert.ok(["Coordinator", "Router"].includes(parent.node.type), "Parent ist Koordinator oder Router");
        assert.ok(n.neighbors.some(e => e.ieee === parent.ieee), "Parent ist ein Nachbar");
      }
      if (n.node.type === "Router" && n.bottleneck !== null && parent) {
        assert.equal(n.bottleneck, Math.min(parent.bottleneck, n.link.lqi), "Pfadwert = schwächste Verbindung");
      }
      n.children.forEach(c => visit(c, n));
    };
    if (t.coordinator) visit(t.coordinator, null);
    t.unconnected.forEach(u => visit(u, null));
    assert.equal(seen.size, t.all.size, "nichts geht verloren");
  });
}
