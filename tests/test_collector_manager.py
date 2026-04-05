import unittest
from unittest.mock import Mock, MagicMock, patch
from src.collectors.manager import CollectorManager
from src.collectors.base_collector import BaseCollector
from src.database.models import Proxy


class _DummyCollector(BaseCollector):
    def __init__(self, config, logger):
        super().__init__()
        self.config = config
        self.logger = logger

    def fetch_proxies(self):
        return []


class _DummyOverseasCollector(BaseCollector):
    def __init__(self, config, logger):
        super().__init__()
        self.config = config
        self.logger = logger

    def fetch_proxies(self):
        return []


class TestCollectorManager(unittest.TestCase):
    
    def setUp(self):
        """设置测试环境"""
        self.mock_config = Mock()
        self.mock_config.COLLECT_INTERVAL_SECONDS = 300
        self.mock_config.REQUEST_TIMEOUT = 10
        self.mock_logger = Mock()
        self.mock_redis = Mock()
    
    def test_load_builtin_collector(self):
        """测试加载预设收集器"""
        collectors_config = [
            {
                "id": "zdaye",
                "name": "站大爷",
                "enabled": True,
                "interval_seconds": 300,
                "source": "builtin",
                "module_path": "src.collectors.zdaye_collector",
                "class_name": "ZdayeCollector",
                "env_vars": {}
            }
        ]
        
        with patch('src.collectors.manager.CollectorManager._load_builtin_collector') as mock_load:
            manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
            mock_load.assert_called_once()
    
    def test_load_custom_collector(self):
        """测试加载自定义收集器"""
        collectors_config = [
            {
                "id": "custom_test",
                "name": "测试收集器",
                "enabled": True,
                "interval_seconds": 300,
                "source": "custom",
                "filename": "custom_test.py",
                "env_vars": {}
            }
        ]
        
        with patch('src.collectors.manager.CollectorManager._load_custom_collector') as mock_load:
            manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
            mock_load.assert_called_once()
    
    def test_disabled_collector_not_loaded(self):
        """测试禁用的收集器不会被加载"""
        collectors_config = [
            {
                "id": "disabled_collector",
                "enabled": False,
                "source": "custom",
                "filename": "disabled.py"
            }
        ]
        
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
        
        # 验证没有加载任何收集器
        self.assertEqual(len(manager._collectors), 0)
    
    def test_get_collector_status(self):
        """测试获取收集器状态"""
        collectors_config = []
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
        
        # 设置一些状态数据
        manager._last_status["test_collector"] = {
            "last_run": "2024-01-01T00:00:00",
            "status": "success",
            "count": 10
        }
        
        status = manager.get_collector_status("test_collector")
        self.assertIsNotNone(status)
        self.assertEqual(status["count"], 10)
        
        # 测试不存在的收集器
        status = manager.get_collector_status("non_existent")
        self.assertIsNone(status)
    
    def test_get_all_status(self):
        """测试获取所有收集器状态"""
        collectors_config = [
            {
                "id": "test_collector",
                "name": "Test Collector",
                "enabled": True,
                "interval_seconds": 300,
                "source": "builtin",
                "module_path": "src.collectors.zdaye_collector",
                "class_name": "ZdayeCollector",
                "env_vars": {}
            }
        ]
        
        with patch.object(CollectorManager, '_load_builtin_collector'):
            manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
            status = manager.get_all_status()
            
            self.assertIn("running", status)
            self.assertIn("collectors_count", status)
            self.assertIn("stats", status)
    
    def test_run_collector_once_not_found(self):
        """测试手动执行不存在的收集器"""
        collectors_config = []
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
        
        result = manager.run_collector_once("non_existent")
        self.assertIsNone(result)

    def test_run_collector_loop_should_skip_cooldown_blocked_proxy_from_store_result(self):
        collectors_config = []
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, collectors_config)
        proxy = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        executor = Mock()
        executor.fetch_proxies.return_value = [proxy]
        helper_result = {
            "stored": False,
            "created": False,
            "proxy_key": "proxy:http:1.2.3.4:8080",
            "cooldown_blocked": True,
        }
        manager._running = True
        manager._running_flags["test_collector"] = True

        def stop_after_first_sleep(_seconds):
            manager._running_flags["test_collector"] = False

        with patch(
            "src.collectors.manager.store_proxy_with_cooldown_awareness",
            return_value=helper_result,
        ) as mock_helper, patch("src.collectors.manager.time.sleep", side_effect=stop_after_first_sleep):
            manager._run_collector_loop("test_collector", executor, interval=1, is_builtin=True)

        mock_helper.assert_called_once_with(self.mock_redis, proxy)
        self.mock_logger.warning.assert_not_called()
        self.mock_logger.info.assert_any_call(
            "收集器 [test_collector] 采集到 1 个代理",
            extra={"component": "COLLECTOR", "collector": "test_collector", "count": 1}
        )
        self.assertEqual(manager._stats["last_collection_count"], 1)
        self.assertEqual(manager._stats["raw_count"], 1)
        self.assertEqual(manager._stats["stored_count"], 0)
        self.assertEqual(manager._stats["cooldown_blocked_count"], 1)
        self.assertEqual(manager._last_status["test_collector"]["raw_count"], 1)
        self.assertEqual(manager._last_status["test_collector"]["stored_count"], 0)
        self.assertEqual(manager._last_status["test_collector"]["cooldown_blocked_count"], 1)
        self.assertEqual(manager._last_status["test_collector"]["queue_length"], 0)

    def test_get_status_should_expose_split_collection_counts(self):
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, [])
        manager._stats["total_collected"] = 24
        manager._stats["collection_attempts"] = 6
        manager._stats["successful_collections"] = 4
        manager._stats["last_collection_count"] = 9
        manager._stats["raw_count"] = 9
        manager._stats["stored_count"] = 6
        manager._stats["cooldown_blocked_count"] = 3
        manager._start_time = 1700000000

        with patch("src.collectors.manager.time.time", return_value=1700000600):
            status = manager.get_status()

        stats = status["stats"]
        self.assertEqual(stats["raw_count"], 9)
        self.assertEqual(stats["stored_count"], 6)
        self.assertEqual(stats["cooldown_blocked_count"], 3)
        self.assertEqual(stats["queue_length"], 6)

    def test_apply_runtime_config_should_update_collector_interval(self):
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, [])
        manager._collectors = [
            (
                "ZdayeCollector",
                Mock(),
                10,
                {"id": "zdaye", "class_name": "ZdayeCollector", "interval_seconds": 10},
                True
            )
        ]
        manager._running = True
        manager._threads["ZdayeCollector"] = Mock()
        self.mock_config.ZDAYE_COLLECT_INTERVAL = 90
        self.mock_config.COLLECT_INTERVAL_SECONDS = 300

        with patch.object(manager, "reload_collector") as mock_reload:
            affected = manager.apply_runtime_config(["ZDAYE_COLLECT_INTERVAL"])

        self.assertIn("ZdayeCollector", affected)
        self.assertEqual(manager._collectors[0][2], 90)
        mock_reload.assert_called_once_with("ZdayeCollector")

    def test_zdaye_intervals_should_use_specific_config_keys(self):
        manager = CollectorManager(self.mock_config, self.mock_logger, self.mock_redis, [])
        self.mock_config.COLLECT_INTERVAL_SECONDS = 300
        self.mock_config.ZDAYE_COLLECT_INTERVAL = 12
        self.mock_config.ZDAYE_OVERSEAS_COLLECT_INTERVAL = 34

        module_mapping = {
            "src.collectors.zdaye_collector": Mock(ZdayeCollector=_DummyCollector),
            "src.collectors.zdaye_overseas_collector": Mock(ZdayeOverseasCollector=_DummyOverseasCollector),
        }

        with patch("importlib.import_module", side_effect=lambda name: module_mapping[name]):
            manager._load_builtin_collector({
                "id": "zdaye",
                "name": "站大爷",
                "enabled": True,
                "source": "builtin",
                "module_path": "src.collectors.zdaye_collector",
                "class_name": "ZdayeCollector",
                "env_vars": {}
            })
            manager._load_builtin_collector({
                "id": "zdaye_overseas",
                "name": "站大爷海外",
                "enabled": True,
                "source": "builtin",
                "module_path": "src.collectors.zdaye_overseas_collector",
                "class_name": "ZdayeOverseasCollector",
                "env_vars": {}
            })

        zdaye_interval = manager._collectors[0][2]
        overseas_interval = manager._collectors[1][2]
        self.assertEqual(zdaye_interval, 12)
        self.assertEqual(overseas_interval, 34)


if __name__ == "__main__":
    unittest.main()
