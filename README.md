# AI翻译服务

一个基于OpenAI API的智能翻译服务，支持批量翻译和缓存功能。

## 环境配置

```bash
export OPENAI_API_KEY=your_openai_api_key
```

## 启动服务

```bash
python start.py
```

访问API文档：http://127.0.0.1:8005/docs

## 数据库迁移

### 新版本表结构变更

新版本将表结构从 `source_text` 主键改为 `id` 主键，并为 `source_text` 添加索引以提升查询性能。

### 执行迁移

```bash
# 执行数据迁移
python migrate_data.py

# 如果需要回滚迁移
python migrate_data.py --rollback
```

### 验证迁移

```bash
# 测试迁移后的表结构
python test_migration.py
```

## API使用示例

```bash
curl -X 'POST' \
  'http://127.0.0.1:8005/translate' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "data": [
    {
      "content": "尖椒炒肉",
      "lang": "zh"
    },
    {
      "content": "订单ID",
      "lang": "zh"
    }
  ]
}'
```

## 缓存查询功能

### 智能缓存查询

`get_cached_translations` 函数支持根据目标语言列表进行智能查询：

```python
from app.crud import get_cached_translations

# 查询指定目标语言的翻译
result = get_cached_translations(
    source_texts=["Hello", "World"],
    source_lang="en",
    trans_lang=["zh", "ja"]  # 只查询中文和日文翻译
)

# 查询所有目标语言的翻译
result = get_cached_translations(
    source_texts=["Hello", "World"],
    source_lang="en",
    trans_lang=[]  # 空列表，查询所有翻译
)

# 语言列表顺序无关：["zh","en"] 和 ["en","zh"] 被视为相同
result = get_cached_translations(
    source_texts=["Hello"],
    source_lang="en",
    trans_lang=["en", "zh"]  # 与 ["zh", "en"] 效果相同
)
```

### 测试和演示

```bash
# 测试CRUD功能
python test_crud.py

# 测试排序功能
python test_sorting.py

# 查看使用示例
python example_usage.py
```

## 数据库配置

支持MySQL和SQLite两种数据库：

- `DB_TYPE`: 数据库类型 (`mysql` 或 `sqlite`)
- `DB_PATH`: SQLite数据库文件路径
- `DB_WRITE_HOST`: MySQL写库主机
- `DB_READ_HOST`: MySQL读库主机
- `DB_USER`: 数据库用户名
- `DB_PASSWORD`: 数据库密码
- `DB_DATABASE`: 数据库名称