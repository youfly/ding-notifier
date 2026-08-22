# 钉钉消息 Webhook 转发器

一个类似于 Apprise 桥接功能的钉钉消息 Webhook 转发器，支持模板渲染、JSON/表单数据处理和钉钉加签安全设置。

## 功能特性

1. **模板支持**: 通过 URL 参数 `template` 指定模板文件（位于 config 目录）
2. **灵活变量**: 
   - JSON POST: 支持点分隔路径引用变量（如 `alert.source`）
   - 表单参数：直接使用参数名作为变量
3. **Jinja2 模板引擎**: 强大的模板渲染能力
4. **钉钉加签安全**: 支持 HMAC-SHA256 签名验证
5. **Docker 部署**: 完整的 Docker 支持，可配置 config 目录路径
6. config/alert.json 或其他模板文件中，现在可以直接使用以下变量：
   - {{ now }}: 当前时间 (格式: 2026-08-21 22:30:00)
   - {{ date }}: 当前日期 (格式: 2026-08-21)
   - {{ time }}: 当前时间 (格式: 22:30:00)
   - {{ timestamp }}: Unix 时间戳 (整数)
   - {{ iso_time }}: ISO 格式时间 (2026-08-21T22:30:00)
   - {{ utc_time }}: UTC 时间
     
## 快速开始

### 方式一：直接运行

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export DINGTALK_WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
export DINGTALK_SECRET="SECxxxxxxxxxxxxxxx"  # 可选，如果开启了加签安全设置

# 运行服务
python app.py
```

### 方式二：Docker 部署

```bash
# 构建镜像
docker build -t dingtalk-forwarder .

# 运行容器
docker run -d \
  -p 5000:5000 \
  -e DINGTALK_WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
  -e DINGTALK_SECRET="SECxxxxxxxxxxxxxxx" \
  -v $(pwd)/config:/app/config \
  -e CONFIG_DIR=/app/config \
  --name dingtalk-forwarder \
  dingtalk-forwarder
```

### 方式三：Docker Compose

```bash
# 编辑 docker-compose.yml 配置你的 webhook 和密钥
# 然后运行：
docker-compose up -d
```

## 使用方法

### 1. 使用模板 + JSON 数据

```bash
curl -X POST http://localhost:5000/webhook?template=alert.json \
  -H "Content-Type: application/json" \
  -d '{
    "title": "服务器告警",
    "severity": "CRITICAL",
    "timestamp": "2024-01-01 12:00:00",
    "service": "nginx",
    "message": "CPU 使用率超过 90%",
    "alert": {
      "source": "prometheus"
    },
    "at_all": true
  }'
```

### 2. 使用模板 + 表单参数

```bash
curl -X POST http://localhost:5000/webhook?template=simple.json \
  -d "title=通知标题" \
  -d "content=这是通知内容"
```

### 3. 不使用模板，直接转发 JSON

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "msgtype": "text",
    "text": {
      "content": "直接发送的消息"
    }
  }'
```

### 4. 覆盖 Webhook 和密钥（可选）

```bash
curl -X POST "http://localhost:5000/webhook?template=alert.json&webhook_url=https://...&secret=SEC..." \
  -H "Content-Type: application/json" \
  -d '{"title": "测试"}'
```

## 配置说明

### 环境变量
钉钉机器人配置的密钥在config/bots.json里，名字为default表示未指定bot参数时默认使用的机器人。
钉钉消息的模板存放在config/templates目录下，可以通过请求的template参数指定名称。
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_DIR` | 配置文件目录路径 | `/app/config` (容器内) 或 `./config` (本地) |
| `PORT` | 服务端口 | `5000` |
| `DEBUG` | 调试模式 | `false` |

### 查询参数

| 参数名 | 说明 | 是否必需 |
|--------|------|----------|
| `bot` | 机器人名字(config/bots.json中配置)，默default | 否 |
| `template` | 模板文件名（位于 config/templates 目录） | 否 |
| `webhook_url` | 覆盖默认的钉钉 Webhook URL | 否 |
| `secret` | 覆盖默认的钉钉加签密钥 | 否 |

### 目录结构

```
.
├── app.py                 # 主程序
├── requirements.txt       # Python 依赖
├── Dockerfile            # Docker 镜像构建文件
├── docker-compose.yml    # Docker Compose 配置
├── .dockerignore         # Docker 忽略文件
├── README.md             # 说明文档
└── config/templates               # 配置目录（可挂载）
    ├── alert.json        # 告警模板示例
    └── simple.json       # 简单通知模板示例
```

## 模板示例

在模板模式下，系统会自动注入时间变量：now（格式：2026-08-21 22:30:00）、now_date（日期）、now_time（时间）、timestamp（时间戳），可直接在模板中使用如{{ now }}来显示当前时间。
            'now': now.strftime('%Y-%m-%d %H:%M:%S'),
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H:%M:%S'),
            'timestamp': int(now.timestamp()),
            'iso_time': now.isoformat(),
            'utc_time': now.utcnow().strftime('%Y-%m-%d %H:%M:%S')

### Markdown 格式告警模板 (config/templates/alert.json)

```json
{
  "msgtype": "markdown",
  "markdown": {
    "title": "{{ title | default('告警通知') }}",
    "text": "## {{ title | default('系统告警') }}\n\n**级别**: {{ severity | default('INFO') }}\n**时间**: {{ timestamp | default('未知') }}\n**服务**: {{ service | default('未知') }}\n\n### 详情\n{{ message | default('无详细信息') }}\n\n{% if alert %}\n**告警源**: {{ alert.source | default('未知') }}\n{% endif %}"
  },
  "at": {
    "isAtAll": {{ at_all | default('false') | lower }}
  }
}
```

### 文本格式简单模板 (config/templates/simple.json)

```json
{
  "msgtype": "text",
  "text": {
    "content": "{{ title }}: {{ content }}"
  }
}
```

## 钉钉加签说明

如果钉钉机器人开启了"加签安全设置"，需要：

1. 设置 `DINGTALK_SECRET` 环境变量为 SEC 开头的密钥
2. 或者在请求时通过 `secret` 参数传递密钥

程序会自动计算签名并附加 `timestamp` 和 `sign` 参数到请求中。

签名算法：
```
string_to_sign = timestamp + '\n' + secret
sign = HMAC-SHA256(string_to_sign, secret)
sign = URL_ENCODE(sign)
```

## 健康检查

```bash
curl http://localhost:5000/health
```

返回：
```json
{"status": "healthy"}
```

## License

MIT
