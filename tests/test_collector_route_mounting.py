import unittest

from fastapi import FastAPI

from src.api.main import mount_collector_routers


class TestCollectorRouteMounting(unittest.TestCase):
    def test_should_only_mount_v2_when_mounting_collector_routers(self):
        app = FastAPI()
        mount_collector_routers(app)

        paths = {route.path for route in app.routes}
        self.assertNotIn('/api/v1/collectors', paths)
        self.assertIn('/api/v1/collectors-v2', paths)


if __name__ == '__main__':
    unittest.main()
