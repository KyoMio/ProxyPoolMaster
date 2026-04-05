import os
import sys
import unittest
from unittest.mock import patch, Mock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from api.auth import verify_api_token
from src import app_globals


class TestAuthQueryToken(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()

        @self.app.get('/protected', dependencies=[Depends(verify_api_token)])
        async def protected():
            return {'ok': True}

        self.client = TestClient(self.app)
        self.token_patcher = patch.object(app_globals.global_config, 'API_TOKEN', 'test-token')
        self.token_patcher.start()

    def tearDown(self):
        self.token_patcher.stop()

    def test_header_token_should_work(self):
        response = self.client.get('/protected', headers={'X-API-Token': 'test-token'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})

    def test_query_token_should_work(self):
        response = self.client.get('/protected?token=test-token')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})

    def test_missing_token_should_fail(self):
        response = self.client.get('/protected')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['detail'], 'Invalid or missing API token.')

    def test_blank_server_token_should_fail_closed(self):
        original_token = app_globals.global_config.API_TOKEN
        try:
            app_globals.global_config.API_TOKEN = ''
            response = self.client.get('/protected', headers={'X-API-Token': 'test-token'})
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.json()['detail'], 'API token not configured on the server.')
        finally:
            app_globals.global_config.API_TOKEN = original_token

    def test_invalid_token_should_not_be_logged_in_plaintext(self):
        original_logger = app_globals.global_logger
        mock_logger = Mock()
        app_globals.global_logger = mock_logger
        try:
            response = self.client.get('/protected?token=secret-token')
            self.assertEqual(response.status_code, 401)
            mock_logger.warning.assert_called_once()
            logged_message = mock_logger.warning.call_args.args[0]
            self.assertNotIn('secret-token', logged_message)
        finally:
            app_globals.global_logger = original_logger

    def test_config_update_should_affect_auth_dependency(self):
        from src.api import auth as auth_module
        from src.api.config_endpoints import router as config_router

        app = FastAPI()

        app.include_router(
            config_router,
            prefix="/api/v1/config",
            dependencies=[Depends(auth_module.verify_api_token)]
        )

        @app.get('/protected', dependencies=[Depends(auth_module.verify_api_token)])
        async def protected_after_update():
            return {'ok': True}

        client = TestClient(app)

        original_token = app_globals.global_config.API_TOKEN
        try:
            app_globals.global_config.API_TOKEN = 'old-token'

            update_response = client.post(
                '/api/v1/config/global',
                headers={'X-API-Token': 'old-token'},
                json={
                    'config': {'API_TOKEN': 'new-token'},
                    'save_to_file': False
                }
            )
            self.assertEqual(update_response.status_code, 200)

            response = client.get('/protected', headers={'X-API-Token': 'new-token'})
            self.assertEqual(response.status_code, 200)
        finally:
            app_globals.global_config.API_TOKEN = original_token


if __name__ == '__main__':
    unittest.main()
