# Collector V2 Web UI 配置教程

> 当前有效 Collector V2 使用文档，其他历史设计与迁移材料已归档到 `docs/archive/`。

相关入口：

- 日常系统使用：`docs/guides/usage-guide.md`
- 本地开发与联调：`docs/guides/development-guide.md`
- 文档导航：`docs/README.md`

**适用对象**

本文只面向通过 Web UI 配置收集器的用户。你不需要会写 Python，也不需要会操作命令行。

**本文目标**

读完后你应该能完成下面这些操作：

- 在“收集器管理”页面新建一个 V2 收集器
- 用 `simple` 模式配置一个 API 型收集器
- 用 `simple + scrape` 模式配置一个支持分页的页面抓取收集器
- 先做测试运行，再发布到正式运行
- 看懂运行结果和常见错误
- 判断什么时候该切到专家模式
- 理解分页配置应该怎么接入
- 以站大爷免费代理接口为例，照着完成一个真实可用的配置

**快速导航**

- 只想快速上手：先看第 3 节和第 4 节
- 想理解 simple 模式到底会生成什么：看第 5 节
- 想知道页面限制和注意事项：看第 8 节
- 测试运行结果看不懂：看第 7 节和第 9 节

## 1. 使用前提

在开始之前，请先确认以下前提已经满足：

- 你已经可以正常打开 Web UI。
- 左侧菜单里已经能看到“收集器管理”页面。
- 管理员已经启用 V2 收集器功能；如果页面里根本没有“收集器管理”，说明这一步还没开。
- 你已经拿到站大爷的 `app_id` 和 `akey`。
- 你的 API Token 已经在前端配置完成，否则页面请求会报 401。

## 2. 先理解 V2 收集器页面

进入“收集器管理”后，你会接触到几个核心概念：

- `草稿（draft）`
  新建后的收集器默认是草稿状态。草稿不会自动执行，只能手动测试。
- `已发布（published）`
  发布后才会进入正式运行状态，参与调度。
- `已暂停（paused）`
  暂停后不会继续调度，但配置会保留，可以稍后恢复。
- `测试运行（Test Run）`
  用当前配置立即跑一次，不代表已经上线，只是验证配置对不对。
- `Collector Worker`
  这是负责执行 V2 收集器任务的后台工作进程。如果页面顶部显示它离线，说明 V2 调度没有真正运行起来，需要管理员处理。
- `冷却池 / 冷却阻断`
  当前页面会把冷却中的代理单独统计。它表示代理暂时被系统隔离，不等同于这次收集器运行失败。

## 3. Web UI 配置流程总览

推荐你始终按下面顺序操作：

1. 新建收集器
2. 填写基础信息
3. 填写简单模式表单
4. 保存
5. 点击“测试运行”
6. 查看测试结果
7. 确认结果正常后点击“发布”
8. 后续需要临时停用时点击“暂停”，恢复时点击“恢复”

不要跳过“测试运行”直接发布。当前后端要求最近一次测试运行必须成功或部分成功，否则发布会失败。

### 3.1 新建收集器前先判断 3 个问题

在真正点“新建收集器”之前，先判断下面这 3 件事：

1. 目标数据是接口返回 JSON，还是网页 / HTML 页面？
2. 当前逻辑能不能只靠一组请求 + 一组提取 + 一组字段映射完成？
3. 目标站点有没有分页，或者有没有敏感参数需要你自己维护？

推荐选择方式：

- 接口返回 JSON，且规则比较直白：
  选 `简单模式 + API`
- HTML 页面抓取，能靠 CSS/XPath 取到列表：
  选 `简单模式 + Scrape`
- 需要分页、特殊流程、额外底层字段，或者必须手写 `spec`：
  选 `专家模式`

### 3.2 命名和配置建议

为了后面排查和管理方便，建议新收集器至少包含这些信息：

- 名称里体现来源站点，例如 `zdaye_free_v2`
- 名称里体现类型，例如 `api` / `scrape`
- 执行间隔先保守设置成 `300` 或更长
- 第一次创建后先做“测试运行”，不要直接发布

## 4. 站大爷示例：从零创建一个可用的 V2 收集器

这一节是全文最重要的部分。你可以直接照着做。

### 4.1 这个示例对应什么

本示例对应项目里原本的“站大爷免费代理”收集器，核心逻辑是：

- 请求地址：`http://www.zdopen.com/FreeProxy/Get/`
- 请求方式：`GET`
- 返回格式：JSON
- 真正的代理列表路径：`$.data.proxy_list[*]`
- 每条代理里关心的字段：`ip`、`port`、`protocol`、`level`
- 因为这是大陆接口，所以国家统一写成 `CN`

### 4.2 在页面中填写基础字段

点击“新建收集器”后，建议按下面填写：

- 名称：`站大爷免费代理 V2`
- 模式：`简单模式`
- 来源：`API`
- 执行间隔(秒)：`300`

说明：

- `300` 表示每 5 分钟执行一次。
- 当前页面的最小间隔是 `60` 秒。
- 创建时页面默认启用，不需要你额外勾选。
- 创建时不会让你手填 ID，系统会根据名称自动生成，创建后 ID 不建议再改。

### 4.3 在简单模式里填写请求、提取和字段映射

把其中的 `your_app_id_here` 和 `your_akey_here` 替换成你自己的值。页面上建议这样填：

- `请求 URL`
  `http://www.zdopen.com/FreeProxy/Get/`
- `请求方法`
  `GET`
- `请求超时(秒)`
  `10`
- `请求参数(JSON)`

```json
{
  "count": 100,
  "app_id": "your_app_id_here",
  "akey": "your_akey_here",
  "dalu": 1,
  "return_type": 3
}
```

- `请求头(JSON)`

```json
{
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
```

- `提取类型`
  `jsonpath`
- `提取表达式`
  `$.data.proxy_list[*]`
- `IP 字段`
  `ip`
- `端口字段`
  `port`
- `协议字段`
  `protocol`
- `国家代码`
  选择“固定值”，填 `CN`
- `匿名度字段`
  `level`

页面保存时会自动生成底层 `spec`。对于想核对底层结构的同学，上面这组表单最终等价于下面这段 JSON：

```json
{
  "request": {
    "url": "http://www.zdopen.com/FreeProxy/Get/",
    "method": "GET",
    "timeout_seconds": 10,
    "params": {
      "count": 100,
      "app_id": "your_app_id_here",
      "akey": "your_akey_here",
      "dalu": 1,
      "return_type": 3
    },
    "headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
  },
  "extract": {
    "type": "jsonpath",
    "expression": "$.data.proxy_list[*]"
  },
  "field_mapping": {
    "ip": "ip",
    "port": "port",
    "protocol": "protocol",
    "country_code": "const:CN",
    "anonymity_level": "level"
  }
}
```

### 4.4 这些表单分别是什么意思

`request`

- 定义向哪个接口发请求。
- `params` 里的字段就是站大爷 API 所需参数。
- `dalu: 1` 表示抓大陆代理。
- `return_type: 3` 表示让接口返回 JSON。

`extract`

- 定义如何从返回结果里找到代理列表。
- `type: jsonpath` 表示返回体按 JSON 解析。
- `expression: $.data.proxy_list[*]` 表示从 `data.proxy_list` 中提取每一项。

`field_mapping`

- 定义每个代理条目要映射成什么字段。
- `ip`、`port`、`protocol` 直接取接口原字段。
- `country_code` 用 `const:CN` 固定写成中国。
- `anonymity_level` 对应站大爷返回的 `level`。

### 4.4.1 海外站大爷的国家字段转换写法

如果你配置的是海外站大爷接口，国家信息通常不适合直接取 `adr` 原值，因为它可能是：

- `美国 洛杉矶`
- `日本东京 Amazon数据中心`
- `韩国 KT电信`

这类值不能直接当作系统里的 `country_code` 使用。当前页面里你可以把“国家代码”切到“文本转代码”，值填写 `adr`，默认值填写 `Unknown`。底层会生成下面这段配置：

```json
{
  "country_code": {
    "expression": "adr",
    "transform": "country_text_to_code",
    "default": "Unknown"
  }
}
```

说明：

- `expression: adr` 表示先取站大爷返回的 `adr` 字段
- `transform: country_text_to_code` 表示由后端内置规则自动转换为 ISO 国家代码
- `default: Unknown` 表示无法识别时回退为 `Unknown`

这个转换器会复用项目内置的国家映射数据，你不需要在每个收集器配置里手写整张国家映射表。

### 4.5 保存后先做测试运行

保存成功后，在列表中找到刚创建的收集器，点击“测试运行”。

你应该重点看这几个结果：

- `状态`
  最理想是“成功”，次优是“部分成功”。
- `raw`
  原始抓到多少条记录。
- `valid`
  通过代理数据校验的数量。
- `stored`
  当前版本的测试运行里，这个值通常等于 `valid`，可以理解为“可入库数量”。
- `duplicate`
  当前版本测试运行里通常为 `0`。

如果 `raw > 0` 但 `valid = 0`，通常说明提取到了数据，但字段格式不符合系统要求。

### 4.6 测试通过后再发布

测试运行结果正常后，点击“发布”。

发布后，收集器会从 `draft` 进入 `published`，才会进入正式调度。

如果你收到发布失败提示，最常见原因就是：

- 还没有做过测试运行
- 最近一次测试运行是失败状态

### 4.7 发布后如何判断它真的在工作

你可以从这几个地方看：

- 收集器列表中的状态是否已经变成已发布
- 顶部 `Collector Worker` 是否显示“运行中”
- 运行记录里是否出现新的执行记录
- 日志页面里是否能看到对应的 `collector_id` / `run_id`

如果收集器已经发布，但 `Collector Worker` 一直显示离线，那么不是这条配置本身有问题，而是 V2 后台工作进程没有正常运行，需要管理员处理。

### 4.8 新收集器配置模板

下面给你 3 套当前版本最常见的新建模板。

#### 模板 A：API 型 simple 收集器

适用场景：

- 目标站点直接返回 JSON
- 代理列表路径清晰
- 不需要手写复杂流程

建议填写：

- 模式：`简单模式`
- 来源：`API`
- 请求 URL：目标接口地址
- 请求方法：通常是 `GET`
- 提取类型：通常是 `jsonpath`
- 提取表达式：例如 `$.data.items[*]`
- `IP 字段` / `端口字段`：必须填
- `协议字段` / `国家代码` / `匿名度字段`：建议补齐

#### 模板 B：Scrape 型 simple 收集器

适用场景：

- 目标站点返回 HTML
- 你能用 CSS 或 XPath 找到每一行代理

推荐选择：

- 模式：`简单模式`
- 来源：`Scrape`
- 提取类型：
  - 页面结构稳定时优先 `css`
  - 节点关系复杂时可选 `xpath`

常见写法示例：

```json
{
  "extract": {
    "type": "css",
    "expression": ".proxy-row"
  },
  "field_mapping": {
    "ip": ".ip::text",
    "port": ".port::text",
    "protocol": ".protocol::text"
  }
}
```

#### 模板 C：需要分页的新收集器

适用场景：

- 接口按页返回数据
- 第 1 页、第 2 页结构一致
- 你希望把多页结果自动累积

当前版本说明：

- simple engine 已支持 `pagination`
- Web UI 已支持在 `简单模式 + Scrape` 下通过表单配置分页
- 如果你配置的是 `简单模式 + API`，这类场景目前仍建议直接走 `专家模式`

最小分页配置示例：

```json
{
  "request": {
    "url": "https://example.com/api/proxies",
    "method": "GET",
    "params": {
      "page_size": 100
    }
  },
  "pagination": {
    "page_param": "page",
    "start_page": 1,
    "max_pages": 5,
    "stop_when_empty": true
  },
  "extract": {
    "type": "jsonpath",
    "expression": "$.data.items[*]"
  },
  "field_mapping": {
    "ip": "ip",
    "port": "port",
    "protocol": "protocol"
  }
}
```

## 5. simple 模式底层 `spec` 对照说明

对 Web UI 用户来说，简单模式优先直接填写结构化表单。这里保留底层 `spec` 说明，方便你对照页面字段和运行时结构。

### 5.1 `request`

常见字段如下：

- `url`
  必填。请求地址。
- `method`
  可选。默认 `GET`，也可以填 `POST`。
- `headers`
  可选。请求头。
- `params`
  可选。查询参数。
- `data`
  可选。表单请求体。
- `json`
  可选。JSON 请求体。
- `timeout_seconds`
  可选。单次请求超时时间。

### 5.1.1 `pagination`

如果目标站点按页返回代理列表，simple engine 支持一个最小分页协议。当前版本里，这组分页字段已经可以直接通过 Web UI 的 `简单模式 + Scrape` 表单配置：

- `page_param`
  页码参数名，例如 `page`
- `start_page`
  从第几页开始，默认 `1`
- `max_pages`
  最多抓多少页
- `stop_when_empty`
  是否在某一页提取结果为空时提前停止；默认 `false`

示例：

```json
{
  "request": {
    "url": "https://example.com/api/proxies",
    "method": "GET",
    "params": {
      "page_size": 100
    }
  },
  "pagination": {
    "page_param": "page",
    "start_page": 1,
    "max_pages": 5,
    "stop_when_empty": true
  }
}
```

说明：

- 执行时会基于 `request.params` 复制一份请求参数，再按页写入 `page_param`
- 每一页抓到的结果会自动累积
- 分页控件只会在 `简单模式` 且 `来源 = Scrape` 时显示
- 如果你配置的是 `简单模式 + API`，当前 Web UI 仍不会显示分页控件；这类场景暂时需要切到专家模式手动编辑底层 `spec`

页面字段和底层 `spec.pagination` 的对应关系如下：

- `启用分页`
  打开后才会在保存时生成 `pagination`
- `页码参数名`
  对应 `page_param`
- `起始页`
  对应 `start_page`
- `最大页数`
  对应 `max_pages`
- `遇到空页即停止`
  对应 `stop_when_empty`

### 5.2 `extract`

用于说明“从哪里取出代理列表”。支持三种类型：

- `jsonpath`
  适合 API 返回 JSON 的场景。
- `css`
  适合 HTML 页面抓取。
- `xpath`
  适合 HTML/XML 页面抓取。

常见写法：

```json
{
  "type": "jsonpath",
  "expression": "$.data.proxy_list[*]"
}
```

### 5.3 `field_mapping`

用于把提取出来的每一条记录映射成系统能识别的代理字段。

最重要的字段是：

- `ip`
- `port`

强烈建议同时提供：

- `protocol`
- `country_code`
- `anonymity_level`

示例：

```json
{
  "ip": "ip",
  "port": "port",
  "protocol": "protocol",
  "country_code": "const:CN",
  "anonymity_level": "level"
}
```

支持的常见写法：

- 直接取字段：`"ip": "ip"`
- 固定值：`"country_code": "const:CN"`
- CSS 文本提取：`"ip": ".ip::text"`
- XPath 提取：`"ip": "./td[1]/text()"`

### 5.4 系统对代理字段的基本要求

当前校验规则中，最少要满足：

- 必须有 `ip`
- 必须有 `port`

另外：

- `port` 最终必须能转换成整数
- `protocol` 如果提供，必须是 `http`、`https`、`socks4`、`socks5` 之一
- `country_code` 和 `anonymity_level` 不填也能过，但建议填

## 6. 页面字段完整说明

### 6.1 名称

这是页面展示名称。建议取一个容易识别的名字，比如：

- `站大爷免费代理 V2`
- `站大爷大陆 HTTP 代理`

### 6.2 模式

- `简单模式`
  通过结构化表单描述请求、提取和字段映射，适合绝大多数 API 型场景。
- `专家模式`
  需要手动编辑 `Spec(JSON)` 和 `CodeRef(JSON)`，更适合自定义 Python 代码，不适合纯 Web UI 用户。

如果你只是想把一个现成 API 接到系统里，优先选“简单模式”。

### 6.3 来源

- `API`
  表示数据来自接口。
- `Scrape`
  表示数据来自网页抓取。

对当前版本来说，这个字段主要是标记来源类型，便于管理和辨认。简单模式下真正的请求与提取逻辑来自表单内容；专家模式下仍然取决于 `Spec(JSON)`。

### 6.4 执行间隔(秒)

表示发布后多久执行一次。

建议：

- 不熟悉目标接口时先用 `300`
- 不要一上来就设成过短间隔

### 6.5 启用状态

编辑时可以看到。它和“发布状态”不是一回事：

- `enabled = true` 只是代表这个定义允许被调度
- 是否真正运行，还要看它是不是已经发布

一个 `draft` 收集器即使 `enabled = true`，也不会自动执行。

### 6.6 `CodeRef(JSON)`

只有专家模式才需要。纯 Web UI 用户通常不用碰它。

### 6.7 专家模式使用建议

专家模式适合下面几类场景：

- simple 模式表单覆盖不了你的抓取逻辑
- 你需要手动维护底层 `spec`
- 你已经准备好了对应的 `code_ref` 文件或执行入口

进入专家模式后，页面会要求你同时维护：

- `Spec(JSON)`
  描述请求、提取或其他底层运行参数
- `CodeRef(JSON)`
  描述代码入口，例如文件名

当前页面会在提交前做基础 JSON 校验：

- 如果 `Spec(JSON)` 不是合法对象 JSON，会直接阻止提交
- 如果 `CodeRef(JSON)` 不是合法对象 JSON，也会直接阻止提交

建议：

- 先在简单模式能完成的范围内优先用简单模式
- 专家模式提交前先做一次“测试运行”
- 已发布收集器如果要改核心配置，先暂停再编辑

## 7. 测试运行结果怎么解读

### 7.1 状态

- `成功`
  采集到了数据，而且所有关键校验都通过。
- `部分成功`
  采集到了部分有效数据，但也有部分条目格式不合格。
- `失败`
  没有拿到可用结果，或者 `raw_count`、`stored_count` 为 0。
- `超时`
  请求或执行过程超过了后端允许的最长时间。

### 7.2 五个统计字段

- `raw`
  从接口或页面原始提取出来的记录数。
- `valid`
  通过数据校验的记录数。
- `stored`
  当前版本中可以理解为“最终可入库数量估算”。
- `duplicate`
  当前版本测试运行里通常为 `0`。
- `冷却阻断`
  表示本次提取和校验都通过了，但命中了系统里的冷却池，所以没有继续入库。它是说明性指标，不等同于失败。

### 7.3 如何快速判断问题在什么环节

- `raw = 0`
  通常是请求失败，或者 `extract.expression` 写错了。
- `raw > 0` 但 `valid = 0`
  通常是 `field_mapping` 有问题，尤其是 `ip`、`port`、`protocol`。
- `valid > 0` 但 `stored = 0` 且 `冷却阻断 > 0`
  说明这次抓到了可用代理，但它们仍在冷却池里，先看是否是重复命中同一批代理。
- `valid > 0` 但发布后没看到调度
  通常是还没发布，或者 `Collector Worker` 没启动。

## 8. 当前 Web UI 版本的已知限制

这一节很重要，尤其是你只通过 UI 操作时。

### 8.1 当前页面没有单独的 `env_vars` 输入框

虽然 V2 后端支持 `env_vars`，但当前前端创建和编辑时会固定提交空对象。

这意味着：

- 你现在不能在页面上单独保存 `app_id`、`akey` 这类环境变量
- 像站大爷这种需要凭据的场景，只能先把凭据直接写进 `Spec(JSON)`

所以本文的站大爷示例才会把：

- `app_id`
- `akey`

直接写在 `request.params` 中。

如果你所在环境对敏感信息管理要求较高，这部分应由管理员提供后续方案，比如补前端能力或改成后端统一注入。

### 8.2 已发布的收集器不能直接修改核心配置

当前后端规则是：

- `draft`
  可编辑
- `paused`
  可编辑
- `published`
  只能做基础更新，不能直接改 `Spec`、`CodeRef`、执行间隔等核心配置

如果你想改核心配置，推荐流程是：

1. 先暂停
2. 再编辑
3. 再测试运行
4. 再重新发布

## 9. 常见问题

### 9.1 测试运行报 JSON 解析失败

通常说明：

- 简单模式里的 `请求参数(JSON)`、`请求头(JSON)`、`表单体(JSON)` 或 `JSON Body(JSON)` 不是合法 JSON
- 或者你在专家模式下填写的 `Spec(JSON)` / `CodeRef(JSON)` 不是合法 JSON
- 多了中文引号
- 少了逗号或引号

建议先把对应 JSON 放到格式化工具里检查一遍，再粘回页面。

### 9.2 测试运行报缺少 `ip` 或 `port`

说明 `field_mapping` 没有正确映射到目标字段。

优先检查：

- `extract.expression` 取出来的到底是不是一条代理对象
- `field_mapping.ip` 和 `field_mapping.port` 是否写对

### 9.3 测试运行成功，但发布失败

最常见原因：

- 最近一次运行不是“成功”或“部分成功”
- 你创建后还没做测试运行就直接发布

### 9.4 保存时报“published collector only supports basic updates”

说明你正在编辑一个已发布的收集器，并且修改了后端不允许直接修改的字段。

正确做法：

1. 先暂停
2. 再修改
3. 再测试运行
4. 再发布

### 9.5 顶部 `Collector Worker` 显示未运行

这通常不是简单模式表单或 `Spec(JSON)` 写错了，而是系统层面问题。常见原因有：

- 管理员没有启用 Collector V2
- V2 Worker 没有启动
- 后台心跳没有正常上报

对纯 Web UI 用户来说，这类问题需要联系管理员处理。

### 9.6 创建后为什么没有立刻自动跑

因为新建后的收集器默认是 `draft`。只有发布后才会进入正式调度。

## 10. 站大爷模板汇总

如果你只想快速照抄，这里再给一份最终模板。

基础字段建议：

- 名称：`站大爷免费代理 V2`
- 模式：`简单模式`
- 来源：`API`
- 执行间隔(秒)：`300`

简单模式表单建议这样填：

- `请求 URL`
  `http://www.zdopen.com/FreeProxy/Get/`
- `请求方法`
  `GET`
- `请求超时(秒)`
  `10`
- `请求参数(JSON)`

```json
{
  "count": 100,
  "app_id": "your_app_id_here",
  "akey": "your_akey_here",
  "dalu": 1,
  "return_type": 3
}
```

- `请求头(JSON)`

```json
{
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
```

- `提取类型`
  `jsonpath`
- `提取表达式`
  `$.data.proxy_list[*]`
- `IP 字段`
  `ip`
- `端口字段`
  `port`
- `协议字段`
  `protocol`
- `国家代码`
  选择“固定值”，填 `CN`
- `匿名度字段`
  `level`

底层等价 `Spec(JSON)`：

```json
{
  "request": {
    "url": "http://www.zdopen.com/FreeProxy/Get/",
    "method": "GET",
    "timeout_seconds": 10,
    "params": {
      "count": 100,
      "app_id": "your_app_id_here",
      "akey": "your_akey_here",
      "dalu": 1,
      "return_type": 3
    },
    "headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
  },
  "extract": {
    "type": "jsonpath",
    "expression": "$.data.proxy_list[*]"
  },
  "field_mapping": {
    "ip": "ip",
    "port": "port",
    "protocol": "protocol",
    "country_code": "const:CN",
    "anonymity_level": "level"
  }
}
```

### 10.1 Simple + Scrape 分页模板

如果你要抓的是按页展示的 HTML 页面，可以直接在 `简单模式 + Scrape` 下用表单配置分页。一个常见示例如下：

- 名称：`示例页面代理抓取`
- 模式：`简单模式`
- 来源：`Scrape`
- 执行间隔(秒)：`300`
- `请求 URL`
  `https://example.com/free-proxy-list`
- `请求方法`
  `GET`
- `提取类型`
  `css`
- `提取表达式`
  `table.proxy-list tbody tr`
- `IP 字段`
  `td:nth-child(1)::text`
- `端口字段`
  `td:nth-child(2)::text`
- `协议字段`
  `const:http`
- `启用分页`
  打开
- `页码参数名`
  `page`
- `起始页`
  `1`
- `最大页数`
  `5`
- `遇到空页即停止`
  打开

这组表单底层会生成：

```json
{
  "request": {
    "url": "https://example.com/free-proxy-list",
    "method": "GET",
    "timeout_seconds": 10
  },
  "extract": {
    "type": "css",
    "expression": "table.proxy-list tbody tr"
  },
  "field_mapping": {
    "ip": "td:nth-child(1)::text",
    "port": "td:nth-child(2)::text",
    "protocol": "const:http"
  },
  "pagination": {
    "page_param": "page",
    "start_page": 1,
    "max_pages": 5,
    "stop_when_empty": true
  }
}
```

## 11. 一句话建议

如果你是第一次接触 V2 收集器，不要一开始就做复杂的网页抓取。先用像站大爷这样返回 JSON 的 API 跑通完整流程，再去尝试更复杂的 `css` 或 `xpath` 提取。
