# 钉钉消息 Webhook 转发器

一个类似于 Apprise 桥接功能的钉钉消息 Webhook 转发器，支持模板渲染和多种数据格式。

## 功能特性

1. **模板支持**: 通过 URL 参数 `template` 指定模板文件（位于 `config` 目录）
2. **JSON 变量提取**: 支持从嵌套 JSON 中通过点分隔路径引用变量（如 `alert.title`）
3. **表单参数**: 直接使用参数名作为变量
4. **Jinja2 模板引擎**: 支持条件判断、循环、过滤器等高级功能

## 安装依赖

```bash
pip install flask requests jinja2
```

## 使用方法

### 1. 设置环境变量

```bash
export DINGTALK_WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
export PORT=5000
export DEBUG=true
```

### 2. 启动服务

```bash
python app.py
```

### 3. 发送消息

#### 方式一：使用模板 + JSON 数据

```bash
curl -X POST http://localhost:5000/webhook?template=alert.json \
  -H "Content-Type: application/json" \
  -d '{
    "title": "服务器告警",
    "severity": "CRITICAL",
    "timestamp": "2024-01-15 10:30:00",
    "service": "web-server",
    "message": "CPU 使用率超过 90%",
    "alert": {
      "source": "prometheus"
    },
    "at_all": true
  }'
```

#### 方式二：使用模板 + 表单参数

```bash
curl -X POST http://localhost:5000/webhook?template=simple.json \
  -d "event_type=系统通知" \
  -d "message=系统将于今晚进行维护" \
  -d "timestamp=2024-01-15"
```

#### 方式三：不使用模板（直接转发 JSON）

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "这是一条测试消息"
    }
  }'
```

#### 方式四：覆盖 Webhook URL

```bash
curl -X POST "http://localhost:5000/webhook?webhook_url=https://oapi.dingtalk.com/robot/send?access_token=OTHER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"msgtype": "text", "text": {"content": "测试"}}'
```

## 模板示例

### Markdown 模板 (config/alert.json)

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "{{ title | default('告警通知') }}",
    "text": "## {{ title }}\n\n**级别**: {{ severity }}\n**时间**: {{ timestamp }}\n\n{{ message }}"
  },
  "at": {
    "isAtAll": {{ at_all | default('false') | lower }}
  }
}
```

### 文本模板 (config/simple.json)

```json
{
  "msgtype": "text",
  "text": {
    "content": "【{{ event_type }}】\n{{ message }}\n\n时间：{{ timestamp }}"
  }
}
```

## 变量引用规则

### JSON 数据
- 扁平化嵌套对象，支持点分隔路径
- 例如：`{"alert": {"source": "prometheus"}}` 可以通过 `alert.source` 引用

### 表单数据
- 直接使用参数名
- 例如：`title=测试` 可以通过 `title` 引用

## API 端点

- `POST /webhook` - 主 Webhook 入口
  - 查询参数：
    - `template`: 模板文件名（可选，位于 config 目录）
    - `webhook_url`: 覆盖默认的钉钉 Webhook URL（可选）
  
- `GET /health` - 健康检查

## 目录结构

```
/workspace
├── app.py              # 主程序
├── config/             # 模板目录
│   ├── alert.json      # 告警模板示例
│   └── simple.json     # 简单文本模板示例
└── README.md           # 说明文档
```
