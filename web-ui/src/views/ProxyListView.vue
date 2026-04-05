<template>
  <div class="proxy-list-container">
    <!-- 筛选卡片 -->
    <el-card shadow="hover" class="filter-card">
      <template #header>
        <div class="card-header">
          <span>代理筛选</span>
          <el-button type="primary" :icon="Refresh" @click="fetchProxies" :loading="loading">
            刷新
          </el-button>
        </div>
      </template>
      <!-- 筛选条件表单 - 多行布局 -->
      <el-form :model="filterForm" class="filter-form">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="可用性">
              <el-select v-model="filterForm.is_available" placeholder="选择可用性" clearable style="width: 100%">
                <el-option label="全部" value=""></el-option>
                <el-option label="B级及以上" :value="true">
                  <el-tag type="success" size="small">B级及以上</el-tag>
                </el-option>
                <el-option label="B级以下" :value="false">
                  <el-tag type="danger" size="small">B级以下</el-tag>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="等级">
              <el-select v-model="filterForm.grade" placeholder="选择等级" clearable style="width: 100%">
                <el-option label="全部等级" value=""></el-option>
                <el-option label="S级 (完美)" value="S">
                  <el-tag type="success" size="small" effect="dark">S</el-tag>
                  <span style="margin-left: 8px">完美 (4目标)</span>
                </el-option>
                <el-option label="A级 (优秀)" value="A">
                  <el-tag type="primary" size="small" effect="dark">A</el-tag>
                  <span style="margin-left: 8px">优秀 (3目标)</span>
                </el-option>
                <el-option label="B级 (良好)" value="B">
                  <el-tag type="warning" size="small" effect="dark">B</el-tag>
                  <span style="margin-left: 8px">良好 (2目标)</span>
                </el-option>
                <el-option label="C级 (低通过率)" value="C">
                  <el-tag type="info" size="small" effect="dark">C</el-tag>
                  <span style="margin-left: 8px">低通过率 (1目标)</span>
                </el-option>
                <el-option label="D级 (不可用)" value="D">
                  <el-tag type="danger" size="small" effect="dark">D</el-tag>
                  <span style="margin-left: 8px">不可用</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="协议">
              <el-select v-model="filterForm.protocol" placeholder="选择协议" clearable style="width: 100%">
                <el-option label="全部协议" value=""></el-option>
                <el-option label="HTTP" value="http"></el-option>
                <el-option label="HTTPS" value="https"></el-option>
                <el-option label="SOCKS4" value="socks4"></el-option>
                <el-option label="SOCKS5" value="socks5"></el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="匿名度">
              <el-select v-model="filterForm.anonymity" placeholder="选择匿名度" clearable style="width: 100%">
                <el-option label="全部" value=""></el-option>
                <el-option label="高匿名" value="elite"></el-option>
                <el-option label="匿名" value="anonymous"></el-option>
                <el-option label="透明" value="transparent"></el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="国家/地区">
              <el-select v-model="filterForm.country" placeholder="选择国家" clearable filterable style="width: 100%">
                <el-option label="全部国家" value=""></el-option>
                <el-option 
                  v-for="(name, code) in countryCodeMap" 
                  :key="code" 
                  :label="name" 
                  :value="code"
                >
                  <span>{{ name }}</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">{{ code }}</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作">
              <div class="filter-actions">
                <el-button type="primary" @click="applyFilter">应用筛选</el-button>
                <el-button @click="resetFilter">重置</el-button>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 代理列表卡片 -->
    <el-card shadow="hover" class="list-card">
      <template #header>
        <div class="card-header">
          <span>代理列表</span>
          <el-tag type="info" size="small">共 {{ totalProxies }} 条</el-tag>
        </div>
      </template>
      
      <el-table 
        :data="proxyList" 
        style="width: 100%" 
        v-loading="loading"
        border
        stripe
        resizable
        :empty-text="emptyText"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="ip" label="IP" width="140" sortable="custom"></el-table-column>
        <el-table-column prop="port" label="端口" width="90" sortable="custom"></el-table-column>
        <el-table-column prop="protocol" label="协议" width="100" sortable="custom">
          <template #default="scope">
            <el-tag size="small" :type="getProtocolTagType(scope.row.protocol)">
              {{ scope.row.protocol.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="country" label="国家/地区" width="120" sortable="custom">
          <template #default="scope">
            {{ getCountryName(scope.row.country) }}
          </template>
        </el-table-column>
        <el-table-column prop="grade" label="等级" width="100" sortable="custom">
          <template #default="scope">
            <el-tag 
              size="small" 
              :type="getGradeTagType(scope.row.grade)"
              effect="dark"
            >
              {{ scope.row.grade || 'N/A' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="anonymity" label="匿名度" width="100" sortable="custom">
          <template #default="scope">
            {{ getAnonymityText(scope.row.anonymity) }}
          </template>
        </el-table-column>
        <el-table-column prop="responseTime" label="响应时间" width="130" sortable="custom">
          <template #default="scope">
            <span :class="getResponseTimeClass(scope.row.responseTime)">
              {{ scope.row.responseTime > 0 ? scope.row.responseTime + ' ms' : 'N/A' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="successCount" label="成功/失败" width="110" sortable="custom">
          <template #default="scope">
            <span style="color: #67c23a">{{ scope.row.successCount }}</span>
            <span style="color: #909399"> / </span>
            <span style="color: #f56c6c">{{ scope.row.failCount }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="lastCheckTime" label="最后检测时间" width="160" sortable="custom"></el-table-column>
        <el-table-column label="代理地址" min-width="200" show-overflow-tooltip>
          <template #default="scope">
            <code class="proxy-url">{{ scope.row.fullProxyString }}</code>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-block">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="totalProxies"
          background
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { getProxies } from '@/api/apiClient';
import countryCodeMap from '@/assets/country_code_to_zh.json';

// 筛选表单
const filterForm = ref({
  is_available: true,  // 默认显示 B级及以上代理
  grade: '',
  protocol: '',
  anonymity: '',
  country: ''
});

const proxyList = ref([]);
const loading = ref(false);
const currentPage = ref(1);
const pageSize = ref(20);
const totalProxies = ref(0);
const emptyText = ref('暂无数据');

// 排序状态
const sortState = ref({
  prop: '',
  order: ''
});

// 获取协议标签类型
const getProtocolTagType = (protocol) => {
  const types = {
    'http': '',
    'https': 'success',
    'socks4': 'warning',
    'socks5': 'danger'
  };
  return types[protocol?.toLowerCase()] || '';
};

// 获取等级标签类型
const getGradeTagType = (grade) => {
  const types = {
    'S': 'success',
    'A': 'primary',
    'B': 'warning',
    'C': 'info',
    'D': 'danger'
  };
  return types[grade] || 'info';
};

// 获取国家中文名
const getCountryName = (code) => {
  if (!code || code === 'Unknown') return '未知';
  return countryCodeMap[code] || code;
};

// 获取匿名度中文
const getAnonymityText = (level) => {
  const map = {
    'elite': '高匿名',
    'anonymous': '匿名',
    'transparent': '透明',
    'Unknown': '未知'
  };
  return map[level] || level || '未知';
};

// 获取响应时间样式类
const getResponseTimeClass = (time) => {
  if (time <= 0) return '';
  if (time < 1000) return 'response-fast';
  if (time < 3000) return 'response-normal';
  return 'response-slow';
};

// 处理排序变化
const handleSortChange = ({ prop, order }) => {
  sortState.value = { prop, order };
  // 前端排序
  if (prop && order) {
    proxyList.value.sort((a, b) => {
      let aVal = a[prop];
      let bVal = b[prop];
      
      // 处理数字排序
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return order === 'ascending' ? aVal - bVal : bVal - aVal;
      }
      
      // 处理字符串排序
      aVal = String(aVal || '').toLowerCase();
      bVal = String(bVal || '').toLowerCase();
      if (order === 'ascending') {
        return aVal.localeCompare(bVal);
      } else {
        return bVal.localeCompare(aVal);
      }
    });
  }
};

// 获取代理列表
const fetchProxies = async () => {
  loading.value = true;
  emptyText.value = '加载中...';
  
  try {
    const params = {
      page: currentPage.value,
      size: pageSize.value,
    };
    
    // 可用性筛选
    if (filterForm.value.is_available !== '') {
      params.is_available = filterForm.value.is_available;
    }
    
    // 协议筛选
    if (filterForm.value.protocol) {
      params.protocol = filterForm.value.protocol;
    }

    // 等级筛选
    if (filterForm.value.grade) {
      params.grade = filterForm.value.grade;
    }
    
    // 匿名度筛选
    if (filterForm.value.anonymity) {
      params.anonymity_level = filterForm.value.anonymity;
    }
    
    // 国家筛选
    if (filterForm.value.country) {
      params.country_code = filterForm.value.country;
    }
    
    const response = await getProxies(params);

    proxyList.value = (response.data || []).map(proxy => ({
      ip: proxy.ip,
      port: proxy.port,
      protocol: proxy.protocol?.toLowerCase() || 'http',
      country: proxy.country_code || 'Unknown',
      grade: proxy.grade || '',
      anonymity: proxy.anonymity_level || 'Unknown',
      responseTime: proxy.response_time ? Math.round(proxy.response_time * 1000) : 0,
      successCount: proxy.success_count || 0,
      failCount: proxy.fail_count || 0,
      lastCheckTime: proxy.last_check_time ? formatDate(proxy.last_check_time) : 'N/A',
      fullProxyString: `${proxy.protocol?.toLowerCase() || 'http'}://${proxy.ip}:${proxy.port}`
    }));
    
    // 应用当前排序
    if (sortState.value.prop && sortState.value.order) {
      handleSortChange(sortState.value);
    }
    
    totalProxies.value = response.total || 0;
    
    if (proxyList.value.length === 0) {
      emptyText.value = '暂无符合条件的代理';
    }
    
  } catch (error) {
    console.error('获取代理列表失败:', error);
    ElMessage.error('获取代理列表失败: ' + (error.response?.data?.detail || error.message));
    proxyList.value = [];
    totalProxies.value = 0;
    emptyText.value = '加载失败';
  } finally {
    loading.value = false;
  }
};

// 格式化日期
const formatDate = (timestamp) => {
  if (!timestamp) return 'N/A';
  try {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return 'N/A';
  }
};

// 应用筛选
const applyFilter = () => {
  currentPage.value = 1;
  fetchProxies();
};

// 重置筛选
const resetFilter = () => {
  filterForm.value = {
    is_available: true,  // 重置后仍默认显示 B级及以上代理
    grade: '',
    protocol: '',
    anonymity: '',
    country: ''
  };
  currentPage.value = 1;
  fetchProxies();
};

// 分页大小变化
const handleSizeChange = (val) => {
  pageSize.value = val;
  fetchProxies();
};

// 页码变化
const handleCurrentChange = (val) => {
  currentPage.value = val;
  fetchProxies();
};

onMounted(() => {
  fetchProxies();
});
</script>

<style scoped>
.proxy-list-container {
  padding: 20px;
}

.filter-card, .list-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.filter-form {
  margin-top: 10px;
}

.filter-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.filter-form :deep(.el-form-item__label) {
  font-weight: 500;
  color: #606266;
}

.filter-actions {
  display: flex;
  gap: 10px;
}

.pagination-block {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 响应时间样式 */
.response-fast {
  color: #67c23a;
  font-weight: 500;
}

.response-normal {
  color: #e6a23c;
  font-weight: 500;
}

.response-slow {
  color: #f56c6c;
  font-weight: 500;
}

/* 代理地址样式 */
.proxy-url {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
  color: #606266;
}

/* 表格优化 */
:deep(.el-table) {
  font-size: 13px;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
  font-weight: 600;
  color: #303133;
}

:deep(.el-table--border th) {
  border-right: 1px solid #ebeef5;
}
</style>
