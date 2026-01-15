"""
NapCat API 历史消息工具
提供获取群组和好友历史消息的功能
"""

import json
from typing import List, Dict, Optional, Tuple
from astrbot.api import logger


class HistoryManager:
    """历史消息管理器"""
    
    def __init__(self):
        """初始化历史消息管理器"""
        pass
    
    async def get_group_history(
        self, 
        client, 
        group_id: int, 
        count: int = 20,
        message_seq: int = 0,
        reverse_order: bool = False
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取群组历史消息
        
        Args:
            client: NapCat API 客户端 (bot)
            group_id: 群号
            count: 获取消息数量，默认20条
            message_seq: 起始消息序号，0为最新消息
            reverse_order: 是否倒序，默认False
            
        Returns:
            (是否成功, 消息, 历史记录列表)
        """
        try:
            # 构造请求参数
            payloads = {
                "group_id": group_id,
                "message_seq": message_seq,
                "count": count,
                "reverseOrder": reverse_order
            }
            
            logger.info(f"调用 get_group_msg_history API，参数: {payloads}")
            
            # 调用 NapCat API
            ret = await client.api.call_action('get_group_msg_history', **payloads)
            
            # NapCat API 直接返回包含 messages 的字典
            messages = ret.get('messages', [])
            
            logger.info(f"成功获取群 {group_id} 的历史消息，共 {len(messages)} 条")
            return True, f"成功获取 {len(messages)} 条历史消息", messages
            
            logger.info(f"成功获取群 {group_id} 的历史消息，共 {len(messages)} 条")
            return True, f"成功获取 {len(messages)} 条历史消息", messages
            
        except Exception as e:
            logger.error(f"获取群历史消息异常: {e}")
            return False, f"获取群历史消息异常: {str(e)}", None
    
    async def get_friend_history(
        self, 
        client, 
        user_id: int, 
        count: int = 20,
        message_seq: int = 0,
        reverse_order: bool = False
    ) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取好友历史消息
        
        Args:
            client: NapCat API 客户端 (bot)
            user_id: 好友QQ号
            count: 获取消息数量，默认20条
            message_seq: 起始消息序号，0为最新消息
            reverse_order: 是否倒序，默认False
            
        Returns:
            (是否成功, 消息, 历史记录列表)
        """
        try:
            # 构造请求参数
            payloads = {
                "user_id": user_id,
                "message_seq": message_seq,
                "count": count,
                "reverseOrder": reverse_order
            }
            
            logger.info(f"调用 get_friend_msg_history API，参数: {payloads}")
            
            # 调用 NapCat API
            ret = await client.api.call_action('get_friend_msg_history', **payloads)
            
            # NapCat API 直接返回包含 messages 的字典
            messages = ret.get('messages', [])
            
            logger.info(f"成功获取好友 {user_id} 的历史消息，共 {len(messages)} 条")
            return True, f"成功获取 {len(messages)} 条历史消息", messages
            
            logger.info(f"成功获取好友 {user_id} 的历史消息，共 {len(messages)} 条")
            return True, f"成功获取 {len(messages)} 条历史消息", messages
            
        except Exception as e:
            logger.error(f"获取好友历史消息异常: {e}")
            return False, f"获取好友历史消息异常: {str(e)}", None
    
    def _serialize_message_content(self, message_data: any) -> str:
        """
        序列化消息内容
        
        Args:
            message_data: 消息数据，可能是字符串、列表或字典
            
        Returns:
            序列化后的字符串
        """
        if isinstance(message_data, str):
            return message_data
        elif isinstance(message_data, list):
            # 消息段数组，需要拼接
            parts = []
            for seg in message_data:
                if isinstance(seg, dict):
                    seg_type = seg.get('type', 'unknown')
                    seg_data = seg.get('data', {})
                    
                    if seg_type == 'text':
                        parts.append(seg_data.get('text', ''))
                    elif seg_type == 'at':
                        qq = seg_data.get('qq', '')
                        parts.append(f"[@{qq}]")
                    elif seg_type == 'image':
                        summary = seg_data.get('summary', '图片')
                        parts.append(f"[图片:{summary}]")
                    elif seg_type == 'reply':
                        reply_id = seg_data.get('id', '')
                        parts.append(f"[回复:{reply_id}]")
                    elif seg_type == 'face':
                        face_id = seg_data.get('id', '')
                        parts.append(f"[表情:{face_id}]")
                    else:
                        parts.append(f"[{seg_type}]")
                else:
                    parts.append(str(seg))
            return ''.join(parts)
        else:
            return str(message_data)
    
    def format_messages(self, messages: List[Dict], title: str = "历史消息") -> str:
        """
        格式化历史消息为易读的字符串，并序列化消息内容
        
        Args:
            messages: 消息列表
            title: 标题
            
        Returns:
            格式化后的字符串
        """
        if not messages:
            return f"📜 {title}：\n\n暂无消息记录"
        
        result = f"📜 {title}（共 {len(messages)} 条）：\n\n"
        
        for i, msg in enumerate(messages, 1):
            # 提取消息基本信息
            message_id = msg.get('message_id', '未知')
            message_seq = msg.get('message_seq', '未知')
            
            # 序列化消息内容
            # 优先使用 raw_message，如果没有则使用 message 字段
            raw_message = msg.get('raw_message')
            if raw_message:
                message_text = raw_message
            else:
                message_data = msg.get('message', '')
                message_text = self._serialize_message_content(message_data)
            
            # 提取发送者信息
            sender = msg.get('sender', {})
            sender_id = sender.get('user_id', '未知')
            sender_name = sender.get('nickname', '未知')
            sender_card = sender.get('card', '')
            
            # 显示名称（优先使用群名片）
            display_name = sender_card if sender_card else sender_name
            
            # 提取时间信息
            time = msg.get('time', 0)
            from datetime import datetime
            time_str = datetime.fromtimestamp(time).strftime('%H:%M:%S') if time else '未知时间'
            
            result += f"{i}. [{time_str}] {display_name}({sender_id})\n"
            result += f"   {message_text}\n"
            result += "\n"
        
        return result.strip()
    
    def extract_id_from_umo(self, umo: str) -> Tuple[Optional[str], Optional[int]]:
        """
        从 UMO 中提取消息类型和 ID
        
        Args:
            umo: UMO 标识符，格式为 platform:message_type:session_id
            例如: 小面包:GroupMessage:528069839 或 aiocqhttp_default:GroupMessage:123456789
            
        Returns:
            (消息类型, ID)
            消息类型: 'group' 或 'friend'
            ID: 群号或好友QQ号
        """
        try:
            parts = umo.split(':')
            logger.info(f"解析 UMO: {umo}, 分割后: {parts}")
            
            if len(parts) < 3:
                logger.warning(f"UMO 格式错误，分段数不足3: {parts}")
                return None, None
            
            # 第二部分是消息类型
            message_type = parts[1].lower()
            # 第三部分是会话ID
            session_id = parts[2]
            
            logger.info(f"提取到消息类型: {message_type}, 会话ID: {session_id}")
            
            # 转换为整数
            try:
                id_int = int(session_id)
            except ValueError:
                logger.error(f"会话ID无法转换为整数: {session_id}")
                return None, None
            
            # 判断消息类型
            if 'group' in message_type:
                logger.info(f"识别为群组消息，群号: {id_int}")
                return 'group', id_int
            elif 'friend' in message_type or 'private' in message_type:
                logger.info(f"识别为好友消息，QQ号: {id_int}")
                return 'friend', id_int
            else:
                logger.warning(f"未知的消息类型: {message_type}")
                return None, None
                
        except Exception as e:
            logger.error(f"解析 UMO 失败: {e}")
            return None, None