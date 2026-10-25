"""Tests für das Umbenennen der Entity-IDs (entity_changes, mark_stale_ids). Start: python3 -m unittest discover -s test"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "zigbee_devices_manager"))
import server  # noqa: E402

AREAS = [{"area_id": "wz_s2", "name": "Wohnzimmer (S2)"}, {"area_id": "kueche", "name": "Küche"}]


def ent(entity_id, device_id, original_name=None, area_id=None):
    return {"entity_id": entity_id, "device_id": device_id, "original_name": original_name, "area_id": area_id}


def dev(device_id, area_id="wz_s2"):
    return {"id": device_id, "area_id": area_id}


def mapping(changes):
    return {c["old"]: c["new"] for c in changes}


class EntityChanges(unittest.TestCase):
    def test_area_prefix_from_ha(self):
        """HA legt neue IDs als <Bereich>_<Gerät> an – der Bereich gehört nicht zum alten Namen und muss mit weg."""
        entities = [ent("light.wohnzimmer_s2_wzel03", "d1"), ent("button.wohnzimmer_s2_wzel03_identify", "d1", "Identify")]
        items = [{"device_id": "d1", "name": "S2-WZEL-LSP03", "old_name": "WZEL03", "orig_name": "KAJPLATS GU10 CWS 470lm"}]
        changes, skipped, _ = server.entity_changes(items, entities, [dev("d1")], AREAS)
        self.assertEqual(mapping(changes), {"light.wohnzimmer_s2_wzel03": "light.s2_wzel_lsp03",
                                            "button.wohnzimmer_s2_wzel03_identify": "button.s2_wzel_lsp03_identify"})
        self.assertEqual(skipped, [])

    def test_single_entity_already_renamed_device(self):
        """Gerät heißt schon S2-WZEL-LSP02, die einzige Entität trägt noch den Namen vom Anlernen (mit Bereich davor)."""
        entities = [ent("light.wohnzimmer_s2_wuel2", "d2")]
        items = [{"device_id": "d2", "name": "S2-WZEL-LSP02", "old_name": "S2-WZEL-LSP02", "orig_name": "KAJPLATS GU10 CWS 470lm"}]
        changes, _, _ = server.entity_changes(items, entities, [dev("d2")], AREAS)
        self.assertEqual(mapping(changes), {"light.wohnzimmer_s2_wuel2": "light.s2_wzel_lsp02"})

    def test_device_moved_to_other_area(self):
        """Die ID trägt noch den früheren Bereich – auch der wird erkannt."""
        entities = [ent("sensor.kuche_wz_temp2_temperature", "d3", "Temperature")]
        items = [{"device_id": "d3", "name": "S2-WZEL-TEM03", "old_name": "Wz Temp2", "orig_name": ""}]
        changes, _, _ = server.entity_changes(items, entities, [dev("d3")], AREAS)
        self.assertEqual(mapping(changes), {"sensor.kuche_wz_temp2_temperature": "sensor.s2_wzel_tem03_temperature"})

    def test_plain_old_name_still_works(self):
        entities = [ent("light.wz_lp_05", "d4"), ent("sensor.wz_lp_05_battery", "d4", "Battery")]
        items = [{"device_id": "d4", "name": "WZ_LP_06", "old_name": "WZ_LP_05", "orig_name": ""}]
        changes, _, _ = server.entity_changes(items, entities, [dev("d4")], AREAS)
        self.assertEqual(mapping(changes), {"light.wz_lp_05": "light.wz_lp_06", "sensor.wz_lp_05_battery": "sensor.wz_lp_06_battery"})

    def test_second_main_entity_keeps_suffix(self):
        """Zwei Haupt-Entitäten (light.x und light.x_2): die kürzere ID ist der Gerätenamen-Teil, _2 bleibt erhalten."""
        entities = [ent("light.wohnzimmer_s2_wz_led_6", "d5"), ent("light.wohnzimmer_s2_wz_led_6_2", "d5")]
        items = [{"device_id": "d5", "name": "S2-WZEL-LSP06", "old_name": "S2-WZEL-LSP06", "orig_name": ""}]
        changes, _, _ = server.entity_changes(items, entities, [dev("d5")], AREAS)
        self.assertEqual(mapping(changes), {"light.wohnzimmer_s2_wz_led_6": "light.s2_wzel_lsp06",
                                            "light.wohnzimmer_s2_wz_led_6_2": "light.s2_wzel_lsp06_2"})

    def test_existing_target_is_skipped(self):
        entities = [ent("light.wohnzimmer_s2_wzel4", "d6"), ent("light.s2_wzel_lsp04", None)]
        items = [{"device_id": "d6", "name": "S2-WZEL-LSP04", "old_name": "S2-WZEL-LSP04", "orig_name": ""}]
        changes, skipped, _ = server.entity_changes(items, entities, [dev("d6")], AREAS)
        self.assertEqual(changes, [])
        self.assertEqual([(s["old"], s["new"]) for s in skipped], [("light.wohnzimmer_s2_wzel4", "light.s2_wzel_lsp04")])


class Zigbee2MqttPartlyRenamed(unittest.TestCase):
    """Z2M hat beim Umbenennen nur einen Teil der Entity-IDs mitgenommen (abgeschaltete wie linkquality/update_* blieben):
    H1-WZFL-TAS02 hat h1_wzfl_tas02_battery, aber noch h1_wz_tas02_linkquality usw."""
    IEEE = "0x001788010b1c2d3e"

    def z2m(self, entity_id, prop, original_name=""):
        return {**ent(entity_id, "t", original_name), "platform": "mqtt", "unique_id": f"{self.IEEE}_{prop}_zigbee2mqtt"}

    def entities(self, with_uid=True):
        rows = [("sensor.h1_wzfl_tas02_battery", "battery", "Battery"), ("event.h1_wzfl_tas02_action", "action", "Action"),
                ("sensor.h1_wz_tas02_linkquality", "linkquality", "Linkquality"),
                ("sensor.h1_wz_tas02_update_state", "update_state", "Update state"),
                ("binary_sensor.h1_wz_tas02_update_available", "update_available", None)]  # Z2M: ohne eigenen Namen
        return [self.z2m(e, p, n) if with_uid else ent(e, "t", n) for e, p, n in rows]

    def check(self, entities):
        items = [{"device_id": "t", "name": "H1-WZFL-TAS02", "old_name": "H1-WZFL-TAS02", "orig_name": "H1-WZFL-TAS02"}]
        changes, skipped, _ = server.entity_changes(items, entities, [dev("t", None)], AREAS)
        self.assertEqual(mapping(changes), {"sensor.h1_wz_tas02_linkquality": "sensor.h1_wzfl_tas02_linkquality",
                                            "sensor.h1_wz_tas02_update_state": "sensor.h1_wzfl_tas02_update_state",
                                            "binary_sensor.h1_wz_tas02_update_available": "binary_sensor.h1_wzfl_tas02_update_available"})
        self.assertEqual(skipped, [])

    def test_endings_from_z2m_unique_id(self):
        self.check(self.entities())

    def test_no_doubling_without_unique_id(self):
        """Ohne Z2M-unique_id: gemeinsamer Anfang nur der noch alten IDs (h1_wz_tas02), nicht „h1“ über alle."""
        self.check(self.entities(with_uid=False))

    def test_leftover_id_of_previous_name(self):
        """H1-SZFL-SW02 trägt noch sensor.h1_szfl_sw01_linkquality (früherer Name SW01): nicht h1_szfl_sw02_sw01_linkquality."""
        entities = [self.z2m("sensor.h1_szfl_sw02_battery", "battery", "Battery"), self.z2m("event.h1_szfl_sw02_action", "action", "Action"),
                    self.z2m("sensor.h1_szfl_sw01_linkquality", "linkquality", "Linkquality")]
        items = [{"device_id": "t", "name": "H1-SZFL-SW02", "old_name": "H1-SZFL-SW02", "orig_name": "H1-SZFL-SW02"}]
        changes, _, _ = server.entity_changes(items, entities, [dev("t", None)], AREAS)
        self.assertEqual(mapping(changes), {"sensor.h1_szfl_sw01_linkquality": "sensor.h1_szfl_sw02_linkquality"})
        # ohne Z2M-unique_id lässt sich die Endung nicht sicher bestimmen: dann lieber nichts ändern als raten
        plain = [ent(e["entity_id"], "t", e["original_name"]) for e in entities]
        self.assertEqual(server.entity_changes(items, plain, [dev("t", None)], AREAS)[0], [])

    def test_z2m_light_keeps_no_type_suffix(self):
        """Z2M lässt den Typ weg: light.flur_light ist das Licht selbst (unique_id …_light_…), light.flur_light_l1 Endpunkt l1."""
        entities = [self.z2m("light.flur_light", "light"), self.z2m("light.flur_light_l1", "light_l1", "L1"),
                    self.z2m("sensor.flur_light_linkquality", "linkquality", "Linkquality")]
        items = [{"device_id": "t", "name": "H1-FL-LP01", "old_name": "Flur Light", "orig_name": "Flur Light"}]
        changes, _, _ = server.entity_changes(items, entities, [dev("t", None)], AREAS)
        self.assertEqual(mapping(changes), {"light.flur_light": "light.h1_fl_lp01", "light.flur_light_l1": "light.h1_fl_lp01_l1",
                                            "sensor.flur_light_linkquality": "sensor.h1_fl_lp01_linkquality"})


class StaleIds(unittest.TestCase):
    def test_marks_only_named_devices_with_old_ids(self):
        out = [
            {"id": "ok", "name": "S2-WZEL-LSP01", "orig_name": "KAJPLATS", "is_new": False},
            {"id": "old", "name": "S2-WZEL-LSP02", "orig_name": "KAJPLATS", "is_new": False},
            {"id": "new", "name": "KAJPLATS", "orig_name": "KAJPLATS", "is_new": True},
        ]
        entities = [ent("light.s2_wzel_lsp01", "ok"), ent("button.s2_wzel_lsp01_identify", "ok", "Identify"),
                    ent("light.wohnzimmer_s2_wuel2", "old"), ent("button.wohnzimmer_s2_wuel2_identify", "old", "Identify"),
                    ent("light.wohnzimmer_s2_kajplats", "new")]
        server.mark_stale_ids(out, entities, [dev("ok"), dev("old"), dev("new")], AREAS)
        self.assertEqual(out[0]["stale_ids"], [])
        self.assertEqual(mapping(out[1]["stale_ids"]), {"light.wohnzimmer_s2_wuel2": "light.s2_wzel_lsp02",
                                                        "button.wohnzimmer_s2_wuel2_identify": "button.s2_wzel_lsp02_identify"})
        self.assertNotIn("stale_ids", out[2])

    def test_collision_suffix_is_not_stale(self):
        """light.<name>_2 (alte verwaiste Entität belegt light.<name>) lässt sich nicht angleichen und gilt nicht als veraltet."""
        out = [{"id": "d", "name": "S2-WZEL-LSP07", "orig_name": "", "is_new": False}]
        server.mark_stale_ids(out, [ent("light.s2_wzel_lsp07_2", "d")], [dev("d")], AREAS)
        self.assertEqual(out[0]["stale_ids"], [])


if __name__ == "__main__":
    unittest.main()


class BrokenReferences(unittest.IsolatedAsyncioTestCase):
    """„Verweise prüfen“: Karten/Automationen, die Entitäten nennen, die es nicht (mehr) gibt."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: getattr(server, k) for k in ("ha", "scan_configs", "replace_references", "backup_root")}
        server.backup_root = lambda: Path(self.tmp.name)
        self.replaced = []

        async def ha(cmds):
            out = []
            for c in cmds:
                if c["type"] == "get_states":
                    out.append([{"entity_id": "light.s2_wzel_lsp02", "attributes": {"friendly_name": "S2-WZEL-LSP02"}},
                                {"entity_id": "person.flo", "attributes": {}}])
                elif c["type"] == "config/entity_registry/list":
                    out.append([{"entity_id": "light.s2_wzel_lsp02"}, {"entity_id": "light.s2_wzel_lsp03"}])
                elif c["type"] == "get_services":
                    out.append({"light": {"turn_on": {}, "toggle": {}}})
            return out

        async def scan_configs():
            card = {"type": "custom:hue-like-light-card", "entities": ["light.s2_wzel_lsp02", "light.wohnzimmer_s2_wzel03"],
                    "tap_action": {"action": "perform-action", "perform_action": "light.toggle"},
                    "image": "/local/person.png", "url": "https://www.example.de", "icon": "mdi:lightbulb"}
            return [{"kind": "dashboard", "id": "licht", "title": "Licht", "config": {"views": [{"cards": [card]}]}},
                    {"kind": "automation", "id": "a1", "title": "Abends", "config": {"actions": [{"action": "light.turn_on", "target": {"entity_id": "light.s2_wzel_lsp02"}}]}}], 0

        async def replace_references(body, mapping):
            self.replaced.append(mapping)
            return [{"kind": "dashboard", "title": "Licht"}], 0, [], []

        server.ha, server.scan_configs, server.replace_references = ha, scan_configs, replace_references

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(server, k, v)
        self.tmp.cleanup()

    async def test_finds_only_missing_entities(self):
        res = await server.broken_references()
        self.assertEqual(res["missing"], ["light.wohnzimmer_s2_wzel03"])  # nicht light.toggle, Pfade, Hostnamen, mdi:
        self.assertEqual([(i["title"], i["entities"]) for i in res["items"]], [("Licht", ["light.wohnzimmer_s2_wzel03"])])
        self.assertEqual([c["id"] for c in res["choices"]["light"]], ["light.s2_wzel_lsp02", "light.s2_wzel_lsp03"])
        self.assertEqual(res["suggestions"], {})

    async def test_suggestion_from_rename_log_follows_chain(self):
        server.log_renames([{"old": "light.wohnzimmer_s2_wzel03", "new": "light.wz_lp_03"}])
        server.log_renames([{"old": "light.wz_lp_03", "new": "light.s2_wzel_lsp03"}])
        res = await server.broken_references()
        self.assertEqual(res["suggestions"], {"light.wohnzimmer_s2_wzel03": "light.s2_wzel_lsp03"})

    async def test_repair_only_maps_missing_to_existing(self):
        class Req:
            async def json(self):
                return {"mapping": {"light.wohnzimmer_s2_wzel03": "light.s2_wzel_lsp03",  # gültig
                                    "light.s2_wzel_lsp02": "light.s2_wzel_lsp03",          # Quelle existiert: nicht anfassen
                                    "light.weg": "light.gibts_nicht"}}                     # Ziel fehlt
        await server.repair_references(Req())
        self.assertEqual(self.replaced, [{"light.wohnzimmer_s2_wzel03": "light.s2_wzel_lsp03"}])
