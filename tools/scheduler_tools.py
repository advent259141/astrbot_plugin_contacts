"""
定时任务管理工具
提供定时发送消息的功能
"""

import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from astrbot.api import logger


class SchedulerManager:
    """定时任务管理器"""
    
    def __init__(self, data_file: str, send_message_callback: Callable):
        """
        初始化定时任务管理器
        
        Args:
            data_file: 定时任务JSON文件的完整路径
            send_message_callback: 发送消息的回调函数 async def(umo, message, task_info)
        """
        self.data_file = Path(data_file)
        self.tasks = []
        self.running_tasks = {}  # task_id -> asyncio.Task
        self.send_message_callback = send_message_callback
        self._stop_event = asyncio.Event()
        
        # 如果文件不存在，创建空任务列表
        if not self.data_file.exists():
            self.save_tasks([])
        else:
            self.tasks = self.load_tasks()
    
    def load_tasks(self) -> List[Dict]:
        """
        从文件加载定时任务
        
        Returns:
            任务列表
        """
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('tasks', [])
        except Exception as e:
            logger.error(f"加载定时任务失败: {e}")
            return []
    
    def save_tasks(self, tasks: List[Dict]):
        """
        保存定时任务到文件
        
        Args:
            tasks: 任务列表
        """
        try:
            data = {'tasks': tasks}
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.tasks = tasks
        except Exception as e:
            logger.error(f"保存定时任务失败: {e}")
            raise RuntimeError(f"保存定时任务失败: {e}")
    
    async def start(self):
        """启动调度器，加载并调度所有启用的任务"""
        logger.info(f"启动定时任务调度器，共 {len(self.tasks)} 个任务")
        self._stop_event.clear()
        
        for task in self.tasks:
            if task.get('enabled', True):
                await self._schedule_task(task)
        
        logger.info("定时任务调度器启动完成")
    
    async def stop(self):
        """停止所有任务"""
        logger.info("停止定时任务调度器...")
        self._stop_event.set()
        
        # 取消所有运行中的任务
        for task_id, async_task in list(self.running_tasks.items()):
            async_task.cancel()
            try:
                await async_task
            except asyncio.CancelledError:
                pass
        
        self.running_tasks.clear()
        logger.info("定时任务调度器已停止")
    
    async def add_task(self, task_config: Dict) -> tuple[bool, str, str]:
        """
        添加新任务
        
        Args:
            task_config: 任务配置
        
        Returns:
            (是否成功, 消息, task_id)
        """
        try:
            # 生成唯一ID
            task_id = str(uuid.uuid4())
            
            # 验证必需字段
            required_fields = ['target_umo', 'message', 'schedule_type', 'schedule_time']
            for field in required_fields:
                if field not in task_config:
                    return False, f"缺少必需字段: {field}", ""
            
            # 解析调度配置
            schedule_config = self._parse_schedule_config(
                task_config['schedule_type'],
                task_config['schedule_time']
            )
            
            if not schedule_config:
                return False, f"无效的调度配置: {task_config['schedule_type']} - {task_config['schedule_time']}", ""
            
            # 计算下次执行时间
            next_run = self._calculate_next_run(task_config['schedule_type'], schedule_config)
            if not next_run:
                return False, "无法计算下次执行时间", ""
            
            # 创建任务
            task = {
                'task_id': task_id,
                'task_name': task_config.get('task_name', f"任务_{task_id[:8]}"),
                'target_umo': task_config['target_umo'],
                'message': task_config['message'],
                'schedule_type': task_config['schedule_type'],
                'schedule_config': schedule_config,
                'created_by': task_config.get('created_by', '未知'),
                'created_from': task_config.get('created_from', '未知'),
                'created_at': datetime.now().isoformat(),
                'enabled': task_config.get('enabled', True),
                'last_run': None,
                'next_run': next_run.isoformat()
            }
            
            # 保存任务
            self.tasks.append(task)
            self.save_tasks(self.tasks)
            
            # 如果启用，立即调度
            if task['enabled']:
                await self._schedule_task(task)
            
            logger.info(f"添加定时任务: {task['task_name']} ({task_id})")
            return True, f"已创建定时任务：{task['task_name']}\n任务ID: {task_id}\n下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S')}", task_id
            
        except Exception as e:
            logger.error(f"添加定时任务失败: {e}")
            return False, f"添加定时任务失败: {str(e)}", ""
    
    def _parse_schedule_config(self, schedule_type: str, schedule_time: str) -> Optional[Dict]:
        """
        解析调度配置
        
        Args:
            schedule_type: 调度类型
            schedule_time: 调度时间字符串
        
        Returns:
            调度配置字典
        """
        try:
            if schedule_type == 'once':
                # 格式: "2026-01-12 08:00" 或 "2026-01-12T08:00:00"
                execute_time = datetime.fromisoformat(schedule_time.replace(' ', 'T'))
                return {'execute_time': execute_time.isoformat()}
            
            elif schedule_type == 'daily':
                # 格式: "08:00"
                time_parts = schedule_time.split(':')
                if len(time_parts) != 2:
                    return None
                hour, minute = int(time_parts[0]), int(time_parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    return None
                return {'hour': hour, 'minute': minute}
            
            elif schedule_type == 'weekly':
                # 格式: "1 08:00" (0=周一, 6=周日)
                parts = schedule_time.split()
                if len(parts) != 2:
                    return None
                day = int(parts[0])
                time_parts = parts[1].split(':')
                if len(time_parts) != 2:
                    return None
                hour, minute = int(time_parts[0]), int(time_parts[1])
                if not (0 <= day <= 6 and 0 <= hour <= 23 and 0 <= minute <= 59):
                    return None
                return {'day': day, 'hour': hour, 'minute': minute}
            
            elif schedule_type == 'cron':
                # 简化的cron支持，格式: "minute hour * * *"
                # 暂时只支持固定时间，不支持复杂表达式
                parts = schedule_time.split()
                if len(parts) < 2:
                    return None
                minute, hour = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    return None
                return {'hour': hour, 'minute': minute, 'expression': schedule_time}
            
            return None
            
        except Exception as e:
            logger.error(f"解析调度配置失败: {e}")
            return None
    
    def _calculate_next_run(self, schedule_type: str, schedule_config: Dict) -> Optional[datetime]:
        """
        计算下次执行时间
        
        Args:
            schedule_type: 调度类型
            schedule_config: 调度配置
        
        Returns:
            下次执行时间
        """
        try:
            now = datetime.now()
            
            if schedule_type == 'once':
                execute_time = datetime.fromisoformat(schedule_config['execute_time'])
                if execute_time > now:
                    return execute_time
                return None  # 已过期
            
            elif schedule_type == 'daily':
                next_run = now.replace(
                    hour=schedule_config['hour'],
                    minute=schedule_config['minute'],
                    second=0,
                    microsecond=0
                )
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run
            
            elif schedule_type == 'weekly':
                # 计算到指定星期几的天数
                current_weekday = now.weekday()
                target_weekday = schedule_config['day']
                days_ahead = target_weekday - current_weekday
                
                next_run = now.replace(
                    hour=schedule_config['hour'],
                    minute=schedule_config['minute'],
                    second=0,
                    microsecond=0
                )
                
                if days_ahead < 0 or (days_ahead == 0 and next_run <= now):
                    days_ahead += 7
                
                next_run += timedelta(days=days_ahead)
                return next_run
            
            elif schedule_type == 'cron':
                # 简化处理：每天固定时间
                next_run = now.replace(
                    hour=schedule_config['hour'],
                    minute=schedule_config['minute'],
                    second=0,
                    microsecond=0
                )
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run
            
            return None
            
        except Exception as e:
            logger.error(f"计算下次执行时间失败: {e}")
            return None
    
    async def _schedule_task(self, task: Dict):
        """
        调度单个任务
        
        Args:
            task: 任务配置
        """
        task_id = task['task_id']
        
        # 如果任务已在运行，先取消
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            try:
                await self.running_tasks[task_id]
            except asyncio.CancelledError:
                pass
        
        # 创建新的异步任务
        async_task = asyncio.create_task(self._task_loop(task))
        self.running_tasks[task_id] = async_task
    
    async def _task_loop(self, task: Dict):
        """
        任务执行循环
        
        Args:
            task: 任务配置
        """
        task_id = task['task_id']
        
        try:
            while task['enabled'] and not self._stop_event.is_set():
                # 计算等待时间
                next_run_str = task.get('next_run')
                if not next_run_str:
                    logger.warning(f"任务 {task_id} 没有下次执行时间")
                    break
                
                next_run = datetime.fromisoformat(next_run_str)
                now = datetime.now()
                wait_seconds = (next_run - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"任务 {task['task_name']} 将在 {wait_seconds:.0f} 秒后执行")
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
                        # 如果等待被中断（收到停止信号），退出循环
                        break
                    except asyncio.TimeoutError:
                        # 超时正常，继续执行任务
                        pass
                
                # 执行任务
                await self._execute_task(task)
                
                # 更新最后执行时间
                task['last_run'] = datetime.now().isoformat()
                
                # 如果是一次性任务，执行后禁用
                if task['schedule_type'] == 'once':
                    task['enabled'] = False
                    self.save_tasks(self.tasks)
                    logger.info(f"一次性任务 {task['task_name']} 已完成并禁用")
                    break
                
                # 计算下次执行时间
                next_run = self._calculate_next_run(
                    task['schedule_type'],
                    task['schedule_config']
                )
                
                if next_run:
                    task['next_run'] = next_run.isoformat()
                    self.save_tasks(self.tasks)
                else:
                    logger.warning(f"无法计算任务 {task['task_name']} 的下次执行时间")
                    break
        
        except asyncio.CancelledError:
            logger.info(f"任务 {task['task_name']} 被取消")
        except Exception as e:
            logger.error(f"任务 {task['task_name']} 执行循环异常: {e}")
        finally:
            # 清理运行中的任务记录
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
    
    async def _execute_task(self, task: Dict):
        """
        执行任务（发送消息）
        
        Args:
            task: 任务配置
        """
        try:
            logger.info(f"执行定时任务: {task['task_name']}")
            
            # 调用发送消息回调
            await self.send_message_callback(
                task['target_umo'],
                task['message'],
                task
            )
            
            logger.info(f"定时任务 {task['task_name']} 执行成功")
            
        except Exception as e:
            logger.error(f"执行定时任务 {task['task_name']} 失败: {e}")
    
    async def remove_task(self, task_id: str) -> tuple[bool, str]:
        """
        删除任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 查找任务
            task = None
            for i, t in enumerate(self.tasks):
                if t['task_id'] == task_id:
                    task = self.tasks.pop(i)
                    break
            
            if not task:
                return False, f"未找到任务: {task_id}"
            
            # 取消运行中的任务
            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                try:
                    await self.running_tasks[task_id]
                except asyncio.CancelledError:
                    pass
                del self.running_tasks[task_id]
            
            # 保存
            self.save_tasks(self.tasks)
            
            logger.info(f"删除定时任务: {task['task_name']}")
            return True, f"已删除任务: {task['task_name']}"
            
        except Exception as e:
            logger.error(f"删除定时任务失败: {e}")
            return False, f"删除任务失败: {str(e)}"
    
    async def toggle_task(self, task_id: str, enabled: bool) -> tuple[bool, str]:
        """
        启用/禁用任务
        
        Args:
            task_id: 任务ID
            enabled: 是否启用
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 查找任务
            task = None
            for t in self.tasks:
                if t['task_id'] == task_id:
                    task = t
                    break
            
            if not task:
                return False, f"未找到任务: {task_id}"
            
            # 更新状态
            old_enabled = task['enabled']
            task['enabled'] = enabled
            
            if enabled and not old_enabled:
                # 启用任务
                await self._schedule_task(task)
                self.save_tasks(self.tasks)
                logger.info(f"启用定时任务: {task['task_name']}")
                return True, f"已启用任务: {task['task_name']}"
            elif not enabled and old_enabled:
                # 禁用任务
                if task_id in self.running_tasks:
                    self.running_tasks[task_id].cancel()
                    try:
                        await self.running_tasks[task_id]
                    except asyncio.CancelledError:
                        pass
                    del self.running_tasks[task_id]
                self.save_tasks(self.tasks)
                logger.info(f"禁用定时任务: {task['task_name']}")
                return True, f"已禁用任务: {task['task_name']}"
            else:
                return True, f"任务状态未改变: {task['task_name']}"
            
        except Exception as e:
            logger.error(f"切换定时任务状态失败: {e}")
            return False, f"切换任务状态失败: {str(e)}"
    
    async def update_task(self, task_id: str, updates: Dict) -> tuple[bool, str]:
        """
        更新任务配置
        
        Args:
            task_id: 任务ID
            updates: 更新内容 (message, schedule_time, task_name)
        
        Returns:
            (是否成功, 消息)
        """
        try:
            # 查找任务
            task = None
            for t in self.tasks:
                if t['task_id'] == task_id:
                    task = t
                    break
            
            if not task:
                return False, f"未找到任务: {task_id}"
            
            # 更新字段
            if 'message' in updates:
                task['message'] = updates['message']
            
            if 'task_name' in updates:
                task['task_name'] = updates['task_name']
            
            if 'schedule_time' in updates:
                # 重新解析调度配置
                schedule_config = self._parse_schedule_config(
                    task['schedule_type'],
                    updates['schedule_time']
                )
                
                if not schedule_config:
                    return False, f"无效的调度配置: {updates['schedule_time']}"
                
                task['schedule_config'] = schedule_config
                
                # 重新计算下次执行时间
                next_run = self._calculate_next_run(
                    task['schedule_type'],
                    schedule_config
                )
                
                if next_run:
                    task['next_run'] = next_run.isoformat()
                else:
                    return False, "无法计算下次执行时间"
                
                # 如果任务启用，重新调度
                if task['enabled']:
                    await self._schedule_task(task)
            
            # 保存
            self.save_tasks(self.tasks)
            
            logger.info(f"更新定时任务: {task['task_name']}")
            return True, f"已更新任务: {task['task_name']}"
            
        except Exception as e:
            logger.error(f"更新定时任务失败: {e}")
            return False, f"更新任务失败: {str(e)}"
    
    def get_all_tasks(self, filter_status: str = 'all') -> List[Dict]:
        """
        获取所有任务
        
        Args:
            filter_status: 过滤状态 (all, enabled, disabled)
        
        Returns:
            任务列表
        """
        if filter_status == 'enabled':
            return [t for t in self.tasks if t.get('enabled', True)]
        elif filter_status == 'disabled':
            return [t for t in self.tasks if not t.get('enabled', True)]
        else:
            return self.tasks.copy()
    
    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """
        通过ID获取任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务信息
        """
        for task in self.tasks:
            if task['task_id'] == task_id:
                return task
        return None
    
    def format_task_list(self, tasks: List[Dict]) -> str:
        """
        格式化任务列表为易读的字符串
        
        Args:
            tasks: 任务列表
        
        Returns:
            格式化后的字符串
        """
        if not tasks:
            return "📅 定时任务列表为空"
        
        result = f"📅 定时任务列表（共{len(tasks)}个任务）：\n\n"
        
        for i, task in enumerate(tasks, 1):
            task_name = task.get('task_name', '未命名')
            task_id = task.get('task_id', '无')
            enabled = task.get('enabled', True)
            status = "✅ 启用" if enabled else "⏸️ 禁用"
            
            target_umo = task.get('target_umo', '无')
            message = task.get('message', '')
            schedule_type = task.get('schedule_type', '未知')
            
            # 调度类型描述
            type_desc = {
                'once': '一次性',
                'daily': '每日',
                'weekly': '每周',
                'cron': 'Cron'
            }.get(schedule_type, schedule_type)
            
            next_run = task.get('next_run')
            last_run = task.get('last_run')
            
            result += f"{i}. {task_name} ({status})\n"
            result += f"   任务ID: {task_id}\n"
            result += f"   目标会话: {target_umo}\n"
            result += f"   消息内容: {message}\n"
            result += f"   调度类型: {type_desc}\n"
            
            if next_run:
                next_run_dt = datetime.fromisoformat(next_run)
                result += f"   下次执行: {next_run_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if last_run:
                last_run_dt = datetime.fromisoformat(last_run)
                result += f"   最后执行: {last_run_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            result += "\n"
        
        return result.strip()