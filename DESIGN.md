# AstrBot 通讯录插件设计文档

## 一、插件概述

### 1.1 功能描述
构建一个通讯录系统，让LLM可以查询和管理会话列表，并向任意会话发送消息。

### 1.2 核心功能
- **查看通讯录**：查看所有已保存的会话（昵称和UMO）
- **关键词查询**：通过昵称关键词查询特定会话的UMO
- **发送消息**：向指定UMO的会话发送消息

## 二、技术架构

### 2.1 插件结构
```
astrbot_plugin_contacts/
├── main.py                 # 主插件文件
├── metadata.yaml          # 插件元数据
├── _conf_schema.json      # 配置文件模式
├── tools/
│   ├── __init__.py
│   └── contact_tools.py   # 通讯录工具函数
└── README.md             # 使用说明

# 数据文件存储位置（运行时生成）
data/plugin_data/contacts/
└── contacts.json          # 通讯录数据文件
```

### 2.2 数据结构

#### 2.2.1 通讯录JSON格式 (contacts.json)
```json
{
  "contacts": [
    {
      "nickname": "测试群",
      "umo": "aiocqhttp_default:GroupMessage:123456789",
      "description": "主要测试群组",
      "created_at": "2026-01-10T12:00:00",
      "last_used": "2026-01-10T12:30:00"
    },
    {
      "nickname": "小明",
      "umo": "aiocqhttp_default:PrivateMessage:987654321",
      "description": "好友小明",
      "created_at": "2026-01-10T12:00:00",
      "last_used": null
    }
  ]
}
```

#### 2.2.2 UMO格式说明
UMO (Unified Message Object) 格式：`platform_id:message_type:session_id`
- `platform_id`: 平台ID，如 `aiocqhttp_default`
- `message_type`: 消息类型，如 `GroupMessage`、`PrivateMessage`
- `session_id`: 会话ID（群号或QQ号）

## 三、LLM工具设计

### 3.1 第一层工具（查询类）

#### 工具1: list_contacts
**功能**：列出所有通讯录中的联系人

**参数**：无

**返回值**：
```
📇 通讯录列表（共3个联系人）：

1. 测试群
   UMO: aiocqhttp_default:GroupMessage:123456789
   描述: 主要测试群组
   
2. 小明
   UMO: aiocqhttp_default:PrivateMessage:987654321
   描述: 好友小明
   
3. 工作群
   UMO: aiocqhttp_default:GroupMessage:111222333
   描述: 工作交流群
```

#### 工具2: search_contact
**功能**：通过昵称关键词搜索联系人

**参数**：
- `keyword` (string): 搜索关键词（昵称）

**返回值**：
```
🔍 搜索结果（关键词: "小明"）：

找到1个匹配的联系人：

1. 小明
   UMO: aiocqhttp_default:PrivateMessage:987654321
   描述: 好友小明
```

### 3.2 第二层工具（操作类）

#### 工具3: send_message_to_contact
**功能**：向指定联系人发送消息

**参数**：
- `umo` (string): 目标会话的UMO标识符
- `message` (string): 要发送的消息内容

**返回值**：
```
✓ 消息已发送到：测试群 (aiocqhttp_default:GroupMessage:123456789)
消息内容: 大家好！
```

### 3.3 管理工具（可选）

#### 工具4: add_contact
**功能**：添加新联系人到通讯录

**参数**：
- `nickname` (string): 联系人昵称
- `umo` (string): UMO标识符
- `description` (string, 可选): 联系人描述

**权限要求**：需要管理员权限

#### 工具5: remove_contact
**功能**：从通讯录删除联系人

**参数**：
- `nickname` (string): 要删除的联系人昵称

**权限要求**：需要管理员权限

#### 工具6: update_contact
**功能**：更新联系人信息

**参数**：
- `nickname` (string): 联系人昵称
- `new_nickname` (string, 可选): 新昵称
- `new_description` (string, 可选): 新描述

**权限要求**：需要管理员权限

## 四、配置文件设计

### 4.1 _conf_schema.json
```json
{
  "admin_ids": {
    "type": "list",
    "title": "管理员列表",
    "description": "允许管理通讯录的QQ号列表，留空表示所有人都可以管理",
    "default": []
  },
  "enable_fuzzy_search": {
    "type": "bool",
    "title": "启用模糊搜索",
    "description": "搜索联系人时是否使用模糊匹配",
    "default": true
  },
  "auto_update_last_used": {
    "type": "bool",
    "title": "自动更新使用时间",
    "description": "发送消息时是否自动更新联系人的最后使用时间",
    "default": true
  }
}
```

## 五、核心类设计

### 5.1 ContactsPlugin (main.py)
```python
class ContactsPlugin(Star):
    """通讯录插件主类"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 获取插件数据目录（符合AstrBot规范）
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path
        self.plugin_data_path = get_astrbot_data_path() / "plugin_data" / self.name
        
        # 确保目录存在
        self.plugin_data_path.mkdir(parents=True, exist_ok=True)
        
        # 通讯录文件路径
        self.contacts_file = self.plugin_data_path / "contacts.json"
        
        # 初始化配置
        self.config = config
        self.admin_ids = set(config.get("admin_ids", []))
        self.enable_fuzzy_search = config.get("enable_fuzzy_search", True)
        self.auto_update_last_used = config.get("auto_update_last_used", True)
        
        # 初始化通讯录管理器
        from .tools.contact_tools import ContactManager
        self.contact_manager = ContactManager(str(self.contacts_file))
    
    # LLM工具装饰器
    @filter.llm_tool(name="list_contacts")
    async def tool_list_contacts(self, event: AstrMessageEvent) -> str:
        """列出所有联系人"""
    
    @filter.llm_tool(name="search_contact")
    async def tool_search_contact(self, event: AstrMessageEvent, keyword: str) -> str:
        """搜索联系人"""
    
    @filter.llm_tool(name="send_message_to_contact")
    async def tool_send_message(self, event: AstrMessageEvent, umo: str, message: str) -> str:
        """发送消息到联系人"""
    
    @filter.llm_tool(name="add_contact")
    async def tool_add_contact(self, event: AstrMessageEvent, nickname: str, umo: str, description: str = "") -> str:
        """添加联系人（需管理员权限）"""
    
    @filter.llm_tool(name="remove_contact")
    async def tool_remove_contact(self, event: AstrMessageEvent, nickname: str) -> str:
        """删除联系人（需管理员权限）"""
```

### 5.2 ContactManager (tools/contact_tools.py)
```python
class ContactManager:
    """通讯录管理器"""
    
    def __init__(self, contacts_file: str):
        """
        初始化通讯录管理器
        
        Args:
            contacts_file: 通讯录JSON文件的完整路径
        """
        self.contacts_file = Path(contacts_file)
        self.contacts = []
        
        # 如果文件不存在，创建空通讯录
        if not self.contacts_file.exists():
            self.save_contacts([])
        else:
            self.contacts = self.load_contacts()
    
    def load_contacts(self) -> list:
        """从文件加载通讯录"""
    
    def save_contacts(self, contacts: list):
        """保存通讯录到文件"""
    
    def search_contacts(self, keyword: str, fuzzy: bool = True) -> list:
        """搜索联系人"""
    
    def add_contact(self, nickname: str, umo: str, description: str = "") -> bool:
        """添加联系人"""
    
    def remove_contact(self, nickname: str) -> bool:
        """删除联系人"""
    
    def update_last_used(self, umo: str):
        """更新最后使用时间"""
    
    def get_contact_by_umo(self, umo: str) -> dict:
        """通过UMO获取联系人信息"""
```

## 六、使用流程示例

### 6.1 查看通讯录
```
用户: 查看通讯录
LLM: [调用 list_contacts 工具]
Bot: 📇 通讯录列表（共3个联系人）：...
```

### 6.2 搜索并发送消息
```
用户: 给小明发消息说"你好"
LLM: 
  1. [调用 search_contact(keyword="小明")]
  2. [获取到 UMO: aiocqhttp_default:PrivateMessage:987654321]
  3. [调用 send_message_to_contact(umo="...", message="你好")]
Bot: ✓ 消息已发送到：小明
```

### 6.3 添加联系人
```
管理员: 添加联系人，昵称是开发群，UMO是aiocqhttp_default:GroupMessage:999888777
LLM: [调用 add_contact(nickname="开发群", umo="...", description="")]
Bot: ✓ 已添加联系人：开发群
```

## 七、安全性考虑

### 7.1 权限控制
- 查看和搜索：所有用户可用
- 发送消息：所有用户可用（但受AstrBot框架的消息发送权限控制）
- 添加/删除/更新联系人：仅管理员可用

### 7.2 数据验证
- UMO格式验证（必须符合 `platform:type:id` 格式）
- 昵称唯一性检查
- 消息内容长度限制

### 7.3 错误处理
- 文件读写失败
- UMO格式错误
- 联系人不存在
- 消息发送失败

## 八、扩展功能（未来版本）

1. **分组管理**：支持将联系人分组
2. **别名系统**：一个联系人支持多个别名
3. **标签系统**：为联系人添加标签便于筛选
4. **使用统计**：记录消息发送次数和频率
5. **导入导出**：支持批量导入和导出联系人
6. **智能推荐**：根据聊天内容推荐可能需要联系的人

## 九、测试计划

### 9.1 单元测试
- 通讯录加载/保存
- 搜索功能（精确/模糊）
- 联系人增删改查

### 9.2 集成测试
- LLM工具调用
- 消息发送
- 权限验证

### 9.3 场景测试
- 通讯录为空时
- 搜索无结果时
- UMO格式错误时
- 并发访问时

## 十、依赖项

- **AstrBot框架**：>=最新版本
- **Python标准库**：json, datetime, pathlib
- 无需额外第三方依赖