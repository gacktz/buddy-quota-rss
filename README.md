# Buddy 积分 RSS

将 Buddy 服务聚合额度平台的积分余额转换为 RSS 源，供 Quote/0 墨水屏等 RSS 设备订阅展示。

## 工作原理

GitHub Actions 每天 08:00（北京时间）自动运行 `scripts/query_balance.py`：
1. 调用 `POST https://btc-gz-cn3.chicross.cn/client/api/v1/query`
2. 获取剩余积分、累计已用、今日请求数、今日消耗等数据
3. 生成 `rss.xml` 并推送到仓库
4. GitHub Pages 托管该文件，RSS 地址固定不变

## 部署步骤

### 1. 推送代码到 GitHub

```bash
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin git@github.com:<用户名>/buddy-quota-rss.git
git push -u origin main
```

### 2. 配置密钥 Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret：
- **Name**: `BUDDY_KEY`
- **Secret**: 你的 `agg_sk_...` 密钥

### 3. 开启 GitHub Pages

仓库 → Settings → Pages → Source 选 **Deploy from a branch** → Branch 选 `main` / `/ (root)` → Save

等待 1-2 分钟，RSS 地址为：

```
https://<用户名>.github.io/buddy-quota-rss/rss.xml
```

### 4. 验证

仓库 → Actions → 手动运行 **Update Buddy Quota RSS**（Run workflow），
成功后访问上述 RSS 地址确认内容。

### 5. 添加 RSS 到 Quote/0

Quote/0 App → 添加 RSS 源 → 粘贴 RSS 地址 → 同步到设备。

## 本地测试

```bash
BUDDY_KEY=agg_sk_xxx python3 scripts/query_balance.py
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `scripts/query_balance.py` | 查询积分并生成 RSS |
| `.github/workflows/update-rss.yml` | 定时任务 (每天 08:00 北京时间) |
| `rss.xml` | 生成的 RSS 产物 |

## 注意

- 密钥只存放在 GitHub Secrets 中，代码和文档中不出现明文
- RSS 刷新频率由设备/App 决定，Actions 每天更新一次足够
- 如需修改更新时间，编辑 workflow 中的 `cron` 表达式（UTC 时区）
