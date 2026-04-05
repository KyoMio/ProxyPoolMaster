// web-ui/src/api/apiClient.ts
import axios from 'axios';
import { ElMessage } from 'element-plus';
import { normalizeApiBaseUrl } from './baseUrl';

// 后端API的基地址
// 在实际部署中，这个地址应该从环境变量或配置文件中获取
// 生产环境使用相对路径，开发环境可以使用完整URL
const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL); // 自动兼容 http://host 与 http://host/api/v1 两种配置

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 10秒超时
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器，用于添加API Token
apiClient.interceptors.request.use(
  (config) => {
    // 从localStorage或其他地方获取API Token
    const apiToken = localStorage.getItem('api_token');
    if (apiToken) {
      config.headers['X-API-Token'] = apiToken;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器，用于处理全局错误，例如API Token过期
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response;
      if (status === 401) {
        // API Token 无效或过期
        console.error('API Token 无效或缺失:', data.detail);
        ElMessage.error('API Token invalid, please check settings');
      } else {
        console.error(`API 请求错误: ${status} - ${data.detail || error.message}`);
      }
    } else if (error.request) {
      // 请求已发出但未收到响应
      console.error('API 请求无响应:', error.request);
    } else {
      // 发送请求时发生错误
      console.error('API 请求发送失败:', error.message);
    }
    return Promise.reject(error);
  }
);

/**
 * API 接口定义
 */

// 获取随机代理
export const getRandomProxy = async () => {
  const response = await apiClient.get('/random');
  return response.data;
};

// 获取带筛选条件的代理列表
export const getProxies = async (params?: {
  country_code?: string
  protocol?: string
  grade?: string
  anonymity_level?: string
  is_available?: boolean
  limit?: number
  page?: number
  size?: number
}) => {
  const response = await apiClient.get('/get', { params });
  return response.data;
};

// ===========================================
//  Dashboard 页面相关 API
// ===========================================

// 获取 Dashboard 概览数据 (总代理数, 可用代理数, 平均延迟, 最近更新)
export const getDashboardOverview = async () => {
  const response = await apiClient.get('/dashboard/overview');
  return response.data;
};

// 获取代理类型分布数据
export const getProxyTypeDistribution = async () => {
  const response = await apiClient.get('/dashboard/proxy_type_distribution');
  return response.data;
};

// 获取代理匿名度分布数据
export const getAnonymityDistribution = async () => {
  const response = await apiClient.get('/dashboard/anonymity_distribution');
  return response.data;
};

// 获取按国家分布的代理数量数据
export const getCountryDistribution = async () => {
  const response = await apiClient.get('/dashboard/country_distribution');
  return response.data;
};


// ===========================================
//  System Status 页面相关 API
// ===========================================

// 获取系统整体状态 (Redis, API, Collector等)
export const getSystemStatus = async () => {
  const response = await apiClient.get('/system/status');
  return response.data;
};

// 获取各个模块的详细运行状态
export const getModuleStatus = async () => {
  const response = await apiClient.get('/system/modules');
  return response.data;
};

// 获取系统性能指标
export const getSystemMetrics = async () => {
  const response = await apiClient.get('/system/metrics');
  return response.data;
};

// 获取历史指标数据（用于图表）
export const getMetricsHistory = async (metric: string, timeRange: string = '1h') => {
  const response = await apiClient.get('/system/metrics/history', {
    params: { metric, time_range: timeRange }
  });
  return response.data;
};


// ===========================================
//  Log 页面相关 API
// ===========================================

// 获取日志数据
export const getLogs = async (params?: {
  level?: string
  min_level?: string
  component?: string
  exclude_components?: string
  keyword?: string
  collector_id?: string
  run_id?: string
  page?: number
  size?: number
}) => {
  const response = await apiClient.get('/logs', { params });
  return response.data;
};

export const clearLogs = async (): Promise<{
  message: string;
  removed_files: number;
}> => {
  const response = await apiClient.post('/logs/clear');
  return response.data;
};


// ===========================================
//  Config 页面相关 API
// ===========================================

// 获取所有配置数据
export const getConfig = async (): Promise<{
  global_config: Record<string, any>;
  collector_configs: any[];
  config_sources: {
    from_env: string[];
    from_file: string[];
    using_defaults: string[];
  };
}> => {
  const response = await apiClient.get('/config/');
  return response.data;
};

export const getRuntimeInfo = async (): Promise<{
  image_tag: string;
  release_version: string;
  git_sha: string;
  label: string;
}> => {
  const response = await apiClient.get('/runtime-info');
  return response.data;
};

// 保存全局配置数据
export const saveGlobalConfig = async (data: {
  config: Record<string, any>;
  save_to_file?: boolean;
  include_secrets?: boolean;
}): Promise<{
  message: string;
  updated_keys: string[];
  file_saved: boolean;
  config_sources: {
    from_env: string[];
    from_file: string[];
    using_defaults: string[];
  };
  runtime_apply?: {
    applied_keys: string[];
    requires_restart: string[];
  };
  requires_restart?: string[];
}> => {
  // 维持前端契约：调用 /config/global，由后端负责兼容别名
  const response = await apiClient.post('/config/global', data);
  return response.data;
};

// 保存单个收集器配置数据
export const updateCollectorConfig = async (collectorId: number, configData: any) => {
  const response = await apiClient.put(`/config/collector/${collectorId}`, configData);
  return response.data;
};

// 添加新收集器配置
export const addCollectorConfig = async (configData: any) => {
  const response = await apiClient.post('/config/collector', configData);
  return response.data;
};

// 删除收集器配置
export const deleteCollectorConfig = async (collectorId: number) => {
  const response = await apiClient.delete(`/config/collector/${collectorId}`);
  return response.data;
};

// Test API connection with given token
export async function testApiConnection(token: string): Promise<{ success: boolean; message?: string }> {
  try {
    const apiBaseUrl = normalizeApiBaseUrl(import.meta.env.VITE_API_BASE_URL)
    const response = await fetch(`${apiBaseUrl}/system/status`, {
      headers: {
        'X-API-Token': token
      }
    })
    if (response.ok) {
      return { success: true }
    } else if (response.status === 401) {
      return { success: false, message: 'Invalid token' }
    } else {
      return { success: false, message: `HTTP ${response.status}` }
    }
  } catch (error: any) {
    return { success: false, message: error.message }
  }
}

// ===========================================
//  Collector 页面相关 API
// ===========================================

// 收集器管理 API
export const collectorApi = {
  getCollectors: () => apiClient.get('/collectors-v2'),

  getCollector: (id: string) => apiClient.get(`/collectors-v2/${id}`),

  createCollector: (data: {
    id?: string
    name: string
    mode: 'simple' | 'code'
    source: 'api' | 'scrape'
    enabled: boolean
    interval_seconds: number
    spec: Record<string, any>
    code_ref?: Record<string, any> | null
    env_vars?: Record<string, { value: string; is_secret: boolean }>
  }) => apiClient.post('/collectors-v2', data),

  updateCollector: (id: string, data: {
    name?: string
    enabled?: boolean
    interval_seconds?: number
    spec?: Record<string, any>
    code_ref?: Record<string, any> | null
    env_vars?: Record<string, { value: string; is_secret: boolean }>
  }) => apiClient.put(`/collectors-v2/${id}`, data),

  deleteCollector: (id: string) => apiClient.delete(`/collectors-v2/${id}`),

  testRunCollector: (id: string, trigger: 'test' | 'manual' = 'test') =>
    apiClient.post(`/collectors-v2/${id}/test-run`, { trigger }),

  publishCollector: (id: string, skip_test_validation = false) =>
    apiClient.post(`/collectors-v2/${id}/publish`, { skip_test_validation }),

  pauseCollector: (id: string) => apiClient.post(`/collectors-v2/${id}/pause`),

  resumeCollector: (id: string) => apiClient.post(`/collectors-v2/${id}/resume`),

  getCollectorRuns: (id: string, limit = 20) =>
    apiClient.get(`/collectors-v2/${id}/runs`, { params: { limit } }),
}

export default apiClient;
