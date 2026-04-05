<template>
  <div class="config-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">配置管理</h1>
      <div class="page-actions">
        <el-button plain @click="showAdvancedSettings = !showAdvancedSettings">
          <el-icon><Setting /></el-icon>
          {{ showAdvancedSettings ? '隐藏高级设置' : '显示高级设置' }}
        </el-button>
        <el-tag v-if="hasEnvOverrides" type="warning" effect="dark" size="large" class="env-warning-tag">
          <el-icon><Warning /></el-icon>
          <span>部分配置由环境变量控制</span>
        </el-tag>
      </div>
    </div>

    <!-- 全局加载状态 -->
    <el-skeleton :rows="10" animated v-if="initialLoading" />

    <template v-else>
      <!-- 卡片 1: Redis 配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Coin /></el-icon>
            <span>Redis 配置</span>
          </div>
        </template>
        <el-form :model="config.redis" label-width="140px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="Redis 主机">
                <el-input 
                  v-model="config.redis.REDIS_HOST" 
                  placeholder="localhost"
                  :disabled="isEnvOverridden('REDIS_HOST')"
                >
                  <template #append v-if="isEnvOverridden('REDIS_HOST')">
                    <el-tag type="warning" size="small">环境变量</el-tag>
                  </template>
                </el-input>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Redis 端口">
                <el-input-number 
                  v-model="config.redis.REDIS_PORT" 
                  :min="1" 
                  :max="65535"
                  :disabled="isEnvOverridden('REDIS_PORT')"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="数据库编号">
                <el-input-number 
                  v-model="config.redis.REDIS_DB" 
                  :min="0" 
                  :max="15"
                  :disabled="isEnvOverridden('REDIS_DB')"
                  style="width: 100%"
                />
              </el-form-item>
            </el-col>
            <el-col v-if="showAdvancedSettings" :span="12">
              <el-form-item label="访问密码">
                <el-input 
                  v-model="config.redis.REDIS_PASSWORD" 
                  type="password"
                  placeholder="可选"
                  show-password
                  :disabled="isEnvOverridden('REDIS_PASSWORD')"
                >
                  <template #append v-if="isEnvOverridden('REDIS_PASSWORD')">
                    <el-tag type="warning" size="small">环境变量</el-tag>
                  </template>
                </el-input>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 卡片 2: 日志配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Document /></el-icon>
            <span>日志配置</span>
          </div>
        </template>
        <el-form :model="config.logging" label-width="140px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="日志级别">
                <el-select 
                  v-model="config.logging.LOG_LEVEL" 
                  placeholder="选择日志级别" 
                  style="width: 100%"
                  :disabled="isEnvOverridden('LOG_LEVEL')"
                >
                  <el-option label="DEBUG" value="DEBUG" />
                  <el-option label="INFO" value="INFO" />
                  <el-option label="WARNING" value="WARNING" />
                  <el-option label="ERROR" value="ERROR" />
                  <el-option label="CRITICAL" value="CRITICAL" />
                </el-select>
                <div v-if="isEnvOverridden('LOG_LEVEL')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="时区">
                <el-select 
                  v-model="config.logging.TIMEZONE" 
                  placeholder="选择时区" 
                  style="width: 100%"
                  :disabled="isEnvOverridden('TIMEZONE')"
                >
                  <el-option label="Asia/Shanghai (北京时间)" value="Asia/Shanghai" />
                  <el-option label="Asia/Tokyo (东京)" value="Asia/Tokyo" />
                  <el-option label="Asia/Seoul (首尔)" value="Asia/Seoul" />
                  <el-option label="America/New_York (纽约)" value="America/New_York" />
                  <el-option label="America/Los_Angeles (洛杉矶)" value="America/Los_Angeles" />
                  <el-option label="Europe/London (伦敦)" value="Europe/London" />
                  <el-option label="Europe/Paris (巴黎)" value="Europe/Paris" />
                  <el-option label="UTC (协调世界时)" value="UTC" />
                </el-select>
                <div v-if="isEnvOverridden('TIMEZONE')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row v-if="showAdvancedSettings" :gutter="20">
            <el-col :span="12">
              <el-form-item label="文件最大大小">
                <el-select 
                  v-model="config.logging.LOG_MAX_BYTES" 
                  style="width: 100%"
                  :disabled="isEnvOverridden('LOG_MAX_BYTES')"
                >
                  <el-option label="1 MB" :value="1048576" />
                  <el-option label="5 MB" :value="5242880" />
                  <el-option label="10 MB" :value="10485760" />
                  <el-option label="50 MB" :value="52428800" />
                  <el-option label="100 MB" :value="104857600" />
                </el-select>
                <div v-if="isEnvOverridden('LOG_MAX_BYTES')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="备份文件数量">
                <el-slider 
                  v-model="config.logging.LOG_BACKUP_COUNT" 
                  :min="0" 
                  :max="10"
                  show-stops
                  show-input
                  :disabled="isEnvOverridden('LOG_BACKUP_COUNT')"
                />
                <div v-if="isEnvOverridden('LOG_BACKUP_COUNT')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 卡片 3: 代理收集配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Connection /></el-icon>
            <span>代理收集配置</span>
          </div>
        </template>
        <el-form :model="config.collector" label-width="140px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="请求超时">
                <el-slider
                  v-model="config.collector.REQUEST_TIMEOUT"
                  :min="1"
                  :max="60"
                  show-stops
                  show-input
                  :disabled="isEnvOverridden('REQUEST_TIMEOUT')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('REQUEST_TIMEOUT')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>收集器和测试器 HTTP 请求超时时间（秒）</template>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="全局收集间隔">
                <time-input-with-unit
                  v-model="config.collector.COLLECT_INTERVAL_SECONDS"
                  :disabled="isEnvOverridden('COLLECT_INTERVAL_SECONDS')"
                />
                <div v-if="isEnvOverridden('COLLECT_INTERVAL_SECONDS')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row v-if="showAdvancedSettings" :gutter="20">
            <el-col :span="12">
              <el-form-item label="收集器模式">
                <el-select
                  v-model="config.collector.COLLECTOR_RUNTIME_MODE"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_RUNTIME_MODE')"
                >
                  <el-option label="legacy" value="legacy" />
                  <el-option label="v2" value="v2" />
                  <el-option label="disabled" value="disabled" />
                </el-select>
                <div class="form-tip">
                  <template v-if="isEnvOverridden('COLLECTOR_RUNTIME_MODE')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>默认推荐使用 v2，由独立 collector worker 执行采集任务</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 卡片 4: 代理检测配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Search /></el-icon>
            <span>代理检测配置</span>
          </div>
        </template>
        <el-form :model="config.tester" label-width="140px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="检测间隔">
                <time-input-with-unit 
                  v-model="config.tester.TEST_INTERVAL_SECONDS" 
                  :disabled="isEnvOverridden('TEST_INTERVAL_SECONDS')"
                />
                <div v-if="isEnvOverridden('TEST_INTERVAL_SECONDS')" class="form-tip">
                  <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最大失败次数">
                <el-slider 
                  v-model="config.tester.MAX_FAIL_COUNT" 
                  :min="1" 
                  :max="20"
                  show-stops
                  show-input
                  :disabled="isEnvOverridden('MAX_FAIL_COUNT')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('MAX_FAIL_COUNT')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>代理连续失败的最大次数，超过则删除</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item v-if="showAdvancedSettings" label="逐代理 INFO 日志">
            <el-switch
              v-model="config.tester.TESTER_LOG_EACH_PROXY"
              :disabled="isEnvOverridden('TESTER_LOG_EACH_PROXY')"
            />
            <div class="form-tip">
              <template v-if="isEnvOverridden('TESTER_LOG_EACH_PROXY')">
                <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
              </template>
              <template v-else>默认关闭，排障时可临时开启（日志量会明显增加）</template>
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 卡片 5: 测试器高级配置 -->
      <el-card v-if="showAdvancedSettings" shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Lightning /></el-icon>
            <span>测试器高级配置</span>
          </div>
        </template>
        <el-form :model="config.testerAdvanced" label-width="140px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="最大并发数">
                <el-input-number 
                  v-model="config.testerAdvanced.TEST_MAX_CONCURRENT" 
                  :min="10" 
                  :max="500"
                  style="width: 100%"
                  :disabled="isEnvOverridden('TEST_MAX_CONCURRENT')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_MAX_CONCURRENT')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>同时测试的代理最大数量</template>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="单目标超时">
                <el-slider 
                  v-model="config.testerAdvanced.TEST_TIMEOUT_PER_TARGET" 
                  :min="1" 
                  :max="30"
                  show-stops
                  show-input
                  :disabled="isEnvOverridden('TEST_TIMEOUT_PER_TARGET')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_TIMEOUT_PER_TARGET')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>单个目标测试超时时间（秒）</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="单批测试数量">
                <el-input-number
                  v-model="config.testerAdvanced.TEST_BATCH_SIZE"
                  :min="1"
                  :max="5000"
                  style="width: 100%"
                  :disabled="isEnvOverridden('TEST_BATCH_SIZE')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_BATCH_SIZE')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>每轮测试批次的代理数量</template>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="空闲休眠秒数">
                <el-input-number
                  v-model="config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS"
                  :min="1"
                  :max="60"
                  style="width: 100%"
                  :disabled="isEnvOverridden('TEST_IDLE_SLEEP_SECONDS')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_IDLE_SLEEP_SECONDS')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>没有待测任务时的轮询休眠时间</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="测试调度 Key">
                <el-input
                  v-model="config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY"
                  placeholder="proxies:test_schedule"
                  :disabled="isEnvOverridden('TEST_SCHEDULE_ZSET_KEY')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_SCHEDULE_ZSET_KEY')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>用于测试调度的 Redis ZSet 键</template>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="迁移批次数量">
                <el-input-number
                  v-model="config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE"
                  :min="1"
                  :max="5000"
                  style="width: 100%"
                  :disabled="isEnvOverridden('TEST_MIGRATION_BATCH_SIZE')"
                />
                <div class="form-tip">
                  <template v-if="isEnvOverridden('TEST_MIGRATION_BATCH_SIZE')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>迁移旧调度数据时的批次大小</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 卡片 6: 测试目标配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Link /></el-icon>
            <span>测试目标配置</span>
            <el-tag v-if="isEnvOverridden('TEST_TARGETS')" type="warning" size="small" style="margin-left: 8px;">环境变量</el-tag>
          </div>
        </template>
        <div class="test-targets-section">
          <el-tag
            v-for="(target, index) in config.testTargets"
            :key="index"
            :closable="!isEnvOverridden('TEST_TARGETS')"
            type="info"
            size="large"
            class="target-tag"
            @close="removeTestTarget(index)"
          >
            {{ target }}
          </el-tag>
          <el-input
            v-if="targetInputVisible && !isEnvOverridden('TEST_TARGETS')"
            ref="targetInputRef"
            v-model="targetInputValue"
            size="small"
            class="target-input"
            placeholder="输入URL后按回车"
            @keyup.enter="addTestTarget"
            @blur="addTestTarget"
          />
          <el-button 
            v-else-if="!isEnvOverridden('TEST_TARGETS')" 
            size="small" 
            type="primary" 
            plain
            @click="showTargetInput"
          >
            <el-icon><Plus /></el-icon>
            添加测试目标
          </el-button>
        </div>
        <div class="form-tip" style="margin-top: 12px;">
          <template v-if="isEnvOverridden('TEST_TARGETS')">
            <el-tag type="warning" size="small" effect="plain">由环境变量配置，不可修改</el-tag>
          </template>
          <template v-else>测试代理时访问的目标网站列表，必须以 http:// 或 https:// 开头。至少保留一个目标。</template>
        </div>
      </el-card>

      <!-- 卡片 7: API 配置 -->
      <el-card shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Lock /></el-icon>
            <span>API 配置</span>
          </div>
        </template>
        <el-form :model="config.api" label-width="140px" class="config-form">
          <!-- API Token - 环境变量配置模式 -->
          <el-form-item label="API Token">
            <template v-if="isEnvOverridden('API_TOKEN')">
              <!-- 环境变量配置：只读，仅允许复制 -->
              <div class="env-config-display">
                <el-input 
                  v-model="config.api.API_TOKEN" 
                  :type="showToken ? 'text' : 'password'"
                  disabled
                  style="width: 400px"
                >
                  <template #append>
                    <el-button @click="showToken = !showToken" title="显示/隐藏">
                      <el-icon><View v-if="!showToken" /><Hide v-else /></el-icon>
                    </el-button>
                  </template>
                </el-input>
                <el-button type="primary" @click="copyApiToken" style="margin-left: 8px;">
                  <el-icon><CopyDocument /></el-icon>
                  复制 Token
                </el-button>
                <el-alert
                  type="info"
                  :closable="false"
                  show-icon
                  class="env-config-alert"
                  style="margin-top: 8px;"
                >
                  <template #title>
                    API Token 由环境变量配置，仅支持查看和复制
                  </template>
                </el-alert>
              </div>
            </template>
            <template v-else>
              <!-- 非环境变量配置：允许编辑 -->
              <el-input 
                v-model="config.api.API_TOKEN" 
                :type="showToken ? 'text' : 'password'"
              >
                <template #append>
                  <el-button @click="showToken = !showToken">
                    <el-icon><View v-if="!showToken" /><Hide v-else /></el-icon>
                  </el-button>
                  <el-button @click="copyApiToken">
                    <el-icon><CopyDocument /></el-icon>
                  </el-button>
                  <el-button @click="generateNewToken">
                    <el-icon><Refresh /></el-icon>
                  </el-button>
                </template>
              </el-input>
              <div class="form-tip">用于访问后端 API 的认证令牌，请妥善保管</div>
            </template>
          </el-form-item>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="代理接口限流">
                <el-input 
                  v-model="config.api.RATE_LIMIT_PROXY_MINUTE" 
                  placeholder="60/minute"
                  :disabled="isEnvOverridden('RATE_LIMIT_PROXY_MINUTE')"
                >
                  <template #append v-if="isEnvOverridden('RATE_LIMIT_PROXY_MINUTE')">
                    <el-tag type="warning" size="small">环境变量</el-tag>
                  </template>
                </el-input>
                <div class="form-tip">
                  <template v-if="isEnvOverridden('RATE_LIMIT_PROXY_MINUTE')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>格式: 数字/时间单位 (如 60/minute)</template>
                </div>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="健康检查限流">
                <el-input 
                  v-model="config.api.RATE_LIMIT_HEALTH_MINUTE" 
                  placeholder="30/minute"
                  :disabled="isEnvOverridden('RATE_LIMIT_HEALTH_MINUTE')"
                >
                  <template #append v-if="isEnvOverridden('RATE_LIMIT_HEALTH_MINUTE')">
                    <el-tag type="warning" size="small">环境变量</el-tag>
                  </template>
                </el-input>
                <div class="form-tip">
                  <template v-if="isEnvOverridden('RATE_LIMIT_HEALTH_MINUTE')">
                    <el-tag type="warning" size="small" effect="plain">由环境变量配置</el-tag>
                  </template>
                  <template v-else>格式: 数字/时间单位 (如 30/minute)</template>
                </div>
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card v-if="showAdvancedSettings" shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span>Collector Worker 高级配置</span>
          </div>
        </template>
        <el-form :model="config.worker" label-width="160px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="启用 Worker">
                <el-switch
                  v-model="config.worker.COLLECTOR_WORKER_ENABLED"
                  :active-value="1"
                  :inactive-value="0"
                  :disabled="isEnvOverridden('COLLECTOR_WORKER_ENABLED')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Worker ID">
                <el-input
                  v-model="config.worker.COLLECTOR_WORKER_ID"
                  :disabled="isEnvOverridden('COLLECTOR_WORKER_ID')"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="Tick 间隔（秒）">
                <el-input-number
                  v-model="config.worker.COLLECTOR_WORKER_TICK_SECONDS"
                  :min="1"
                  :max="60"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_WORKER_TICK_SECONDS')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最大并发任务数">
                <el-input-number
                  v-model="config.worker.COLLECTOR_WORKER_MAX_CONCURRENT"
                  :min="1"
                  :max="64"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_WORKER_MAX_CONCURRENT')"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <el-card v-if="showAdvancedSettings" shadow="hover" class="config-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><Setting /></el-icon>
            <span>执行隔离高级配置</span>
          </div>
        </template>
        <el-form :model="config.execution" label-width="160px" class="config-form">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="执行超时（秒）">
                <el-input-number
                  v-model="config.execution.COLLECTOR_EXEC_TIMEOUT"
                  :min="1"
                  :max="600"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_EXEC_TIMEOUT')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="最大内存（MB）">
                <el-input-number
                  v-model="config.execution.COLLECTOR_EXEC_MAX_MEMORY_MB"
                  :min="64"
                  :max="2048"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_EXEC_MAX_MEMORY_MB')"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="标准输出限制（KB）">
                <el-input-number
                  v-model="config.execution.COLLECTOR_EXEC_STDOUT_LIMIT_KB"
                  :min="64"
                  :max="2048"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_EXEC_STDOUT_LIMIT_KB')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="运行记录保留数">
                <el-input-number
                  v-model="config.execution.COLLECTOR_RUN_HISTORY_LIMIT"
                  :min="1"
                  :max="1000"
                  style="width: 100%"
                  :disabled="isEnvOverridden('COLLECTOR_RUN_HISTORY_LIMIT')"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-card>

      <!-- 卡片 8: 配置操作 -->
      <el-card shadow="hover" class="action-card">
        <template #header>
          <div class="card-header">
            <el-icon class="card-icon"><DocumentChecked /></el-icon>
            <span>配置操作</span>
          </div>
        </template>
        
        <div class="action-buttons">
          <el-button type="primary" size="large" @click="saveAllConfig" :loading="saving">
            <el-icon><DocumentChecked /></el-icon>
            保存到运行时配置文件
          </el-button>
          
          <el-button size="large" @click="resetChanges" :disabled="saving">
            <el-icon><RefreshRight /></el-icon>
            重置当前修改
          </el-button>
          
          <el-button size="large" type="warning" plain @click="restoreDefaults" :disabled="saving">
            <el-icon><RefreshLeft /></el-icon>
            恢复默认配置
          </el-button>
        </div>
        
        <el-alert
          v-if="hasEnvOverrides"
          type="warning"
          :closable="false"
          show-icon
          class="action-alert"
        >
          <template #title>
            部分配置项被环境变量覆盖，修改后将不会生效。建议直接修改 .env 文件。
          </template>
        </el-alert>
        
        <el-alert
          type="info"
          :closable="false"
          show-icon
          class="action-alert"
        >
          <template #title>
            配置将保存到运行时配置文件；本地默认路径为 <code>config.json</code>，容器内默认路径为 <code>/app/data/config/config.json</code>。
            环境变量 (.env) 的优先级高于配置文件。
          </template>
        </el-alert>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Coin,
  Connection,
  Document,
  Search,
  Lightning,
  Link,
  Lock,
  DocumentChecked,
  View,
  Hide,
  CopyDocument,
  Refresh,
  RefreshRight,
  RefreshLeft,
  Plus,
  Setting,
  Warning,
} from '@element-plus/icons-vue';
import { getConfig, saveGlobalConfig } from '@/api/apiClient';
import TimeInputWithUnit from '@/components/TimeInputWithUnit.vue';

// 加载状态
const initialLoading = ref(true);
const saving = ref(false);
const showAdvancedSettings = ref(false);

// 配置来源（环境变量/文件/默认值）
const configSource = ref<{
  from_env: string[];
  from_file: string[];
  using_defaults: string[];
}>({
  from_env: [],
  from_file: [],
  using_defaults: [],
});

// 原始配置（用于重置）
const originalConfig = ref<any>(null);

// 表单数据模型
const config = reactive({
  redis: {
    REDIS_HOST: 'localhost',
    REDIS_PORT: 6379,
    REDIS_DB: 0,
    REDIS_PASSWORD: '',
  },
  logging: {
    LOG_LEVEL: 'INFO',
    LOG_MAX_BYTES: 10485760,
    LOG_BACKUP_COUNT: 5,
    TIMEZONE: 'Asia/Shanghai',
  },
  collector: {
    COLLECTOR_RUNTIME_MODE: 'v2',
    REQUEST_TIMEOUT: 10,
    COLLECT_INTERVAL_SECONDS: 300,
  },
  tester: {
    TEST_INTERVAL_SECONDS: 300,
    MAX_FAIL_COUNT: 5,
    TESTER_LOG_EACH_PROXY: false,
  },
  testerAdvanced: {
    TEST_MAX_CONCURRENT: 100,
    TEST_TIMEOUT_PER_TARGET: 5,
    TEST_BATCH_SIZE: 200,
    TEST_IDLE_SLEEP_SECONDS: 2,
    TEST_SCHEDULE_ZSET_KEY: 'proxies:test_schedule',
    TEST_MIGRATION_BATCH_SIZE: 500,
  },
  worker: {
    COLLECTOR_WORKER_ENABLED: 1,
    COLLECTOR_WORKER_ID: 'collector-worker-1',
    COLLECTOR_WORKER_TICK_SECONDS: 1,
    COLLECTOR_WORKER_MAX_CONCURRENT: 4,
  },
  execution: {
    COLLECTOR_EXEC_TIMEOUT: 60,
    COLLECTOR_EXEC_MAX_MEMORY_MB: 256,
    COLLECTOR_EXEC_STDOUT_LIMIT_KB: 256,
    COLLECTOR_RUN_HISTORY_LIMIT: 200,
  },
  testTargets: [] as string[],
  api: {
    API_TOKEN: '',
    RATE_LIMIT_PROXY_MINUTE: '60/minute',
    RATE_LIMIT_HEALTH_MINUTE: '30/minute',
  },
});

// Token 显示/隐藏
const showToken = ref(false);

// 测试目标输入
const targetInputVisible = ref(false);
const targetInputValue = ref('');
const targetInputRef = ref<HTMLInputElement | null>(null);

// 计算是否被环境变量覆盖
const isEnvOverridden = (key: string): boolean => {
  return configSource.value.from_env.includes(key);
};

// 计算是否有环境变量覆盖
const hasEnvOverrides = computed(() => {
  return configSource.value.from_env.length > 0;
});

// 加载配置
const fetchConfig = async () => {
  initialLoading.value = true;
  try {
    const response = await getConfig();
    const { global_config, config_sources } = response;

    // 保存原始配置用于重置
    originalConfig.value = JSON.parse(JSON.stringify(global_config));

    // 保存配置来源
    if (config_sources) {
      configSource.value = config_sources;
    }

    // 填充表单数据
    config.redis.REDIS_HOST = global_config.REDIS_HOST ?? 'localhost';
    config.redis.REDIS_PORT = global_config.REDIS_PORT ?? 6379;
    config.redis.REDIS_DB = global_config.REDIS_DB ?? 0;
    config.redis.REDIS_PASSWORD = global_config.REDIS_PASSWORD ?? '';

    config.logging.LOG_LEVEL = global_config.LOG_LEVEL ?? 'INFO';
    config.logging.LOG_MAX_BYTES = global_config.LOG_MAX_BYTES ?? 10485760;
    config.logging.LOG_BACKUP_COUNT = global_config.LOG_BACKUP_COUNT ?? 5;
    config.logging.TIMEZONE = global_config.TIMEZONE ?? 'Asia/Shanghai';

    config.collector.COLLECTOR_RUNTIME_MODE = global_config.COLLECTOR_RUNTIME_MODE ?? 'v2';
    config.collector.REQUEST_TIMEOUT = global_config.REQUEST_TIMEOUT ?? 10;
    config.collector.COLLECT_INTERVAL_SECONDS = global_config.COLLECT_INTERVAL_SECONDS ?? 300;

    config.tester.TEST_INTERVAL_SECONDS = global_config.TEST_INTERVAL_SECONDS ?? 300;
    config.tester.MAX_FAIL_COUNT = global_config.MAX_FAIL_COUNT ?? 5;
    config.tester.TESTER_LOG_EACH_PROXY = global_config.TESTER_LOG_EACH_PROXY ?? false;

    config.testerAdvanced.TEST_MAX_CONCURRENT = global_config.TEST_MAX_CONCURRENT ?? 100;
    config.testerAdvanced.TEST_TIMEOUT_PER_TARGET = global_config.TEST_TIMEOUT_PER_TARGET ?? 5;
    config.testerAdvanced.TEST_BATCH_SIZE = global_config.TEST_BATCH_SIZE ?? 200;
    config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS = global_config.TEST_IDLE_SLEEP_SECONDS ?? 2;
    config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY = global_config.TEST_SCHEDULE_ZSET_KEY ?? 'proxies:test_schedule';
    config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE = global_config.TEST_MIGRATION_BATCH_SIZE ?? 500;

    config.worker.COLLECTOR_WORKER_ENABLED = global_config.COLLECTOR_WORKER_ENABLED ?? 1;
    config.worker.COLLECTOR_WORKER_ID = global_config.COLLECTOR_WORKER_ID ?? 'collector-worker-1';
    config.worker.COLLECTOR_WORKER_TICK_SECONDS = global_config.COLLECTOR_WORKER_TICK_SECONDS ?? 1;
    config.worker.COLLECTOR_WORKER_MAX_CONCURRENT = global_config.COLLECTOR_WORKER_MAX_CONCURRENT ?? 4;

    config.execution.COLLECTOR_EXEC_TIMEOUT = global_config.COLLECTOR_EXEC_TIMEOUT ?? 60;
    config.execution.COLLECTOR_EXEC_MAX_MEMORY_MB = global_config.COLLECTOR_EXEC_MAX_MEMORY_MB ?? 256;
    config.execution.COLLECTOR_EXEC_STDOUT_LIMIT_KB = global_config.COLLECTOR_EXEC_STDOUT_LIMIT_KB ?? 256;
    config.execution.COLLECTOR_RUN_HISTORY_LIMIT = global_config.COLLECTOR_RUN_HISTORY_LIMIT ?? 200;

    config.testTargets = global_config.TEST_TARGETS ?? [
      'http://www.baidu.com',
      'http://www.qq.com',
      'http://www.sina.com.cn',
      'http://www.163.com',
    ];

    config.api.API_TOKEN = global_config.API_TOKEN ?? '';
    config.api.RATE_LIMIT_PROXY_MINUTE = global_config.RATE_LIMIT_PROXY_MINUTE ?? '60/minute';
    config.api.RATE_LIMIT_HEALTH_MINUTE = global_config.RATE_LIMIT_HEALTH_MINUTE ?? '30/minute';

  } catch (error: any) {
    ElMessage.error('获取配置失败: ' + (error.response?.data?.detail || error.message));
    console.error('Failed to fetch config:', error);
  } finally {
    initialLoading.value = false;
  }
};

// 保存所有配置
const saveAllConfig = async () => {
  // 验证测试目标
  if (config.testTargets.length === 0) {
    ElMessage.error('至少需要一个测试目标');
    return;
  }

  // 验证 URL 格式
  const invalidTarget = config.testTargets.find(
    (url) => !url.startsWith('http://') && !url.startsWith('https://')
  );
  if (invalidTarget) {
    ElMessage.error(`无效的测试目标: ${invalidTarget}`);
    return;
  }

  saving.value = true;
  try {
    // 合并所有配置
    const configToSave = {
      ...config.redis,
      ...config.logging,
      ...config.collector,
      ...config.tester,
      ...config.testerAdvanced,
      ...config.worker,
      ...config.execution,
      TEST_TARGETS: config.testTargets,
      ...config.api,
    };

    const saveResult = await saveGlobalConfig({
      config: configToSave,
      save_to_file: true,
      include_secrets: false,
    });
    const restartKeys = saveResult.requires_restart ?? saveResult.runtime_apply?.requires_restart ?? [];
    if (restartKeys.length > 0) {
      ElMessage.warning(`配置已保存，以下配置需重启后生效: ${restartKeys.join(', ')}`);
    } else {
      ElMessage.success('配置已保存并已热更新生效');
    }
    
    // 重新加载配置以确保一致性
    await fetchConfig();
  } catch (error: any) {
    ElMessage.error('保存配置失败: ' + (error.response?.data?.detail || error.message));
    console.error('Failed to save config:', error);
  } finally {
    saving.value = false;
  }
};

// 重置当前修改
const resetChanges = () => {
  ElMessageBox.confirm('确定要重置所有修改吗？未保存的更改将丢失。', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      fetchConfig();
      ElMessage.info('已重置为当前系统配置');
    })
    .catch(() => {
      // 用户取消
    });
};

// 恢复默认配置
const restoreDefaults = () => {
  ElMessageBox.confirm(
    '确定要恢复默认配置吗？这将重置所有配置项为初始值。',
    '警告',
    {
      confirmButtonText: '确定恢复',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(() => {
      // 设置默认值
      config.redis.REDIS_HOST = 'localhost';
      config.redis.REDIS_PORT = 6379;
      config.redis.REDIS_DB = 0;
      config.redis.REDIS_PASSWORD = '';

      config.logging.LOG_LEVEL = 'INFO';
      config.logging.LOG_MAX_BYTES = 10485760;
      config.logging.LOG_BACKUP_COUNT = 5;
      config.logging.TIMEZONE = 'Asia/Shanghai';

      config.collector.COLLECTOR_RUNTIME_MODE = 'v2';
      config.collector.REQUEST_TIMEOUT = 10;
      config.collector.COLLECT_INTERVAL_SECONDS = 300;

      config.tester.TEST_INTERVAL_SECONDS = 300;
      config.tester.MAX_FAIL_COUNT = 5;
      config.tester.TESTER_LOG_EACH_PROXY = false;

      config.testerAdvanced.TEST_MAX_CONCURRENT = 100;
      config.testerAdvanced.TEST_TIMEOUT_PER_TARGET = 5;
      config.testerAdvanced.TEST_BATCH_SIZE = 200;
      config.testerAdvanced.TEST_IDLE_SLEEP_SECONDS = 2;
      config.testerAdvanced.TEST_SCHEDULE_ZSET_KEY = 'proxies:test_schedule';
      config.testerAdvanced.TEST_MIGRATION_BATCH_SIZE = 500;

      config.worker.COLLECTOR_WORKER_ENABLED = 1;
      config.worker.COLLECTOR_WORKER_ID = 'collector-worker-1';
      config.worker.COLLECTOR_WORKER_TICK_SECONDS = 1;
      config.worker.COLLECTOR_WORKER_MAX_CONCURRENT = 4;

      config.execution.COLLECTOR_EXEC_TIMEOUT = 60;
      config.execution.COLLECTOR_EXEC_MAX_MEMORY_MB = 256;
      config.execution.COLLECTOR_EXEC_STDOUT_LIMIT_KB = 256;
      config.execution.COLLECTOR_RUN_HISTORY_LIMIT = 200;

      config.testTargets = [
        'http://www.baidu.com',
        'http://www.qq.com',
        'http://www.sina.com.cn',
        'http://www.163.com',
      ];

      config.api.RATE_LIMIT_PROXY_MINUTE = '60/minute';
      config.api.RATE_LIMIT_HEALTH_MINUTE = '30/minute';

      ElMessage.success('已恢复默认配置，请记得保存');
    })
    .catch(() => {
      // 用户取消
    });
};

// 复制 API Token
const copyApiToken = () => {
  if (!config.api.API_TOKEN) {
    ElMessage.warning('没有可复制的 API Token');
    return;
  }
  navigator.clipboard.writeText(config.api.API_TOKEN).then(() => {
    ElMessage.success('API Token 已复制到剪贴板');
  }).catch(() => {
    ElMessage.error('复制失败，请手动复制');
  });
};

// 生成新 Token
const generateNewToken = () => {
  ElMessageBox.confirm('确定要生成新的 API Token 吗？旧 Token 将立即失效。', '警告', {
    confirmButtonText: '确定生成',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(() => {
      // 生成随机 Token
      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
      let token = '';
      for (let i = 0; i < 32; i++) {
        token += chars.charAt(Math.floor(Math.random() * chars.length));
      }
      config.api.API_TOKEN = token;
      ElMessage.success('已生成新的 API Token，请记得保存');
    })
    .catch(() => {
      // 用户取消
    });
};

// 显示测试目标输入框
const showTargetInput = () => {
  targetInputVisible.value = true;
  nextTick(() => {
    targetInputRef.value?.focus();
  });
};

// 添加测试目标
const addTestTarget = () => {
  const url = targetInputValue.value.trim();
  if (url) {
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      ElMessage.error('测试目标必须以 http:// 或 https:// 开头');
      targetInputVisible.value = false;
      targetInputValue.value = '';
      return;
    }
    if (config.testTargets.includes(url)) {
      ElMessage.warning('该测试目标已存在');
    } else {
      config.testTargets.push(url);
      ElMessage.success('已添加测试目标');
    }
  }
  targetInputVisible.value = false;
  targetInputValue.value = '';
};

// 删除测试目标
const removeTestTarget = (index: number) => {
  if (config.testTargets.length <= 1) {
    ElMessage.error('至少保留一个测试目标');
    return;
  }
  config.testTargets.splice(index, 1);
  ElMessage.success('已删除测试目标');
};

// 组件挂载时加载配置
onMounted(() => {
  fetchConfig();
});
</script>

<style scoped>
.config-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.config-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-icon {
  margin-right: 8px;
  font-size: 18px;
}

.config-form {
  width: 100%;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.5;
}

/* 环境变量覆盖时，禁用控件统一呈现灰色输入态 */
:deep(.el-input.is-disabled .el-input__wrapper),
:deep(.el-textarea.is-disabled .el-textarea__inner),
:deep(.el-input-number.is-disabled .el-input__wrapper),
:deep(.el-select .el-input.is-disabled .el-input__wrapper) {
  background-color: #f2f3f5 !important;
  box-shadow: 0 0 0 1px #e5e7eb inset !important;
}

/* 测试目标标签样式 */
.test-targets-section {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.target-tag {
  margin-right: 0;
}

.target-input {
  width: 200px;
}

/* 环境变量配置显示样式 */
.env-config-display {
  width: 100%;
}

.env-config-alert {
  margin-top: 8px;
}

/* 参数预览样式 */
.params-preview {
  background-color: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-size: 12px;
  margin: 0;
}

/* 操作卡片样式 */
.action-card {
  margin-top: 20px;
  background-color: #f5f7fa;
}

.action-buttons {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.action-alert {
  margin-top: 12px;
}

.action-alert:first-of-type {
  margin-top: 0;
}

/* 环境变量警示条样式 */
.env-warning-tag {
  height: auto;
  padding: 8px 12px;
  line-height: 1.5;
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.env-warning-tag :deep(.el-tag__content) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.env-warning-tag .el-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.env-warning-tag span {
  white-space: nowrap;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .config-container {
    padding: 12px;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .page-actions {
    justify-content: flex-start;
  }

  .config-form :deep(.el-form-item__label) {
    float: none;
    display: block;
    text-align: left;
    padding: 0 0 8px;
    line-height: 1.5;
  }

  .action-buttons {
    flex-direction: column;
  }

  .action-buttons .el-button {
    width: 100%;
    margin-left: 0 !important;
  }
}
</style>
