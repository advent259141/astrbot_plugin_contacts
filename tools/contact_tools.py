"""
通讯录管理工具
提供通讯录的增删改查功能
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


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
    
    def load_contacts(self) -> List[Dict]:
        """
        从文件加载通讯录
        
        Returns:
            联系人列表
        """
        try:
            with open(self.contacts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('contacts', [])
        except Exception as e:
            raise RuntimeError(f"加载通讯录失败: {e}")
    
    def save_contacts(self, contacts: List[Dict]):
        """
        保存通讯录到文件
        
        Args:
            contacts: 联系人列表
        """
        try:
            data = {'contacts': contacts}
            with open(self.contacts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.contacts = contacts
        except Exception as e:
            raise RuntimeError(f"保存通讯录失败: {e}")
    
    def search_contacts(self, keyword: str, fuzzy: bool = True) -> List[Dict]:
        """
        搜索联系人
        
        Args:
            keyword: 搜索关键词
            fuzzy: 是否使用模糊匹配
        
        Returns:
            匹配的联系人列表
        """
        keyword_lower = keyword.lower()
        results = []
        
        for contact in self.contacts:
            nickname = contact.get('nickname', '').lower()
            
            if fuzzy:
                # 模糊匹配：关键词在昵称中
                if keyword_lower in nickname:
                    results.append(contact)
            else:
                # 精确匹配
                if keyword_lower == nickname:
                    results.append(contact)
        
        return results
    
    def add_contact(self, nickname: str, umo: str, description: str = "") -> tuple[bool, str]:
        """
        添加联系人
        
        Args:
            nickname: 联系人昵称
            umo: UMO标识符
            description: 联系人描述
        
        Returns:
            (是否成功, 消息)
        """
        # 验证UMO格式
        if not self._validate_umo(umo):
            return False, f"UMO格式错误，应为 'platform:type:id' 格式，如 'aiocqhttp_default:GroupMessage:123456789'"
        
        # 检查昵称是否已存在
        for contact in self.contacts:
            if contact.get('nickname', '').lower() == nickname.lower():
                return False, f"昵称 '{nickname}' 已存在"
        
        # 检查UMO是否已存在
        for contact in self.contacts:
            if contact.get('umo') == umo:
                return False, f"UMO '{umo}' 已存在（昵称：{contact.get('nickname')}）"
        
        # 创建新联系人
        new_contact = {
            'nickname': nickname,
            'umo': umo,
            'description': description,
            'created_at': datetime.now().isoformat(),
            'last_used': None
        }
        
        self.contacts.append(new_contact)
        self.save_contacts(self.contacts)
        
        return True, f"已添加联系人：{nickname}"
    
    def remove_contact(self, nickname: str) -> tuple[bool, str]:
        """
        删除联系人
        
        Args:
            nickname: 联系人昵称
        
        Returns:
            (是否成功, 消息)
        """
        for i, contact in enumerate(self.contacts):
            if contact.get('nickname', '').lower() == nickname.lower():
                removed = self.contacts.pop(i)
                self.save_contacts(self.contacts)
                return True, f"已删除联系人：{removed.get('nickname')}"
        
        return False, f"未找到联系人：{nickname}"
    
    def update_contact(self, nickname: str, new_nickname: Optional[str] = None, 
                      new_description: Optional[str] = None) -> tuple[bool, str]:
        """
        更新联系人信息
        
        Args:
            nickname: 当前昵称
            new_nickname: 新昵称（可选）
            new_description: 新描述（可选）
        
        Returns:
            (是否成功, 消息)
        """
        for contact in self.contacts:
            if contact.get('nickname', '').lower() == nickname.lower():
                # 如果要更新昵称，检查新昵称是否已存在
                if new_nickname and new_nickname.lower() != nickname.lower():
                    for c in self.contacts:
                        if c.get('nickname', '').lower() == new_nickname.lower():
                            return False, f"昵称 '{new_nickname}' 已存在"
                    contact['nickname'] = new_nickname
                
                # 更新描述
                if new_description is not None:
                    contact['description'] = new_description
                
                self.save_contacts(self.contacts)
                return True, f"已更新联系人：{contact.get('nickname')}"
        
        return False, f"未找到联系人：{nickname}"
    
    def update_last_used(self, umo: str):
        """
        更新最后使用时间
        
        Args:
            umo: UMO标识符
        """
        for contact in self.contacts:
            if contact.get('umo') == umo:
                contact['last_used'] = datetime.now().isoformat()
                self.save_contacts(self.contacts)
                break
    
    def get_contact_by_umo(self, umo: str) -> Optional[Dict]:
        """
        通过UMO获取联系人信息
        
        Args:
            umo: UMO标识符
        
        Returns:
            联系人信息，如果不存在则返回None
        """
        for contact in self.contacts:
            if contact.get('umo') == umo:
                return contact
        return None
    
    def get_contact_by_nickname(self, nickname: str) -> Optional[Dict]:
        """
        通过昵称获取联系人信息（精确匹配）
        
        Args:
            nickname: 联系人昵称
        
        Returns:
            联系人信息，如果不存在则返回None
        """
        for contact in self.contacts:
            if contact.get('nickname', '').lower() == nickname.lower():
                return contact
        return None
    
    def get_all_contacts(self) -> List[Dict]:
        """
        获取所有联系人
        
        Returns:
            所有联系人列表
        """
        return self.contacts.copy()
    
    def _validate_umo(self, umo: str) -> bool:
        """
        验证UMO格式
        
        Args:
            umo: UMO字符串
        
        Returns:
            是否有效
        """
        parts = umo.split(':')
        # UMO格式: platform_id:message_type:session_id
        # 至少需要3个部分
        return len(parts) >= 3 and all(part.strip() for part in parts)
    
    def format_contact_list(self, contacts: List[Dict]) -> str:
        """
        格式化联系人列表为易读的字符串
        
        Args:
            contacts: 联系人列表
        
        Returns:
            格式化后的字符串
        """
        if not contacts:
            return "通讯录为空"
        
        result = f"📇 通讯录列表（共{len(contacts)}个联系人）：\n\n"
        
        for i, contact in enumerate(contacts, 1):
            nickname = contact.get('nickname', '未命名')
            umo = contact.get('umo', '无')
            description = contact.get('description', '')
            
            result += f"{i}. {nickname}\n"
            result += f"   UMO: {umo}\n"
            if description:
                result += f"   描述: {description}\n"
            result += "\n"
        
        return result.strip()
    
    def format_search_result(self, keyword: str, contacts: List[Dict]) -> str:
        """
        格式化搜索结果为易读的字符串
        
        Args:
            keyword: 搜索关键词
            contacts: 搜索结果列表
        
        Returns:
            格式化后的字符串
        """
        if not contacts:
            return f"🔍 搜索结果（关键词: \"{keyword}\"）：\n\n未找到匹配的联系人"
        
        result = f"🔍 搜索结果（关键词: \"{keyword}\"）：\n\n"
        result += f"找到{len(contacts)}个匹配的联系人：\n\n"
        
        for i, contact in enumerate(contacts, 1):
            nickname = contact.get('nickname', '未命名')
            umo = contact.get('umo', '无')
            description = contact.get('description', '')
            
            result += f"{i}. {nickname}\n"
            result += f"   UMO: {umo}\n"
            if description:
                result += f"   描述: {description}\n"
            result += "\n"
        
        return result.strip()