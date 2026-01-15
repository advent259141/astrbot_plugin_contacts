# AstrBot 通讯录插件

让LLM可以查询和管理会话列表，并向任意会话发送消息的AstrBot插件。支持定时发送消息功能。

## 功能特性

### 📋 核心功能

1. **查看通讯录** - 查看所有已保存的联系人（昵称和UMO）
2. **搜索联系人** - 通过昵称关键词快速搜索联系人
3. **发送消息** - 向指定UMO的会话发送消息
4. **管理联系人** - 添加、删除、更新联系人信息（需管理员权限）
5. **⏰ 定时消息** - 创建定时发送消息任务，支持一次性、每日、每周等多种调度方式（需管理员权限）

### 🤖 LLM工具

插件提供以下LLM工具，可通过自然语言与LLM对话调用：

#### 查询类工具（所有用户可用）
- `list_contacts` - 列出所有联系人
- `search_contact` - 搜索联系人

#### 操作类工具（所有用户可用）
- `send_message_to_contact` - 发送消息到指定联系人

#### 管理类工具（需管理员权限）
- `add_contact` - 添加新联系人
- `remove_contact` - 删除联系人
- `update_contact` - 更新联系人信息

#### 定时任务工具（需管理员权限）
- `schedule_message` - 创建定时发送消息任务
- `list_scheduled_messages` - 查看所有定时任务
- `cancel_scheduled_message` - 取消并删除定时任务
- `toggle_scheduled_message` - 启用/禁用定时任务
- `update_scheduled_message` - 修改定时任务

## 安装方法

1. 将插件文件夹放置到 AstrBot 的插件目录
2. 重启 AstrBot 或重载插件
3. 插件会自动创建数据目录：`data/plugin_data/contacts/`

## 配置说明

在 AstrBot 的插件配置中可以设置以下选项：

```json
{
  "admin_ids": [],                    // 管理员QQ号列表，留空表示所有人都可以管理
  "enable_fuzzy_search": true,        // 是否启用模糊搜索
  "auto_update_last_used": true       // 发送消息时是否自动更新最后使用时间
}
```

### 配置项说明

- **admin_ids**: 管理员列表
  - 类型：列表
  - 默认：空（所有人都可以管理）
  - 说明：只有列表中的用户可以添加、删除、更新联系人

- **enable_fuzzy_search**: 启用模糊搜索
  - 类型：布尔值
  - 默认：true
  - 说明：搜索时使用模糊匹配，关键词在昵称中即可匹配

- **auto_update_last_used**: 自动更新使用时间
  - 类型：布尔值
  - 默认：true
  - 说明：发送消息时自动更新联系人的最后使用时间

## 使用示例

### 通过LLM对话使用

#### 查看通讯录
```
用户: 查看通讯录
Bot: 📇 通讯录列表（共3个联系人）：

1. 测试群
   UMO: aiocqhttp_default:GroupMessage:123456789
   描述: 主要测试群组
   
2. 小明
   UMO: aiocqhttp_default:PrivateMessage:987654321
   描述: 好友小明
   
3. 开发群
   UMO: aiocqhttp_default:GroupMessage:111222333
   描述: 开发交流群
```

#### 搜索联系人
```
用户: 搜索联系人 小明
Bot: 🔍 搜索结果（关键词: "小明"）：

找到1个匹配的联系人：

1. 小明
   UMO: aiocqhttp_default:PrivateMessage:987654321
   描述: 好友小明
```

#### 发送消息
```
用户: 给小明发消息说"你好，最近怎么样？"
Bot: ✓ 消息已发送到：小明
UMO: aiocqhttp_default:PrivateMessage:987654321
消息内容: 你好，最近怎么样？
```

#### 添加联系人（需管理员权限）
```
用户: 添加联系人，昵称是工作群，UMO是aiocqhttp_default:GroupMessage:999888777，描述是公司工作群
Bot: ✓ 已添加联系人：工作群
```

#### 删除联系人（需管理员权限）
```
用户: 删除联系人 工作群
Bot: ✓ 已删除联系人：工作群
```

#### 更新联系人（需管理员权限）
```
用户: 更新联系人小明的描述为"我的好朋友"
Bot: ✓ 已更新联系人：小明
```

#### 创建定时任务（需管理员权限）
```
用户: 帮我设置一个定时任务，每天早上8点给开发群发"早安，新的一天开始了"
Bot: ✓ 已创建定时任务：每日早安
任务ID: abc123-def456
下次执行: 2026-01-12 08:00:00
```

#### 查看定时任务
```
用户: 查看所有定时任务
Bot: 📅 定时任务列表（共2个任务）：

1. 每日早安 (✅ 启用)
   任务ID: abc123-def456
   目标会话: aiocqhttp_default:GroupMessage:123456
   消息内容: 早安，新的一天开始了
   调度类型: 每日
   下次执行: 2026-01-12 08:00:00
   
2. 周一开会提醒 (✅ 启用)
   任务ID: xyz789-uvw012
   目标会话: aiocqhttp_default:GroupMessage:123456
   消息内容: 提醒：10点开会！
   调度类型: 每周
   下次执行: 2026-01-13 10:00:00
```

#### 修改定时任务（需管理员权限）
```
用户: 把每日早安的时间改成9点
Bot: ✓ 已更新任务：每日早安
```

#### 取消定时任务（需管理员权限）
```
用户: 取消任务 abc123-def456
Bot: ✓ 已删除任务：每日早安
```

### 通过命令使用

#### 查看通讯录
```
/contacts
```

#### 查看插件信息
```
/contact_info
```

## UMO格式说明

UMO (Unified Message Object) 是 AstrBot 中用于标识会话的统一格式：

```
platform_id:message_type:session_id
```

### 组成部分

- **platform_id**: 平台标识符，如 `aiocqhttp_default`
- **message_type**: 消息类型
  - `GroupMessage` - 群聊消息
  - `PrivateMessage` - 私聊消息
- **session_id**: 会话ID（群号或QQ号）

### 定时任务调度类型

#### once - 一次性任务
在指定的时间点执行一次，执行后自动禁用。

**时间格式：** `"2026-01-12 08:00"` 或 `"2026-01-12T08:00:00"`

**示例：**
```
schedule_type="once"
schedule_time="2026-01-12 08:00"
```

#### daily - 每日任务
每天在指定时间执行。

**时间格式：** `"08:00"` (24小时制)

**示例：**
```
schedule_type="daily"
schedule_time="08:00"  # 每天早上8点执行
```

#### weekly - 每周任务
每周指定星期几的指定时间执行。

**时间格式：** `"day HH:MM"` (day: 0=周一, 1=周二, ..., 6=周日)

**示例：**
```
schedule_type="weekly"
schedule_time="0 09:00"  # 每周一早上9点执行
schedule_time="4 14:30"  # 每周五下午2:30执行
```

#### cron - Cron表达式（简化版）
使用简化的cron表达式，支持固定时间的每日任务。

**时间格式：** `"minute hour * * *"`

**示例：**
```
schedule_type="cron"
schedule_time="0 8 * * *"  # 每天早上8点执行
schedule_time="30 14 * * *"  # 每天下午2:30执行
```

### 示例

- 群聊：`aiocqhttp_default:GroupMessage:123456789`
- 私聊：`aiocqhttp_default:PrivateMessage:987654321`

### 如何获取UMO

1. 在需要保存的会话中发送消息触发LLM
2. 查看AstrBot日志，找到该会话的UMO
3. 或者让LLM使用 `add_contact` 工具时，直接提供UMO

## 数据存储

### 数据文件位置

```
data/plugin_data/contacts/
├── contacts.json
└── scheduled_tasks.json
```

### 数据格式

```json
{
  "contacts": [
    {
      "nickname": "测试群",
      "umo": "aiocqhttp_default:GroupMessage:123456789",
      "description": "主要测试群组",
      "created_at": "2026-01-10T12:00:00",
      "last_used": "2026-01-10T12:30:00"
    }
  ]
}
```

**scheduled_tasks.json 格式：**
```json
{
  "tasks": [
    {
      "task_id": "abc123-def456",
      "task_name": "每日早安",
      "target_umo": "aiocqhttp_default:GroupMessage:123456",
      "message": "早安，新的一天开始了",
      "schedule_type": "daily",
      "schedule_config": {
        "hour": 8,
        "minute": 0
      },
      "created_by": "Jason(123456)",
      "created_from": "小面包的私聊",
      "created_at": "2026-01-11T16:00:00",
      "enabled": true,
      "last_run": "2026-01-11T08:00:00",
      "next_run": "2026-01-12T08:00:00"
    }
  ]
}
```

### 备份建议

建议定期备份 `contacts.json` 和 `scheduled_tasks.json` 文件，以防数据丢失。

## 权限说明

### 无需权限的操作
- 查看通讯录（`list_contacts`）
- 搜索联系人（`search_contact`）
- 发送消息（`send_message_to_contact`）
- 查看定时任务（`list_scheduled_messages`）
- 使用 `/contacts` 和 `/contact_info` 命令

### 需要管理员权限的操作
- 添加联系人（`add_contact`）
- 删除联系人（`remove_contact`）
- 更新联系人（`update_contact`）
- 创建定时任务（`schedule_message`）
- 取消定时任务（`cancel_scheduled_message`）
- 启用/禁用定时任务（`toggle_scheduled_message`）
- 修改定时任务（`update_scheduled_message`）

## 常见问题

### Q: 如何获取会话的UMO？
A: 在目标会话中发送消息，查看AstrBot日志即可找到UMO。或者使用其他插件的功能获取当前会话信息。

### Q: 发送消息失败怎么办？
A: 
1. 检查UMO格式是否正确
2. 确认目标会话仍然存在
3. 检查AstrBot的平台连接状态
4. 查看日志获取详细错误信息

### Q: 如何批量导入联系人？
A: 当前版本需要逐个添加。未来版本会支持批量导入功能。或者直接编辑 `contacts.json` 文件后重启插件。

### Q: 通讯录数据会丢失吗？
A: 数据保存在 `data/plugin_data/contacts/`目录下，包括 `contacts.json` 和 `scheduled_tasks.json`，建议定期备份这些文件。

### Q: 定时任务重启后会丢失吗？
A: 不会。定时任务会持久化保存在 `scheduled_tasks.json` 中，AstrBot重启后会自动恢复所有启用的任务。

### Q: 定时任务的时间是什么时区？
A: 使用系统本地时区。请确保服务器时间设置正确。

### Q: 可以创建多少个定时任务？
A: 理论上没有限制，但建议合理控制任务数量以避免资源占用过多。

## 开发计划

未来版本可能添加的功能：

- [x] 定时发送消息
- [ ] 分组管理
- [ ] 别名系统
- [ ] 标签系统
- [ ] 使用统计
- [ ] 批量导入/导出
- [ ] 智能推荐
- [ ] 更复杂的cron表达式支持

## 更新日志

### v1.1.0 (2026-01-11)
- ✨ 新增定时消息功能
- ✅ 支持一次性、每日、每周、cron等多种调度方式
- ✅ 定时任务持久化，重启后自动恢复
- ✅ 完整的任务生命周期管理（创建、查看、修改、启用/禁用、删除）
- ✅ 定时消息自动添加到目标会话上下文

### v1.0.0 (2026-01-10)
- ✨ 初始版本发布
- ✅ 基础的通讯录管理功能
- ✅ LLM工具集成
- ✅ 权限控制系统
- ✅ 模糊搜索支持
- ✅ 消息发送时自动添加到目标会话上下文

## 许可证

MIT License

## 反馈与贡献

欢迎提交Issue和Pull Request！

- GitHub仓库：[待添加]
- 问题反馈：[待添加]

## 致谢

感谢 AstrBot 团队提供的优秀框架！