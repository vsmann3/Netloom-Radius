from django.test import SimpleTestCase


class ProductionStaticTests(SimpleTestCase):
    def test_local_dashboard_assets_are_served_without_debug_or_database(self):
        for path in ["/static/vendor/tabler/tabler.min.css", "/static/netloom/app.css"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/css", response["Content-Type"])
                self.assertTrue(b"".join(response.streaming_content))
                response.close()
