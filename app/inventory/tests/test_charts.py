from types import SimpleNamespace

from django.test import SimpleTestCase

from inventory.charts import alert_evolution


class ExampleEventTests(SimpleTestCase):
    def test_no_hosts_produces_zero_counts_and_valid_axis(self):
        chart = alert_evolution([])
        self.assertEqual(chart["total"], 0)
        self.assertEqual(chart["peak_count"], 0)
        self.assertGreater(chart["ticks"][-1]["value"], 0)
        for series in chart["series"]:
            self.assertTrue(all(point["value"] == 0 for point in series["markers"]))
            self.assertTrue(all(point["y"] == 150 for point in series["markers"]))

    def test_non_seed_hosts_do_not_generate_fabricated_events(self):
        real_host = SimpleNamespace(hostname="real-host", seed_metrics=False)
        chart = alert_evolution([real_host])
        self.assertEqual(chart["total"], 0)
        for series in chart["series"]:
            self.assertEqual(series["total"], 0)
