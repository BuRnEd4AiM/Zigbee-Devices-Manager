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
