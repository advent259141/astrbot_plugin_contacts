"""
AstrBot 通讯录插件
让LLM可以查询和管理会话列表，并向任意会话发送消息
"""

from pathlib import Path
from astrbot.api.star import Context, Star, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import AstrBotConfig, logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path
from astrbot.core.agent.message import (
    AssistantMessageSegment,
    UserMessageSegment,
    TextPart,
)

from .tools.contact_tools import ContactManager
from .tools.scheduler_tools import SchedulerManager
from .tools.history_tools import HistoryManager


@register(
    name="contacts",
    desc="通讯录管理插件 - 让LLM可以查询和管理会话列表，并向任意会话发送消息。支持定时发送消息功能。",
    version="1.1.0",
    author="AstrBot Community"
)
class ContactsPlugin(Star):
    """通讯录插件主类"""
    
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 初始化配置
        self.config = config
        self.admin_ids = set(self.config.get("admin_ids", []))
        self.enable_fuzzy_search = self.config.get("enable_fuzzy_search", True)
        self.auto_update_last_used = self.config.get("auto_update_last_used", True)
        

        # 获取插件数据目录
        plugin_name = "contacts"
        self.plugin_data_path = Path(get_astrbot_data_path()) / "plugin_data" / plugin_name
        
        # 确保目录存在
        self.plugin_data_path.mkdir(parents=True, exist_ok=True)
        
        # 通讯录文件路径
        self.contacts_file = self.plugin_data_path / "contacts.json"
        
        # 初始化通讯录管理器
        self.contact_manager = ContactManager(str(self.contacts_file))
        
        # 定时任务文件路径
        self.scheduler_file = self.plugin_data_path / "scheduled_tasks.json"
        
        # 初始化定时任务管理器
        self.scheduler_manager = SchedulerManager(
            str(self.scheduler_file),
            self._send_scheduled_message
        )
        
        # 初始化历史记录管理器
        self.history_manager = HistoryManager()
        
        logger.info(f"通讯录插件已加载，数据文件: {self.contacts_file}")
        logger.info(f"当前通讯录中有 {len(self.contact_manager.get_all_contacts())} 个联系人")
        
        # 启动定时任务调度器
        import asyncio
        asyncio.create_task(self._start_scheduler())
    
    def is_admin(self, user_id: str) -> bool:
        """
        检查用户是否为管理员
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否为管理员，如果admin_ids为空则所有人都是管理员
        """
        if not self.admin_ids:
            return True
        return str(user_id) in self.admin_ids
    
    def _check_permission(self, event: AstrMessageEvent) -> tuple[bool, str]:
        """
        检查用户是否有管理权限
        
        Args:
            event: 消息事件
            
        Returns:
            (是否有权限, 错误消息或空字符串)
        """
        user_id = event.get_sender_id()
        if not self.is_admin(user_id):
            return False, f"❌ 权限不足：用户 {user_id} 不在管理员列表中"
        return True, ""
    
    async def _start_scheduler(self):
        """启动定时任务调度器"""
        try:
            await self.scheduler_manager.start()
            logger.info("定时任务调度器已启动")
        except Exception as e:
            logger.error(f"启动定时任务调度器失败: {e}")
    
    async def _send_scheduled_message(self, umo: str, message: str, task_info: dict):
        """
        定时任务的消息发送回调函数
        
        Args:
            umo: 目标会话UMO
            message: 消息内容
            task_info: 任务信息
        """
        try:
            # 发送消息
            from astrbot.api.event import MessageChain
            message_chain = MessageChain().message(message)
            await self.context.send_message(umo, message_chain)
            
            # 添加到目标会话的上下文
            try:
                conv_mgr = self.context.conversation_manager
                if conv_mgr:
                    target_cid = await conv_mgr.get_curr_conversation_id(umo)
                    
                    # 构造用户消息：说明这是定时任务触发的
                    task_name = task_info.get('task_name', '未命名任务')
                    created_by = task_info.get('created_by', '未知')
                    created_from = task_info.get('created_from', '未知')
                    
                    user_context = f"[定时任务] 任务「{task_name}」自动触发\n创建者：{created_by}\n来源会话：{created_from}"
                    user_msg = UserMessageSegment(content=[TextPart(text=user_context)])
                    assistant_msg = AssistantMessageSegment(content=[TextPart(text=message)])
                    
                    await conv_mgr.add_message_pair(
                        cid=target_cid,
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                    )
                    logger.info(f"已将定时消息添加到目标会话 ({umo}) 的上下文")
            except AttributeError:
                logger.warning(f"Context 对象不支持 conversation_manager 属性")
            except Exception as ctx_err:
                logger.warning(f"添加定时消息到会话上下文失败: {ctx_err}")
            
            # 更新联系人最后使用时间
            if self.auto_update_last_used:
                contact = self.contact_manager.get_contact_by_umo(umo)
                if contact:
                    self.contact_manager.update_last_used(umo)
            
            logger.info(f"定时任务发送消息到 {umo}: {message}")
            
        except Exception as e:
            logger.error(f"定时任务发送消息失败: {e}")
            raise
    
    # ============ LLM工具：查询类（无需权限） ============
    
    @filter.llm_tool(name="list_contacts")
    async def tool_list_contacts(self, event: AstrMessageEvent) -> str:
        """列出所有通讯录中的联系人
        
        此工具用于查看通讯录中的所有联系人信息，包括昵称、UMO和描述。
        无需任何参数，直接调用即可获取完整的联系人列表。
        """
        try:
            contacts = self.contact_manager.get_all_contacts()
            result = self.contact_manager.format_contact_list(contacts)
            logger.info(f"列出通讯录：共 {len(contacts)} 个联系人")
            return result
        except Exception as e:
            logger.error(f"列出通讯录失败: {e}")
            return f"❌ 列出通讯录失败: {str(e)}"
    
    @filter.llm_tool(name="search_contact")
    async def tool_search_contact(self, event: AstrMessageEvent, keyword: str) -> str:
        """通过昵称关键词搜索联系人
        
        使用昵称关键词搜索通讯录中的联系人，支持模糊匹配。
        搜索结果会显示匹配的联系人的完整信息，包括UMO标识符。
        
        Args:
            keyword(string): 搜索关键词（昵称）
        """
        try:
            contacts = self.contact_manager.search_contacts(
                keyword, 
                fuzzy=self.enable_fuzzy_search
            )
            result = self.contact_manager.format_search_result(keyword, contacts)
            logger.info(f"搜索联系人 '{keyword}'：找到 {len(contacts)} 个结果")
            return result
        except Exception as e:
            logger.error(f"搜索联系人失败: {e}")
            return f"❌ 搜索失败: {str(e)}"
    
    # ============ LLM工具：操作类（无需权限） ============
    
    @filter.llm_tool(name="send_message_to_contact")
    async def tool_send_message(self, event: AstrMessageEvent, umo: str, message: str) -> str:
        """向指定联系人发送消息
        
        通过UMO标识符向指定的会话发送消息。
        UMO格式为: platform_id:message_type:session_id
        例如: aiocqhttp_default:GroupMessage:123456789
        
        Args:
            umo(string): 目标会话的UMO标识符
            message(string): 要发送的消息内容
        """
        try:
            # 查找联系人信息
            contact = self.contact_manager.get_contact_by_umo(umo)
            contact_name = contact.get('nickname', '未知联系人') if contact else umo
            
            # 发送消息
            from astrbot.api.event import MessageChain
            message_chain = MessageChain().message(message)
            await self.context.send_message(umo, message_chain)
            
            # 获取会话管理器并添加对话记录到目标会话
            try:
                # 从 context 中获取 conversation_manager
                conv_mgr = self.context.conversation_manager
                if conv_mgr:
                    # 获取目标会话的当前对话ID
                    target_cid = await conv_mgr.get_curr_conversation_id(umo)
                    
                    # 获取发送者信息、来源会话和原始消息
                    sender_name = event.get_sender_name()
                    sender_id = event.get_sender_id()
                    source_umo = event.unified_msg_origin  # 来源会话的UMO
                    original_message = event.message_str  # 获取消息的纯文本内容
                    
                    # 查找来源会话的联系人信息
                    source_contact = self.contact_manager.get_contact_by_umo(source_umo)
                    source_name = source_contact.get('nickname', source_umo) if source_contact else source_umo
                    
                    # 构造用户消息：说明原会话的要求和发送行为
                    user_context = f"这是原会话{source_name}的要求：{sender_name}({sender_id})：{original_message}\n你在{source_name}会话中使用通讯录向这个会话发送了下面这条消息"
                    user_msg = UserMessageSegment(content=[TextPart(text=user_context)])
                    assistant_msg = AssistantMessageSegment(content=[TextPart(text=message)])
                    
                    # 将消息对添加到目标会话的上下文
                    await conv_mgr.add_message_pair(
                        cid=target_cid,
                        user_message=user_msg,
                        assistant_message=assistant_msg,
                    )
                    logger.info(f"已将消息添加到目标会话 ({umo}) 的上下文: {user_context}")
            except AttributeError:
                logger.warning(f"Context 对象不支持 conversation_manager 属性")
            except Exception as ctx_err:
                logger.warning(f"添加消息到会话上下文失败: {ctx_err}")
            
            # 更新最后使用时间
            if self.auto_update_last_used and contact:
                self.contact_manager.update_last_used(umo)
            
            logger.info(f"发送消息到 {contact_name} ({umo}): {message}")
            return f"✓ 消息已发送到：{contact_name}\nUMO: {umo}\n消息内容: {message}"
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return f"❌ 发送消息失败: {str(e)}"
    
    # ============ LLM工具：管理类（需要管理员权限） ============
    
    @filter.llm_tool(name="add_contact")
    async def tool_add_contact(self, event: AstrMessageEvent, nickname: str, umo: str, description: str = "") -> str:
        """添加新联系人到通讯录
        
        将新的联系人添加到通讯录中。需要提供昵称和UMO标识符。
        UMO格式为: platform_id:message_type:session_id
        例如: aiocqhttp_default:GroupMessage:123456789
        
        描述字段用于补充说明该联系人的详细信息，例如"公司工作群"、"我的好朋友"、"客户服务群"等。
        LLM可以根据上下文和会话性质自行决定是否添加描述，如果不确定或无需描述则留空即可。
        
        注意：此操作需要管理员权限。
        
        Args:
            nickname(string): 联系人昵称（必须唯一）
            umo(string): UMO标识符（必须唯一且格式正确）
            description(string): 联系人描述（可选，由LLM根据上下文自行决定是否添加，默认为空）
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        try:
            success, msg = self.contact_manager.add_contact(nickname, umo, description)
            if success:
                logger.info(f"添加联系人: {nickname} ({umo})")
                return f"✓ {msg}"
            else:
                logger.warning(f"添加联系人失败: {msg}")
                return f"❌ {msg}"
        except Exception as e:
            logger.error(f"添加联系人异常: {e}")
            return f"❌ 添加联系人失败: {str(e)}"
    
    @filter.llm_tool(name="remove_contact")
    async def tool_remove_contact(self, event: AstrMessageEvent, nickname: str) -> str:
        """从通讯录删除联系人
        
        根据昵称从通讯录中删除指定的联系人。
        
        注意：此操作需要管理员权限，且删除后无法恢复。
        
        Args:
            nickname(string): 要删除的联系人昵称
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        try:
            success, msg = self.contact_manager.remove_contact(nickname)
            if success:
                logger.info(f"删除联系人: {nickname}")
                return f"✓ {msg}"
            else:
                logger.warning(f"删除联系人失败: {msg}")
                return f"❌ {msg}"
        except Exception as e:
            logger.error(f"删除联系人异常: {e}")
            return f"❌ 删除联系人失败: {str(e)}"
    
    @filter.llm_tool(name="update_contact")
    async def tool_update_contact(self, event: AstrMessageEvent, nickname: str,
                                  new_nickname: str = None, new_description: str = None) -> str:
        """更新联系人信息
        
        更新指定联系人的昵称或描述信息。
        至少需要提供新昵称或新描述中的一个。
        
        描述字段用于补充说明该联系人的详细信息，例如"公司工作群"、"我的好朋友"等。
        LLM可以根据上下文自行决定是否添加或更新描述，如果不提供new_description参数，
        则保持原有描述不变。
        
        注意：此操作需要管理员权限。
        
        Args:
            nickname(string): 当前联系人昵称
            new_nickname(string): 新昵称（可选，不提供则保持不变）
            new_description(string): 新描述（可选，不提供则保持不变，提供空字符串可清空描述）
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        # 检查是否至少提供了一个更新参数
        if new_nickname is None and new_description is None:
            return "❌ 请至少提供新昵称或新描述中的一个"
        
        try:
            success, msg = self.contact_manager.update_contact(
                nickname, 
                new_nickname, 
                new_description
            )
            if success:
                logger.info(f"更新联系人: {nickname}")
                return f"✓ {msg}"
            else:
                logger.warning(f"更新联系人失败: {msg}")
                return f"❌ {msg}"
        except Exception as e:
            logger.error(f"更新联系人异常: {e}")
            return f"❌ 更新联系人失败: {str(e)}"
    
    # ============ LLM工具：定时任务管理（需要管理员权限） ============
    
    @filter.llm_tool(name="schedule_message")
    async def tool_schedule_message(
        self,
        event: AstrMessageEvent,
        umo: str,
        message: str,
        schedule_type: str,
        schedule_time: str,
        task_name: str = "",
        enabled: bool = True
    ) -> str:
        """创建定时发送消息任务
        
        通过此工具可以设置在指定时间自动向目标会话发送消息。
        支持一次性任务、每日重复、每周重复等多种调度方式。
        
        注意：此操作需要管理员权限。
        
        Args:
            umo(string): 目标会话的UMO标识符
            message(string): 要发送的消息内容
            schedule_type(string): 调度类型，可选值：
                - "once": 一次性任务（在指定时间点执行一次）
                - "daily": 每日任务（每天在指定时间执行）
                - "weekly": 每周任务（每周指定星期几的指定时间执行）
                - "cron": cron表达式（高级用户使用）
            schedule_time(string): 执行时间，格式根据schedule_type而定：
                - once: "2026-01-12 08:00" 或 "2026-01-12T08:00:00"
                - daily: "08:00" (每天8点)
                - weekly: "1 08:00" (每周二8点，0=周一, 6=周日)
                - cron: "0 8 * * *" (简化的cron表达式)
            task_name(string): 任务名称，用于标识任务（可选，默认自动生成）
            enabled(bool): 是否立即启用任务（可选，默认true）
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        try:
            # 获取创建者信息
            sender_name = event.get_sender_name()
            sender_id = event.get_sender_id()
            source_umo = event.unified_msg_origin
            
            # 查找来源会话
            source_contact = self.contact_manager.get_contact_by_umo(source_umo)
            source_name = source_contact.get('nickname', source_umo) if source_contact else source_umo
            
            # 构造任务配置
            task_config = {
                'target_umo': umo,
                'message': message,
                'schedule_type': schedule_type,
                'schedule_time': schedule_time,
                'task_name': task_name,
                'enabled': enabled,
                'created_by': f"{sender_name}({sender_id})",
                'created_from': source_name
            }
            
            # 添加任务
            success, msg, task_id = await self.scheduler_manager.add_task(task_config)
            
            if success:
                logger.info(f"创建定时任务: {task_name} ({task_id})")
                return f"✓ {msg}"
            else:
                logger.warning(f"创建定时任务失败: {msg}")
                return f"❌ {msg}"
                
        except Exception as e:
            logger.error(f"创建定时任务异常: {e}")
            return f"❌ 创建定时任务失败: {str(e)}"
    
    @filter.llm_tool(name="list_scheduled_messages")
    async def tool_list_scheduled_messages(
        self,
        event: AstrMessageEvent,
        filter_status: str = "all"
    ) -> str:
        """查看所有定时消息任务
        
        此工具用于查看当前所有的定时消息任务，包括任务状态、执行时间等信息。
        可以按状态筛选任务列表。
        
        Args:
            filter_status(string): 过滤状态（可选，默认"all"）
                - "all": 显示所有任务
                - "enabled": 只显示已启用的任务
                - "disabled": 只显示已禁用的任务
        """
        try:
            tasks = self.scheduler_manager.get_all_tasks(filter_status)
            result = self.scheduler_manager.format_task_list(tasks)
            logger.info(f"列出定时任务：共 {len(tasks)} 个任务")
            return result
        except Exception as e:
            logger.error(f"列出定时任务失败: {e}")
            return f"❌ 列出定时任务失败: {str(e)}"
    
    @filter.llm_tool(name="cancel_scheduled_message")
    async def tool_cancel_scheduled_message(
        self,
        event: AstrMessageEvent,
        task_id: str
    ) -> str:
        """取消并删除定时消息任务
        
        通过任务ID永久删除指定的定时消息任务。
        任务删除后无法恢复，请谨慎操作。
        
        注意：此操作需要管理员权限。
        
        Args:
            task_id(string): 任务ID（通过list_scheduled_messages工具获取）
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        try:
            success, msg = await self.scheduler_manager.remove_task(task_id)
            
            if success:
                logger.info(f"删除定时任务: {task_id}")
                return f"✓ {msg}"
            else:
                logger.warning(f"删除定时任务失败: {msg}")
                return f"❌ {msg}"
                
        except Exception as e:
            logger.error(f"删除定时任务异常: {e}")
            return f"❌ 删除定时任务失败: {str(e)}"
    
    @filter.llm_tool(name="toggle_scheduled_message")
    async def tool_toggle_scheduled_message(
        self,
        event: AstrMessageEvent,
        task_id: str,
        enabled: bool
    ) -> str:
        """启用或禁用定时消息任务
        
        暂时启用或禁用指定的定时消息任务，不会删除任务。
        禁用的任务可以随时重新启用。
        
        注意：此操作需要管理员权限。
        
        Args:
            task_id(string): 任务ID（通过list_scheduled_messages工具获取）
            enabled(bool): true=启用任务，false=禁用任务
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        try:
            success, msg = await self.scheduler_manager.toggle_task(task_id, enabled)
            
            if success:
                action = "启用" if enabled else "禁用"
                logger.info(f"{action}定时任务: {task_id}")
                return f"✓ {msg}"
            else:
                logger.warning(f"切换定时任务状态失败: {msg}")
                return f"❌ {msg}"
                
        except Exception as e:
            logger.error(f"切换定时任务状态异常: {e}")
            return f"❌ 切换任务状态失败: {str(e)}"
    
    @filter.llm_tool(name="update_scheduled_message")
    async def tool_update_scheduled_message(
        self,
        event: AstrMessageEvent,
        task_id: str,
        message: str = None,
        schedule_time: str = None,
        task_name: str = None
    ) -> str:
        """修改定时消息任务的内容或时间
        
        更新指定定时任务的消息内容、执行时间或任务名称。
        至少需要提供一个更新参数。
        
        注意：此操作需要管理员权限。
        
        Args:
            task_id(string): 任务ID（通过list_scheduled_messages工具获取）
            message(string): 新的消息内容（可选）
            schedule_time(string): 新的执行时间（可选，格式同创建时的schedule_time）
            task_name(string): 新的任务名称（可选）
        """
        # 检查权限
        has_permission, error_msg = self._check_permission(event)
        if not has_permission:
            return error_msg
        
        # 检查是否至少提供了一个更新参数
        if message is None and schedule_time is None and task_name is None:
            return "❌ 请至少提供消息内容、执行时间或任务名称中的一个"
        
        try:
            updates = {}
            if message is not None:
                updates['message'] = message
            if schedule_time is not None:
                updates['schedule_time'] = schedule_time
            if task_name is not None:
                updates['task_name'] = task_name
            
            success, msg = await self.scheduler_manager.update_task(task_id, updates)
            
            if success:
                logger.info(f"更新定时任务: {task_id}")
                return f"✓ {msg}"
            else:
                logger.warning(f"更新定时任务失败: {msg}")
                return f"❌ {msg}"
                
        except Exception as e:
            logger.error(f"更新定时任务异常: {e}")
            return f"❌ 更新定时任务失败: {str(e)}"
    
    # ============ LLM工具：历史消息查询 ============
    
    @filter.llm_tool(name="get_chat_history")
    async def tool_get_chat_history(
        self,
        event: AstrMessageEvent,
        umo: str,
        count: int = 20,
        reverse_order: bool = False
    ) -> str:
        """获取指定会话的历史消息记录
        
        通过 UMO 标识符获取群组或好友的历史消息记录。
        此工具会自动识别会话类型（群组或好友）并调用相应的 NapCat API。
        
        注意：此功能仅适用于 QQ 平台（aiocqhttp）。
        
        Args:
            umo(string): 目标会话的UMO标识符，格式为 platform:message_type:session_id
                例如: aiocqhttp_default:GroupMessage:123456789
            count(int): 获取消息数量，默认20条，最多可获取更多（可选）
            reverse_order(bool): 是否倒序排列，true=从旧到新，false=从新到旧（可选，默认false）
        """
        try:
            # 检查是否为 QQ 平台
            if event.get_platform_name() != "aiocqhttp":
                return "❌ 此功能仅支持 QQ 平台（aiocqhttp）"
            
            # 获取 client
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            
            # 从 UMO 中提取消息类型和 ID
            msg_type, session_id = self.history_manager.extract_id_from_umo(umo)
            
            if msg_type is None or session_id is None:
                return f"❌ 无法解析 UMO: {umo}\n请确保 UMO 格式正确，例如: aiocqhttp_default:GroupMessage:123456789"
            
            # 查找联系人信息
            contact = self.contact_manager.get_contact_by_umo(umo)
            contact_name = contact.get('nickname', umo) if contact else umo
            
            # 根据消息类型调用相应的 API
            if msg_type == 'group':
                success, msg, messages = await self.history_manager.get_group_history(
                    client, session_id, count, 0, reverse_order
                )
                title = f"群组 {contact_name} 的历史消息"
            else:  # friend
                success, msg, messages = await self.history_manager.get_friend_history(
                    client, session_id, count, 0, reverse_order
                )
                title = f"好友 {contact_name} 的历史消息"
            
            if not success:
                return f"❌ {msg}"
            
            # 格式化并返回结果
            result = self.history_manager.format_messages(messages, title)
            logger.info(f"获取 {contact_name} ({umo}) 的历史消息：{len(messages) if messages else 0} 条")
            return result
            
        except AssertionError:
            return "❌ 此功能仅支持 QQ 平台（aiocqhttp）"
        except Exception as e:
            logger.error(f"获取历史消息失败: {e}")
            return f"❌ 获取历史消息失败: {str(e)}"
    
    # ============ 命令：测试和管理 ============
    
    @filter.command("contacts")
    async def cmd_show_contacts(self, event: AstrMessageEvent):
        """显示所有联系人"""
        try:
            contacts = self.contact_manager.get_all_contacts()
            result = self.contact_manager.format_contact_list(contacts)
            yield event.plain_result(result)
        except Exception as e:
            yield event.plain_result(f"❌ 获取通讯录失败: {str(e)}")
    
    @filter.command("contact_info")
    async def cmd_show_info(self, event: AstrMessageEvent):
        """显示通讯录插件信息"""
        info = f"""📇 通讯录插件信息

插件名称: {self.name}
数据文件: {self.contacts_file}
联系人数量: {len(self.contact_manager.get_all_contacts())}

配置:
- 管理员数量: {len(self.admin_ids) if self.admin_ids else '所有人'}
- 模糊搜索: {'启用' if self.enable_fuzzy_search else '禁用'}
- 自动更新使用时间: {'启用' if self.auto_update_last_used else '禁用'}

使用方法:
直接与LLM对话即可使用，例如：
- "查看通讯录"
- "搜索联系人 小明"
- "给测试群发消息说你好"
- "添加联系人，昵称是开发群，UMO是..."
"""
        yield event.plain_result(info)