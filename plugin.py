import asyncio
import aiohttp
import os
import json
import logging
import time
import base64
from typing import List, Tuple, Type, Optional, Dict, Any
from src.chat.message_receive.message import MessageRecv
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseCommand,
    ComponentInfo,
    ConfigField,
)

logger = logging.getLogger("suno_ai")


class SunoAIClient:
    """Suno AI API客户端 - 支持Vector Engine API"""
    def __init__(self, cookie: str, api_base: str = "https://api.vectorengine.ai", api_key: str = ""):
        self.cookie = cookie
        self.api_base = api_base
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        # 添加API密钥认证
        if api_key:
            self.headers.update({
                "Authorization": f"Bearer {api_key}"
            })
    
    async def generate_song(self, prompt: str, style: str = "", title: str = "", music_type: str = "song", model: str = "chirp-v4", continue_at: float = 0.0, continue_clip_id: str = "", task_id: str = "", notify_hook: str = "") -> Optional[str]:
        """生成歌曲 - 使用Vector Engine API
        
        Args:
            prompt: 自定义的完整歌词或创作提示词
            style: 歌曲风格，使用半角逗号隔开
            title: 歌词标题
            music_type: 音乐类型，song或pure_music
            model: 模型版本号，支持chirp-v3-0, chirp-v3-5, chirp-v4, chirp-auk, chirp-v5
            continue_at: 续写起始时间点，浮点数，单位为秒
            continue_clip_id: 需要续写的歌曲ID
            task_id: 任务ID，用于对已有任务进行操作（如续写）
            notify_hook: 任务完成后的回调通知地址
        
        Returns:
            task_id: 生成的任务ID
        """
        url = f"{self.api_base}/suno/submit/music"
        
        # 检查模型是否在支持列表中
        supported_models = ["chirp-v3-0", "chirp-v3-5", "chirp-v4", "chirp-auk", "chirp-v5"]
        if model not in supported_models:
            model = "chirp-v4"  # 默认使用最新模型
            logger.warning(f"模型 {model} 不在支持列表中，使用默认模型 chirp-v4")
        
        # 确保必填字段
        if not prompt:
            logger.error("生成歌曲失败: 缺少必填参数 prompt")
            return None
        
        if not title:
            title = prompt[:20]  # 使用prompt前20个字符作为标题
        
        # 准备API请求参数 - 根据最新OpenAPI规范
        payload = {
            "prompt": prompt,  # 歌词内容，仅用于自定义模式，必填
            "mv": model,  # 模型选择，必填
            "title": title,  # 歌曲标题，仅用于自定义模式，可选
            "tags": style,  # 风格标签，多个标签用半角逗号分隔，可选
            "make_instrumental": music_type == "pure_music",  # 是否生成纯音乐版本
            "gpt_description_prompt": prompt,  # 创作描述提示词，仅用于灵感模式，必需
        }
        
        # 添加续写相关参数（如果提供）
        if continue_clip_id:
            payload["continue_at"] = continue_at
            payload["continue_clip_id"] = continue_clip_id
            logger.info(f"使用续写模式生成歌曲，续写歌曲ID: {continue_clip_id}，续写时间点: {continue_at}")
        
        # 添加任务ID（如果提供）
        if task_id:
            payload["task_id"] = task_id
            logger.info(f"使用任务ID: {task_id} 进行操作")
        
        # 添加回调通知地址（如果提供）
        if notify_hook:
            payload["notify_hook"] = notify_hook
            logger.info(f"设置回调通知地址: {notify_hook}")
        
        logger.info(f"使用生成模式生成歌曲，模型: {model}")
        if music_type == "pure_music":
            logger.info("生成纯音乐")
        
        # 确保必填参数存在
        if not payload.get("mv"):
            payload["mv"] = "chirp-v4"
        
        if not payload.get("gpt_description_prompt"):
            payload["gpt_description_prompt"] = "一首动听的歌曲"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                logger.info(f"请求参数: {payload}")
                async with session.post(url, headers=self.headers, json=payload) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if data.get("code") == "success":
                                # 返回task_id
                                return data["data"]
                            else:
                                logger.error(f"生成歌曲失败: {data.get('message')}")
                        else:
                            logger.error(f"生成歌曲失败: 无效的响应格式")
                    else:
                        logger.error(f"生成歌曲请求失败，状态码: {response.status}")
                        logger.error(f"响应内容: {response_text}")
        except Exception as e:
            logger.error(f"生成歌曲异常: {str(e)}")
        return None
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """查询单个任务状态 - 使用Vector Engine API
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict: 包含任务状态的字典
        """
        # 使用新的API路径格式，task_id作为路径参数
        url = f"{self.api_base}/suno/fetch/{task_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                async with session.get(url, headers=self.headers) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")  # 记录完整响应内容，以便调试
                    
                    if response.status == 200:
                        # 检查响应内容类型
                        content_type = response.headers.get("Content-Type", "")
                        if "text/html" in content_type:
                            # 处理HTML响应，这通常是API网关错误或重定向
                            logger.error(f"获取任务状态失败: API返回了HTML页面而不是JSON响应")
                            logger.error(f"请检查API地址是否正确，或尝试使用不同的API基础地址")
                            return {"success": False, "error": "HTML_RESPONSE"}
                        
                        try:
                            data = await response.json()
                            if isinstance(data, dict):
                                if data.get("code") == "success":
                                    task_data = data.get("data", {})
                                    status = task_data.get("status", "PROCESSING")
                                    
                                    # 转换状态映射
                                    status_mapping = {
                                        "SUCCESS": "SUCCESS",
                                        "FAILURE": "FAILED",
                                        "IN_PROGRESS": "PROCESSING",
                                        "QUEUED": "PROCESSING",
                                        "SUBMITTED": "PROCESSING",
                                        "NOT_START": "PROCESSING"
                                    }
                                    
                                    mapped_status = status_mapping.get(status, "PROCESSING")
                                    
                                    # 尝试从不同字段获取歌曲URL
                                    song_url = None
                                    
                                    # 扩展URL字段列表，增加更多可能的字段名
                                    potential_url_fields = [
                                        "audio_url", "url", "song_url", "play_url", "download_url",
                                        "audio", "audio_file", "file_url", "mp3_url", "mp3",
                                        "song", "music_url", "music_file", "download", "play"
                                    ]
                                    
                                    # 处理两种可能的响应格式
                                    clip_id = None
                                    clip = {}
                                    
                                    # 情况1：task_data是字符串（直接是clip_id）
                                    if isinstance(task_data, str):
                                        clip_id = task_data
                                        # 如果是字符串，尝试解析为JSON
                                        try:
                                            task_data_json = json.loads(task_data)
                                            if isinstance(task_data_json, dict):
                                                task_data = task_data_json
                                            elif isinstance(task_data_json, list) and task_data_json:
                                                task_data = task_data_json[0]
                                        except (json.JSONDecodeError, TypeError):
                                            pass
                                    
                                    # 情况2：task_data是字典
                                    if isinstance(task_data, dict):
                                        # 尝试获取clip_id
                                        clip_id = task_data.get("id") or task_data.get("clip_id") or task_data.get("clipId")
                                        
                                        # 记录task_data结构，便于调试
                                        logger.info(f"task_data结构: {json.dumps(task_data, ensure_ascii=False, indent=2)}")
                                        
                                        # 尝试从task_data直接获取URL
                                        for field in potential_url_fields:
                                            if task_data.get(field):
                                                song_url = task_data.get(field)
                                                logger.info(f"从task_data直接获取到URL: {song_url}")
                                                break
                                        
                                        # 检查嵌套结构
                                        if not song_url:
                                            # 检查clip或audio字段中的URL
                                            for nested_key in ["clip", "audio", "result", "data"]:
                                                nested = task_data.get(nested_key, {})
                                                if isinstance(nested, dict):
                                                    # 从嵌套结构获取clip_id
                                                    clip_id = clip_id or nested.get("id") or nested.get("clip_id") or nested.get("clipId")
                                                    # 从嵌套结构获取URL
                                                    for field in potential_url_fields:
                                                        if nested.get(field):
                                                            song_url = nested.get(field)
                                                            logger.info(f"从{nested_key}获取到URL: {song_url}")
                                                            break
                                                    if song_url:
                                                        break
                                                    
                                                    # 检查嵌套结构中的嵌套结构
                                                    for deep_key in ["clip", "audio", "result"]:
                                                        deep_nested = nested.get(deep_key, {})
                                                        if isinstance(deep_nested, dict):
                                                            # 从深层嵌套结构获取clip_id
                                                            clip_id = clip_id or deep_nested.get("id") or deep_nested.get("clip_id") or deep_nested.get("clipId")
                                                            # 从深层嵌套结构获取URL
                                                            for field in potential_url_fields:
                                                                if deep_nested.get(field):
                                                                    song_url = deep_nested.get(field)
                                                                    logger.info(f"从{nested_key}.{deep_key}获取到URL: {song_url}")
                                                                    break
                                                            if song_url:
                                                                break
                                                    if song_url:
                                                        break
                                        
                                        # 检查audio_info或similar字段
                                        if not song_url:
                                            audio_info = task_data.get("audio_info", {}) or task_data.get("audioInfo", {})
                                            if isinstance(audio_info, dict):
                                                for field in potential_url_fields:
                                                    if audio_info.get(field):
                                                        song_url = audio_info.get(field)
                                                        logger.info(f"从audio_info获取到URL: {song_url}")
                                                        break
                                        
                                        # 检查results列表
                                        if not song_url:
                                            results = task_data.get("results", []) or task_data.get("clips", [])
                                            if isinstance(results, list):
                                                for item in results:
                                                    if isinstance(item, dict):
                                                        # 从results列表获取clip_id
                                                        clip_id = clip_id or item.get("id") or item.get("clip_id") or item.get("clipId")
                                                        # 从results列表获取URL
                                                        for field in potential_url_fields:
                                                            if item.get(field):
                                                                song_url = item.get(field)
                                                                logger.info(f"从results列表获取到URL: {song_url}")
                                                                break
                                                    if song_url:
                                                        break
                                    
                                    # 如果还是没有找到URL，尝试从raw_data中提取
                                    if not song_url and isinstance(task_data, str):
                                        import re
                                        # 使用正则表达式从字符串中提取URL
                                        url_pattern = r'(https?://[^\s"\'<]+\.(mp3|wav|aac|flac|ogg))'
                                        matches = re.findall(url_pattern, task_data)
                                        if matches:
                                            song_url = matches[0][0]  # 获取完整URL，而不仅仅是文件扩展名
                                            logger.info(f"从字符串中提取到URL: {song_url}")
                                    
                                    # 最后的尝试：如果有clip_id，构造一个可能的URL
                                    if not song_url and clip_id:
                                        # 尝试构造Suno官方URL格式
                                        possible_urls = [
                                            f"https://app.suno.ai/api/clips/{clip_id}/audio",
                                            f"https://app.suno.ai/api/v1/clips/{clip_id}/audio",
                                            f"https://cdn.suno.ai/{clip_id}.mp3"
                                        ]
                                        # 记录可能的URL，便于调试
                                        logger.info(f"构造可能的URL列表: {possible_urls}")
                                        # 这里不直接设置song_url，因为这些是猜测的URL
                                    
                                    # 提取其他资源信息
                                    image_url = None
                                    lyrics = None
                                    title = None  # 初始化为None，确保在所有情况下都有定义
                                    author = None  # 初始化为None，确保在所有情况下都有定义
                                    
                                    # 首先检查task_data是否直接包含资源信息（用户提供的最新响应格式）
                                    if isinstance(task_data, dict):
                                        # 检查是否直接包含资源字段
                                        if "audio_url" in task_data or "image_url" in task_data or "prompt" in task_data:
                                            # 直接从task_data提取资源
                                            logger.info("直接从task_data提取资源信息")
                                            # 提取song_url
                                            if not song_url:
                                                for field in potential_url_fields:
                                                    if task_data.get(field):
                                                        song_url = task_data.get(field)
                                                        logger.info(f"从task_data直接获取到URL: {song_url}")
                                                        break
                                            # 提取image_url
                                            image_url = task_data.get("image_url") or task_data.get("cover_url") or task_data.get("thumbnail_url")
                                            # 提取lyrics（prompt字段包含歌词）
                                            lyrics = task_data.get("prompt") or task_data.get("lyrics") or task_data.get("text") or task_data.get("content")
                                            # 提取title
                                            title = task_data.get("title") or task_data.get("name") or task_data.get("display_name")
                                            # 提取author
                                            author = task_data.get("handle") or task_data.get("display_name") or task_data.get("author")
                                            # 提取clip_id
                                            if not clip_id:
                                                clip_id = task_data.get("id") or task_data.get("clip_id") or task_data.get("clipId")
                                        else:
                                            # 处理results、clips或data列表中的资源
                                            # 检查多种可能的列表字段名
                                            resource_list = task_data.get("data", []) or task_data.get("results", []) or task_data.get("clips", [])
                                            if isinstance(resource_list, list) and resource_list:
                                                # 获取第一个结果项
                                                result_item = resource_list[0]
                                                if isinstance(result_item, dict):
                                                    logger.info(f"从data列表提取资源信息")
                                                    # 提取image_url
                                                    image_url = result_item.get("image_url") or result_item.get("cover_url") or result_item.get("thumbnail_url")
                                                    # 提取lyrics（prompt字段包含歌词）
                                                    lyrics = result_item.get("prompt") or result_item.get("lyrics") or result_item.get("text") or result_item.get("content")
                                                    # 提取title
                                                    title = result_item.get("title") or result_item.get("name") or result_item.get("display_name")
                                                    # 提取author
                                                    author = result_item.get("handle") or result_item.get("display_name") or result_item.get("author")
                                                    # 如果song_url为空，尝试从结果项获取
                                                    if not song_url:
                                                        for field in potential_url_fields:
                                                            if result_item.get(field):
                                                                song_url = result_item.get(field)
                                                                logger.info(f"从列表项获取到URL: {song_url}")
                                                                break
                                                    # 如果clip_id为空，尝试从结果项获取
                                                    if not clip_id:
                                                        clip_id = result_item.get("id") or result_item.get("clip_id") or result_item.get("clipId")
                                            else:
                                                # 从嵌套结构提取
                                                logger.info("从嵌套结构提取资源信息")
                                                # 直接从task_data提取
                                                if not image_url:
                                                    image_url = task_data.get("image_url") or task_data.get("cover_url") or task_data.get("thumbnail_url")
                                                if not lyrics:
                                                    lyrics = task_data.get("prompt") or task_data.get("lyrics") or task_data.get("text") or task_data.get("content")
                                                if not title:
                                                    title = task_data.get("title") or task_data.get("name") or task_data.get("display_name")
                                                if not author:
                                                    author = task_data.get("handle") or task_data.get("display_name") or task_data.get("author")
                                                if not clip_id:
                                                    clip_id = task_data.get("id") or task_data.get("clip_id") or task_data.get("clipId")
                                                
                                                # 从更深层的嵌套结构提取
                                                if not image_url or not lyrics or not title or not author or not clip_id or not song_url:
                                                    for nested_key in ["clip", "audio", "result", "data"]:
                                                        nested = task_data.get(nested_key, {})
                                                        if isinstance(nested, dict):
                                                            if not image_url:
                                                                image_url = nested.get("image_url") or nested.get("cover_url") or nested.get("thumbnail_url")
                                                            if not lyrics:
                                                                lyrics = nested.get("prompt") or nested.get("lyrics") or nested.get("text") or nested.get("content")
                                                            if not title:
                                                                title = nested.get("title") or nested.get("name") or nested.get("display_name")
                                                            if not author:
                                                                author = nested.get("handle") or nested.get("display_name") or nested.get("author")
                                                            if not clip_id:
                                                                clip_id = nested.get("id") or nested.get("clip_id") or nested.get("clipId")
                                                            if not song_url:
                                                                for field in potential_url_fields:
                                                                    if nested.get(field):
                                                                        song_url = nested.get(field)
                                                                        logger.info(f"从嵌套结构{nested_key}获取到URL: {song_url}")
                                                                        break
                                                            if image_url and lyrics and title and author and clip_id and song_url:
                                                                break
                                    
                                    # 清理URL中的空格和反引号（处理用户提供的响应格式）
                                    if song_url:
                                        song_url = song_url.strip()
                                        if song_url.startswith('`') and song_url.endswith('`'):
                                            song_url = song_url[1:-1]
                                        logger.info(f"清理后的song_url: {song_url}")
                                    if image_url:
                                        image_url = image_url.strip()
                                        if image_url.startswith('`') and image_url.endswith('`'):
                                            image_url = image_url[1:-1]
                                        logger.info(f"清理后的image_url: {image_url}")
                                    
                                    # 记录提取的资源信息
                                    logger.info(f"提取到的资源信息：song_url={song_url}, image_url={image_url}, lyrics={lyrics[:100]}..." if lyrics else f"提取到的资源信息：song_url={song_url}, image_url={image_url}, lyrics=None")
                                    
                                    return {
                                        "success": True,
                                        "data": {
                                            "status": mapped_status,
                                            "progress": 100 if mapped_status == "SUCCESS" else 50,
                                            "song_url": song_url,
                                            "image_url": image_url,
                                            "lyrics": lyrics,
                                            "title": title or (task_data.get("title") if isinstance(task_data, dict) else None),
                                            "author": author,
                                            "clip": clip,
                                            "clip_id": clip_id,
                                            "raw_data": task_data
                                        }
                                    }
                                else:
                                    logger.error(f"获取任务状态失败: {data.get('message')}")
                                    return {"success": False, "error": data.get('message')}
                            else:
                                logger.error(f"获取任务状态失败: 无效的响应格式")
                                return {"success": False, "error": "INVALID_RESPONSE_FORMAT"}
                        except json.JSONDecodeError as e:
                            logger.error(f"解析JSON响应失败: {str(e)}")
                            logger.error(f"响应内容: {response_text}")
                            return {"success": False, "error": "JSON_DECODE_ERROR"}
                    else:
                        logger.error(f"获取任务状态请求失败，状态码: {response.status}")
                        return {"success": False, "error": f"HTTP_{response.status}"}
        except Exception as e:
            logger.error(f"获取任务状态异常: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_wav(self, clip_id: str) -> Optional[Dict[str, Any]]:
        """获取wav文件 - 使用Vector Engine API
        
        Args:
            clip_id: 音频clip ID
            
        Returns:
            Dict: 包含wav文件信息的字典，格式：{"success": bool, "data": str, "error": str}
        """
        # 构建正确的API路径
        url = f"{self.api_base}/suno/act/wav/{clip_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                
                # 发送请求，使用已配置的headers（包含Authorization信息）
                async with session.get(url, headers=self.headers) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        try:
                            # 解析JSON响应
                            data = await response.json()
                            
                            if isinstance(data, dict):
                                code = data.get("code")
                                response_data = data.get("data")
                                message = data.get("message", "")
                                
                                if code == "success":
                                    # 成功响应
                                    return {
                                        "success": True,
                                        "data": response_data,
                                        "message": message
                                    }
                                else:
                                    # 错误响应
                                    logger.error(f"获取wav失败: {message}")
                                    return {
                                        "success": False,
                                        "error": message,
                                        "code": code
                                    }
                            else:
                                # 无效的响应格式
                                logger.error(f"获取wav失败: 无效的响应格式")
                                return {
                                    "success": False,
                                    "error": "无效的响应格式"
                                }
                        except json.JSONDecodeError as e:
                            # JSON解析失败
                            logger.error(f"解析wav响应失败: {str(e)}")
                            logger.error(f"响应内容: {response_text}")
                            return {
                                "success": False,
                                "error": f"JSON解析失败: {str(e)}"
                            }
                    else:
                        # HTTP请求失败
                        logger.error(f"获取wav请求失败，状态码: {response.status}")
                        return {
                            "success": False,
                            "error": f"HTTP请求失败，状态码: {response.status}"
                        }
        except Exception as e:
            # 其他异常
            logger.error(f"获取wav异常: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def generate_lyrics(self, prompt: str, notify_hook: str = "") -> Optional[str]:
        """生成歌词 - 使用Vector Engine API
        
        Args:
            prompt: 歌词提示词（必需）
            notify_hook: 回调地址（可选）
            
        Returns:
            str: 生成的歌词任务ID
        """
        url = f"{self.api_base}/suno/submit/lyrics"
        
        # 确保必填字段
        if not prompt:
            logger.error("生成歌词失败: 缺少必填参数 prompt")
            return None
        
        # 准备API请求参数 - 根据OpenAPI规范
        payload = {
            "prompt": prompt,  # 歌词提示词，必需
        }
        
        # 添加可选参数
        if notify_hook:
            payload["notify_hook"] = notify_hook
            logger.info(f"设置回调通知地址: {notify_hook}")
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                logger.info(f"请求参数: {payload}")
                async with session.post(url, headers=self.headers, json=payload) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if data.get("code") == "success":
                                # 返回task_id
                                return data["data"]
                            else:
                                logger.error(f"生成歌词失败: {data.get('message')}")
                        else:
                            logger.error(f"生成歌词失败: 无效的响应格式")
                    else:
                        logger.error(f"生成歌词请求失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"生成歌词异常: {str(e)}")
        return None
    
    async def download_song(self, song_url: str) -> Optional[bytes]:
        """下载歌曲"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(song_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Cookie": self.cookie
                }) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"下载歌曲失败，状态码: {response.status}")
                        logger.error(f"响应内容: {await response.text()}")
        except Exception as e:
            logger.error(f"下载歌曲异常: {str(e)}")
        return None
    
    async def get_balance(self) -> Optional[Dict[str, Any]]:
        """获取账户余额"""
        # 新API没有明确的余额查询端点，返回默认值
        return {
            "balance": "无限",
            "expire_at": "永久"
        }
    
    async def get_history(self, limit: int = 20) -> Optional[List[Dict[str, Any]]]:
        """获取历史生成记录"""
        # 新API没有明确的历史记录端点，返回空列表
        return []
    
    async def request_upload_authorization(self) -> Optional[Dict[str, Any]]:
        """请求上传授权 - 第1步
        
        Returns:
            Dict: 包含upload_id和upload_url的字典
        """
        url = f"{self.api_base}/suno/uploads/audio"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                async with session.post(url, headers=self.headers) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if data.get("code") == "success":
                                return data["data"]
                            else:
                                logger.error(f"请求上传授权失败: {data.get('message')}")
                        else:
                            logger.error(f"请求上传授权失败: 无效的响应格式")
                    else:
                        logger.error(f"请求上传授权失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"请求上传授权异常: {str(e)}")
        return None
    
    async def report_upload_finish(self, upload_id: str, upload_type: str = "file_upload", upload_filename: str = "audio.mp3") -> bool:
        """报告上传完毕 - 第3步
        
        Args:
            upload_id: 上传ID
            upload_type: 上传类型，默认file_upload
            upload_filename: 上传的文件名称
            
        Returns:
            bool: 是否成功
        """
        url = f"{self.api_base}/suno/uploads/audio/{upload_id}/upload-finish"
        
        payload = {
            "upload_type": upload_type,
            "upload_filename": upload_filename
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                async with session.post(url, headers=self.headers, json=payload) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        return True
                    else:
                        logger.error(f"报告上传完毕失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"报告上传完毕异常: {str(e)}")
        return False
    
    async def get_upload_status(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """查询上传状态 - 第4步
        
        Args:
            upload_id: 上传ID
            
        Returns:
            Dict: 包含上传状态的字典
        """
        url = f"{self.api_base}/suno/uploads/audio/{upload_id}"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                async with session.get(url, headers=self.headers) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if data.get("code") == "success":
                                return data["data"]
                            else:
                                logger.error(f"查询上传状态失败: {data.get('message')}")
                        else:
                            logger.error(f"查询上传状态失败: 无效的响应格式")
                    else:
                        logger.error(f"查询上传状态失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"查询上传状态异常: {str(e)}")
        return None
    
    async def initialize_clip(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """初始化音频clip - 第5步
        
        Args:
            upload_id: 上传ID
            
        Returns:
            Dict: 包含clip_id的字典
        """
        url = f"{self.api_base}/suno/uploads/audio/{upload_id}/initialize-clip"
        
        try:
            async with aiohttp.ClientSession() as session:
                logger.info(f"发送Suno API请求: {url}")
                async with session.post(url, headers=self.headers) as response:
                    logger.info(f"API响应状态码: {response.status}")
                    response_text = await response.text()
                    logger.info(f"API响应内容: {response_text}")
                    
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, dict):
                            if data.get("code") == "success":
                                return data["data"]
                            else:
                                logger.error(f"初始化音频clip失败: {data.get('message')}")
                        else:
                            logger.error(f"初始化音频clip失败: 无效的响应格式")
                    else:
                        logger.error(f"初始化音频clip失败，状态码: {response.status}")
        except Exception as e:
            logger.error(f"初始化音频clip异常: {str(e)}")
        return None


class SunoSingCommand(BaseCommand):
    """Suno AI唱歌命令"""
    command_name: str = "suno_sing"
    command_description: str = "使用Suno AI生成AI歌曲"
    command_pattern: str = r"^(?:#作曲|/suno)\s+(?P<prompt>.+)$|^/suno\s+作曲\s+(?P<prompt2>.+)$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行唱歌命令"""
        # 获取prompt，优先使用prompt，其次使用prompt2
        prompt = self.matched_groups.get("prompt", "").strip()
        if not prompt:
            prompt = self.matched_groups.get("prompt2", "").strip()
        
        if not prompt:
            await self.send_text("请输入歌曲描述，例如：#作曲 一首关于爱情的流行歌曲")
            return True, "缺少歌曲描述", 1
        
        # 获取配置
        api_base = self.get_config("api.api_base", "https://api.vectorengine.ai")
        api_key = self.get_config("api.api_key", "")
        model = self.get_config("api.model", "suno_music")
        default_account = self.get_config("accounts.default_account", "default")
        accounts_list = self.get_config("accounts.accounts_list", "default:")
        
        # 解析账户列表
        accounts = {}
        # 处理配置格式
        cleaned_accounts_list = accounts_list.strip()
        
        # 如果没有竖线分隔符，也没有冒号，假设用户直接输入了Cookie
        if "|" not in cleaned_accounts_list and ":" not in cleaned_accounts_list:
            # 直接将整个内容作为默认账户的Cookie
            accounts["default"] = cleaned_accounts_list
            logger.info("检测到直接输入的Cookie，使用默认账户名")
        else:
            # 使用竖线|作为账户分隔符，因为Cookie本身包含分号;
            for account_entry in cleaned_accounts_list.split("|"):
                if account_entry.strip():
                    parts = account_entry.split(":", 1)
                    if len(parts) == 2:
                        account_name, cookie = parts
                        accounts[account_name.strip()] = cookie.strip()
                    elif len(parts) == 1 and parts[0].strip():
                        # 如果只有一个部分且不为空，假设是直接输入的Cookie
                        accounts["default"] = parts[0].strip()
                        logger.info("检测到直接输入的Cookie，使用默认账户名")
                    else:
                        # 跳过空的配置项
                        logger.warning(f"跳过无效的账户配置: {account_entry}")
        
        # 选择账户
        selected_account = default_account
        selected_cookie = accounts.get(selected_account, "")
        
        # 检查API密钥
        if not api_key:
            await self.send_text("❌ 生成歌曲失败：未配置API密钥")
            await self.send_text("请在配置文件中设置有效的Vector Engine API密钥")
            await self.send_text("配置文件位置：plugins/suno_ai/config.toml")
            return True, "未配置API密钥", 1
        
        # 修复模型名称，确保使用正确的模型
        if model == "suno_music":
            model = "chirp-v4"  # 默认使用最新模型
            logger.info("检测到旧模型名称'suno_music'，已自动切换为'chirp-v4'")
        
        # 创建Suno AI客户端
        suno_client = SunoAIClient(selected_cookie, api_base, api_key)
        
        # 生成歌曲
        # 根据prompt判断生成类型
        music_type = "song"
        if "随机" in prompt:
            music_type = "random"
        elif "纯音乐" in prompt:
            music_type = "pure_music"
        
        task_id = await suno_client.generate_song(prompt, music_type=music_type, model=model)
        if not task_id:
            await self.send_text("❌ 生成歌曲失败，请检查配置或稍后重试")
            await self.send_text("错误详情：请查看日志获取更多信息")
            return True, "生成歌曲失败", 1
        
        # 合并所有状态消息为一条
        status_message = f"🎵 正在生成歌曲：{prompt}...\n"
        status_message += f"🔑 使用账户：{selected_account}\n"
        status_message += f"🌐 使用API：Vector Engine API\n"
        status_message += f"🔄 歌曲生成中，任务ID：{task_id}，请稍候..."
        
        # 发送合并后的状态消息
        await self.send_text(status_message)
        
        max_wait_time = 300  # 最大等待时间5分钟
        start_time = time.time()
        song_url = None
        image_url = None
        lyrics = None
        clip_id = None
        title = None
        author = None
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while time.time() - start_time < max_wait_time:
            await asyncio.sleep(10)  # 每10秒查询一次
            
            task_status = await suno_client.get_task_status(task_id)
            if task_status.get("success"):
                consecutive_errors = 0  # 重置错误计数
                data = task_status.get("data", {})
                status = data.get("status")
                
                if status == "SUCCESS":
                    song_url = data.get("song_url")
                    image_url = data.get("image_url")
                    lyrics = data.get("lyrics")
                    clip_id = data.get("clip_id")
                    title = data.get("title")
                    author = data.get("author")
                    break
                elif status == "FAILED":
                    await self.send_text("歌曲生成失败")
                    return True, "歌曲生成失败", 1
                elif status == "PROCESSING":
                    # 不发送进度消息，只在任务完成时通知用户
                    pass
            else:
                consecutive_errors += 1
                error = task_status.get("error", "未知错误")
                
                if error == "HTML_RESPONSE":
                    await self.send_text("⚠️ API返回了HTML页面，请检查API地址是否正确")
                    await self.send_text("📌 建议尝试不同的API基础地址：")
                    await self.send_text("   1. https://api.vectorengine.ai")
                    await self.send_text("   2. https://api.vectorengine.ai/v1")
                    await self.send_text("   3. https://api.vectorengine.ai/v1/chat/completions")
                    return True, "API地址错误", 1
                elif error == "JSON_DECODE_ERROR":
                    await self.send_text("⚠️ API返回了无效的JSON格式")
                else:
                    await self.send_text(f"⚠️ 获取任务状态失败：{error}")
                
                if consecutive_errors >= max_consecutive_errors:
                    await self.send_text(f"❌ 连续{max_consecutive_errors}次获取任务状态失败，终止轮询")
                    return True, "获取任务状态失败", 1
            
            # 检查是否超时
            if time.time() - start_time >= max_wait_time:
                await self.send_text("歌曲生成超时，请稍后重试")
                return True, "歌曲生成超时", 1
        
        # 下载并发送歌曲、图片封面和歌词
        if song_url:
            song_data = await suno_client.download_song(song_url)
            
            if song_data:
                # 保存到临时文件
                temp_file = f"temp_song_{int(time.time())}.mp3"
                with open(temp_file, "wb") as f:
                    f.write(song_data)
                
                try:
                    # 准备转发消息内容
                    message_content = []
                    
                    # 添加歌曲生成完成消息
                    message_content.append("🎵 歌曲生成完成！\n")
                    
                    # 添加作者信息（如果有）
                    if author:
                        message_content.append(f"👤 作者：{author}\n")
                    
                    # 添加歌曲标题（如果有）
                    if title:
                        message_content.append(f"🎼 标题：{title}\n\n")
                    
                    # 添加歌词（如果有）
                    if lyrics:
                        message_content.append(f"📝 歌词：\n{lyrics}\n\n")
                    
                    # 添加歌曲链接
                    message_content.append(f"🎵 歌曲链接：`{song_url}`")
                    
                    # 合并为完整消息
                    full_message = "".join(message_content)
                    
                    # 下载图片封面（如果有）
                    image_base64 = None
                    if image_url:
                        image_data = await suno_client.download_song(image_url)
                        if image_data:
                            # 将图片转换为base64编码
                            image_base64 = base64.b64encode(image_data).decode('utf-8')
                    
                    # 构造转发消息格式 - 合并文本和图片
                    forward_items = []
                    
                    # 添加文本消息
                    forward_items.append(("text", full_message))
                    
                    # 添加图片消息（如果有）
                    if image_base64:
                        forward_items.append(("image", image_base64))
                    
                    # 构造完整的转发消息
                    forward_messages = [
                        ("123456", "Suno AI", forward_items)
                    ]
                    
                    # 发送转发消息
                    await self.send_forward(forward_messages)
                    logger.info("转发消息发送成功")
                    
                    # 发送MP3文件
                    mp3_sent = False
                    try:
                        # 检查send_file方法是否存在
                        if hasattr(self, 'send_file'):
                            # 直接发送MP3文件
                            logger.info(f"直接发送MP3文件：{temp_file}")
                            await self.send_file(temp_file)
                            mp3_sent = True
                            logger.info("MP3文件发送成功")
                        # 尝试使用send_voice方法发送base64编码的语音
                        elif hasattr(self, 'send_voice'):
                            logger.info("send_file方法不可用，尝试使用send_voice方法发送语音")
                            with open(temp_file, "rb") as f:
                                mp3_data = f.read()
                            await self.send_voice(base64.b64encode(mp3_data).decode('utf-8'))
                            mp3_sent = True
                            logger.info("语音文件发送成功")
                        else:
                            logger.info("send_file和send_voice方法都不可用，回退到发送歌曲链接")
                            await self.send_text(f"🎵 歌曲链接：`{song_url}`")
                    except Exception as e:
                        logger.error(f"发送MP3失败: {str(e)}")
                        # 最终回退到发送歌曲链接
                        await self.send_text(f"🎵 歌曲链接：`{song_url}`")
                finally:
                    # 删除临时文件
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
            else:
                # 下载失败时的整合消息
                error_message = "❌ 下载歌曲失败\n\n"
                if lyrics:
                    error_message += f"📝 歌词：\n{lyrics}\n\n"
                if image_url:
                    error_message += f"🖼️ 歌曲封面链接：{image_url}\n\n"
                if song_url:
                    error_message += f"🎵 歌曲链接：{song_url}"
                
                await self.send_text(error_message)
                return True, "下载歌曲失败", 1
        else:
            # 没有获取到song_url时的整合消息
            no_url_message = f"🎵 歌曲生成完成！任务ID：{task_id}\n\n"
            no_url_message += "⚠️ 未能获取到歌曲下载链接，请稍后查看您的Suno账户或使用任务ID查询\n\n"
            
            if lyrics:
                no_url_message += f"📝 歌词：\n{lyrics}\n\n"
            if image_url:
                no_url_message += f"🖼️ 歌曲封面链接：{image_url}"
            
            await self.send_text(no_url_message)
        
        return True, "歌曲生成完成", 1


class SunoBalanceCommand(BaseCommand):
    """Suno AI账户余额命令"""
    command_name: str = "suno_balance"
    command_description: str = "查看Suno AI账户余额"
    command_pattern: str = r"^/suno余额$|^/suno\s+余额$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行查看账户余额命令"""
        # 获取配置
        api_base = self.get_config("api.api_base", "https://api.vectorengine.ai")
        api_key = self.get_config("api.api_key", "")
        default_account = self.get_config("accounts.default_account", "default")
        accounts_list = self.get_config("accounts.accounts_list", "default:")
        
        # 解析账户列表
        accounts = {}
        # 处理配置格式
        cleaned_accounts_list = accounts_list.strip()
        
        # 如果没有竖线分隔符，也没有冒号，假设用户直接输入了Cookie
        if "|" not in cleaned_accounts_list and ":" not in cleaned_accounts_list:
            # 直接将整个内容作为默认账户的Cookie
            accounts["default"] = cleaned_accounts_list
            logger.info("检测到直接输入的Cookie，使用默认账户名")
        else:
            # 使用竖线|作为账户分隔符，因为Cookie本身包含分号;
            for account_entry in cleaned_accounts_list.split("|"):
                if account_entry.strip():
                    parts = account_entry.split(":", 1)
                    if len(parts) == 2:
                        account_name, cookie = parts
                        accounts[account_name.strip()] = cookie.strip()
                    elif len(parts) == 1 and parts[0].strip():
                        # 如果只有一个部分且不为空，假设是直接输入的Cookie
                        accounts["default"] = parts[0].strip()
                        logger.info("检测到直接输入的Cookie，使用默认账户名")
                    else:
                        # 跳过空的配置项
                        logger.warning(f"跳过无效的账户配置: {account_entry}")
        
        # 显示所有账户的余额
        for account_name, cookie in accounts.items():
            # 创建Suno AI客户端
            suno_client = SunoAIClient(cookie, api_base, api_key)
            
            # 获取账户余额
            balance_data = await suno_client.get_balance()
            if balance_data:
                # 合并账户信息为一条消息
                account_info = f"🔑 账户：{account_name}\n"
                account_info += f"💰 余额：{balance_data.get('balance', '未知')}\n"
                account_info += f"📅 有效期：{balance_data.get('expire_at', '永久')}"
                await self.send_text(account_info)
            else:
                await self.send_text(f"❌ 无法获取账户 {account_name} 的余额")
        
        return True, "查看账户余额完成", 1


class SunoHistoryCommand(BaseCommand):
    """Suno AI历史记录命令"""
    command_name: str = "suno_history"
    command_description: str = "查看Suno AI历史生成记录"
    command_pattern: str = r"^/suno历史$|^/suno\s+历史$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行查看历史记录命令"""
        # 获取配置
        api_base = self.get_config("api.api_base", "https://api.vectorengine.ai")
        api_key = self.get_config("api.api_key", "")
        default_account = self.get_config("accounts.default_account", "default")
        accounts_list = self.get_config("accounts.accounts_list", "default:")
        
        # 解析账户列表
        accounts = {}
        # 处理配置格式
        cleaned_accounts_list = accounts_list.strip()
        
        # 如果没有竖线分隔符，也没有冒号，假设用户直接输入了Cookie
        if "|" not in cleaned_accounts_list and ":" not in cleaned_accounts_list:
            # 直接将整个内容作为默认账户的Cookie
            accounts["default"] = cleaned_accounts_list
            logger.info("检测到直接输入的Cookie，使用默认账户名")
        else:
            # 使用竖线|作为账户分隔符，因为Cookie本身包含分号;
            for account_entry in cleaned_accounts_list.split("|"):
                if account_entry.strip():
                    parts = account_entry.split(":", 1)
                    if len(parts) == 2:
                        account_name, cookie = parts
                        accounts[account_name.strip()] = cookie.strip()
                    elif len(parts) == 1 and parts[0].strip():
                        # 如果只有一个部分且不为空，假设是直接输入的Cookie
                        accounts["default"] = parts[0].strip()
                        logger.info("检测到直接输入的Cookie，使用默认账户名")
                    else:
                        # 跳过空的配置项
                        logger.warning(f"跳过无效的账户配置: {account_entry}")
        
        # 选择账户
        selected_account = default_account
        selected_cookie = accounts.get(selected_account, "")
        
        # 创建Suno AI客户端
        suno_client = SunoAIClient(selected_cookie, api_base, api_key)
        
        # 获取历史记录
        history = await suno_client.get_history(limit=10)
        if history:
            # 合并历史记录为一条消息
            history_info = f"📜 账户 {selected_account} 的历史记录：\n\n"
            for i, record in enumerate(history, 1):
                history_info += f"{i}. {record.get('title', '无标题')}\n"
                history_info += f"   类型：{record.get('music_type', 'song')} | 状态：{record.get('status', 'unknown')} | 生成时间：{record.get('created_at', 'unknown')}\n"
                if record.get('song_url'):
                    history_info += f"   下载链接：{record.get('song_url')}\n"
                history_info += "\n"
            await self.send_text(history_info)
        else:
            await self.send_text(f"❌ 无法获取账户 {selected_account} 的历史记录")
        
        return True, "查看历史记录完成", 1


class SunoLyricsCommand(BaseCommand):
    """Suno AI生成歌词命令"""
    command_name: str = "suno_lyrics"
    command_description: str = "使用Suno AI生成歌词"
    command_pattern: str = r"^(?:#写词|/suno_lyrics)\s+(?P<prompt>.+)$|^/suno\s+写词\s+(?P<prompt2>.+)$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行生成歌词命令"""
        # 获取prompt，优先使用prompt，其次使用prompt2
        prompt = self.matched_groups.get("prompt", "").strip()
        if not prompt:
            prompt = self.matched_groups.get("prompt2", "").strip()
        
        if not prompt:
            await self.send_text("请输入歌词描述，例如：#写词 一首关于爱情的流行歌曲歌词")
            return True, "缺少歌词描述", 1
        
        # 获取配置
        api_base = self.get_config("api.api_base", "https://api.vectorengine.ai")
        api_key = self.get_config("api.api_key", "")
        default_account = self.get_config("accounts.default_account", "default")
        accounts_list = self.get_config("accounts.accounts_list", "default:")
        
        # 解析账户列表
        accounts = {}
        # 处理配置格式
        cleaned_accounts_list = accounts_list.strip()
        
        # 如果没有竖线分隔符，也没有冒号，假设用户直接输入了Cookie
        if "|" not in cleaned_accounts_list and ":" not in cleaned_accounts_list:
            # 直接将整个内容作为默认账户的Cookie
            accounts["default"] = cleaned_accounts_list
            logger.info("检测到直接输入的Cookie，使用默认账户名")
        else:
            # 使用竖线|作为账户分隔符，因为Cookie本身包含分号;
            for account_entry in cleaned_accounts_list.split("|"):
                if account_entry.strip():
                    parts = account_entry.split(":", 1)
                    if len(parts) == 2:
                        account_name, cookie = parts
                        accounts[account_name.strip()] = cookie.strip()
                    elif len(parts) == 1 and parts[0].strip():
                        # 如果只有一个部分且不为空，假设是直接输入的Cookie
                        accounts["default"] = parts[0].strip()
                        logger.info("检测到直接输入的Cookie，使用默认账户名")
                    else:
                        # 跳过空的配置项
                        logger.warning(f"跳过无效的账户配置: {account_entry}")
        
        # 选择账户
        selected_account = default_account
        selected_cookie = accounts.get(selected_account, "")
        
        # 检查API密钥
        if not api_key:
            await self.send_text("❌ 生成歌词失败：未配置API密钥")
            await self.send_text("请在配置文件中设置有效的Vector Engine API密钥")
            await self.send_text("配置文件位置：plugins/suno_ai/config.toml")
            return True, "未配置API密钥", 1
        
        # 创建Suno AI客户端
        suno_client = SunoAIClient(selected_cookie, api_base, api_key)
        
        try:
            # 生成歌词
            task_id = await suno_client.generate_lyrics(prompt)
            if not task_id:
                await self.send_text("❌ 生成歌词失败，请检查配置或稍后重试")
                await self.send_text("错误详情：请查看日志获取更多信息")
                return True, "生成歌词失败", 1
            
            # 合并所有状态消息为一条
            status_message = f"✍️ 正在生成歌词：{prompt}...\n"
            status_message += f"🔑 使用账户：{selected_account}\n"
            status_message += f"🌐 使用API：Vector Engine API\n"
            status_message += f"🔄 歌词生成中，任务ID：{task_id}，请稍候..."
            
            # 发送合并后的状态消息
            await self.send_text(status_message)
            
            # 轮询任务状态
            max_wait_time = 120  # 最大等待时间2分钟
            start_time = time.time()
            lyrics_url = None
            consecutive_errors = 0
            max_consecutive_errors = 3
            
            while time.time() - start_time < max_wait_time:
                await asyncio.sleep(5)  # 每5秒查询一次
                
                task_status = await suno_client.get_task_status(task_id)
                if task_status.get("success"):
                    consecutive_errors = 0  # 重置错误计数
                    data = task_status.get("data", {})
                    status = data.get("status")
                    
                    if status == "SUCCESS":
                        lyrics_url = data.get("lyrics_url")
                        if lyrics_url:
                            await self.send_text(f"📝 歌词生成完成！下载链接：{lyrics_url}")
                        else:
                            await self.send_text(f"📝 歌词生成完成！任务ID：{task_id}")
                        break
                    elif status == "FAILED":
                        await self.send_text("歌词生成失败")
                        return True, "歌词生成失败", 1
                    elif status == "PROCESSING":
                        progress = data.get("progress", 0)
                        await self.send_text(f"⏳ 歌词生成中，进度：{progress}%")
                else:
                    consecutive_errors += 1
                    error = task_status.get("error", "未知错误")
                    
                    if error == "HTML_RESPONSE":
                        await self.send_text("⚠️ API返回了HTML页面，请检查API地址是否正确")
                        await self.send_text("📌 建议尝试不同的API基础地址：")
                        await self.send_text("   1. https://api.vectorengine.ai")
                        await self.send_text("   2. https://api.vectorengine.ai/v1")
                        await self.send_text("   3. https://api.vectorengine.ai/v1/chat/completions")
                        return True, "API地址错误", 1
                    elif error == "JSON_DECODE_ERROR":
                        await self.send_text("⚠️ API返回了无效的JSON格式")
                    else:
                        await self.send_text(f"⚠️ 获取任务状态失败：{error}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        await self.send_text(f"❌ 连续{max_consecutive_errors}次获取任务状态失败，终止轮询")
                        return True, "获取任务状态失败", 1
                
                # 检查是否超时
                if time.time() - start_time >= max_wait_time:
                    await self.send_text("歌词生成超时，请稍后重试")
                    return True, "歌词生成超时", 1
            
            return True, "歌词生成完成", 1
        except Exception as e:
            logger.error(f"生成歌词异常: {str(e)}")
            await self.send_text(f"❌ 生成歌词过程中发生错误: {str(e)}")
            await self.send_text("请检查日志获取详细信息")
            return True, f"生成歌词异常: {str(e)}", 1


class SunoSwitchAccountCommand(BaseCommand):
    """Suno AI切换账户命令"""
    command_name: str = "suno_switch_account"
    command_description: str = "切换Suno AI默认账户"
    command_pattern: str = r"^/切换账户\s+(?P<account_name>\w+)$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行切换账户命令"""
        account_name = self.matched_groups.get("account_name", "").strip()
        if not account_name:
            await self.send_text("请输入要切换的账户名称")
            return True, "缺少账户名称", 1
        
        # 获取配置
        accounts_list = self.get_config("accounts.accounts_list", "default:")
        
        # 解析账户列表
        accounts = {}
        # 处理配置格式
        cleaned_accounts_list = accounts_list.strip()
        
        # 如果没有竖线分隔符，也没有冒号，假设用户直接输入了Cookie
        if "|" not in cleaned_accounts_list and ":" not in cleaned_accounts_list:
            # 直接将整个内容作为默认账户的Cookie
            accounts["default"] = cleaned_accounts_list
            logger.info("检测到直接输入的Cookie，使用默认账户名")
        else:
            # 使用竖线|作为账户分隔符，因为Cookie本身包含分号;
            for account_entry in cleaned_accounts_list.split("|"):
                if account_entry.strip():
                    parts = account_entry.split(":", 1)
                    if len(parts) == 2:
                        acc_name, cookie = parts
                        accounts[acc_name.strip()] = cookie.strip()
                    elif len(parts) == 1 and parts[0].strip():
                        # 如果只有一个部分且不为空，假设是直接输入的Cookie
                        accounts["default"] = parts[0].strip()
                        logger.info("检测到直接输入的Cookie，使用默认账户名")
                    else:
                        # 跳过空的配置项
                        logger.warning(f"跳过无效的账户配置: {account_entry}")
        
        if account_name not in accounts:
            await self.send_text(f"❌ 账户 {account_name} 不存在")
            return True, "账户不存在", 1
        
        # 这里无法直接修改配置，提示用户手动修改
        await self.send_text(f"✅ 请手动修改配置文件中的default_account为：{account_name}")
        await self.send_text(f"📄 配置文件位置：plugins/suno_ai/config.toml")
        
        return True, "切换账户完成", 1


class SunoHelpCommand(BaseCommand):
    """Suno AI帮助命令"""
    command_name: str = "suno_help"
    command_description: str = "显示Suno AI插件帮助信息"
    command_pattern: str = r"^/suno$"
    
    async def execute(self) -> Tuple[bool, Optional[str], int]:
        """执行帮助命令"""
        # 合并所有帮助信息为一个字符串
        help_message = "🎵 Suno AI插件帮助信息\n"
        help_message += "=" * 30 + "\n"
        help_message += "📋 可用命令：\n"
        help_message += "/suno 或 #作曲 [提示词] - 生成歌曲\n"
        help_message += "/suno 或 #写词 [提示词] - 生成歌词\n"
        help_message += "/suno余额 - 查看账户余额\n"
        help_message += "/suno历史 - 查看历史生成记录\n"
        help_message += "/切换账户 [账户名] - 切换默认账户\n"
        help_message += "/suno - 显示本帮助信息\n"
        help_message += "=" * 30 + "\n"
        help_message += "💡 提示：\n"
        help_message += "- 歌曲生成可能需要几分钟时间，请耐心等待\n"
        help_message += "- 歌词生成通常较快，约30秒左右\n"
        help_message += "- 可以在配置文件中设置多个账户\n"
        help_message += "- 支持多种模型版本，默认使用最新模型"
        
        # 一次性发送所有帮助信息
        await self.send_text(help_message)
        
        return True, "显示帮助信息完成", 1


@register_plugin
class SunoAIPlugin(BasePlugin):
    # 插件基本信息
    plugin_name = "suno_ai"
    plugin_description = "使用Suno AI生成AI歌曲"
    plugin_author = "MaiBot"
    plugin_version = "1.0.0"
    enable_plugin = True
    dependencies: List[str] = []
    python_dependencies: List[str] = []
    config_file_name = "config.toml"
    
    # 配置schema
    config_schema = {
        "api": {
            "api_base": ConfigField(
                description="API基础地址，支持Vector Engine或其他第三方API",
                type="string",
                default="https://api.vectorengine.ai"
            ),
            "api_key": ConfigField(
                description="Vector Engine API密钥",
                type="string",
                default=""
            ),
            "model": ConfigField(
                description="使用的模型名称，支持: chirp-v3-0, chirp-v3-5, chirp-v4, chirp-auk, chirp-v5",
                type="string",
                default="chirp-v4"
            )
        },
        "accounts": {
            "default_account": ConfigField(
                description="默认账户名称",
                type="string",
                default="default"
            ),
            "accounts_list": ConfigField(
                description="账户列表，格式为：账户名:Cookie|账户名2:Cookie2",
                type="string",
                default="default:"
            )
        },
        "features": {
            "random_generate": ConfigField(
                description="是否启用随机生成功能",
                type="boolean",
                default=True
            ),
            "pure_music": ConfigField(
                description="是否启用纯音乐生成功能",
                type="boolean",
                default=True
            ),
            "custom_lyrics": ConfigField(
                description="是否启用自定义歌词生成功能",
                type="boolean",
                default=True
            )
        }
    }
    
    def __init__(self, plugin_dir: str):
        super().__init__(plugin_dir)
        logger.info("SunoAIPlugin 已初始化")
    
    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """获取插件包含的组件列表"""
        return [
            (SunoSingCommand.get_command_info(), SunoSingCommand),
            (SunoBalanceCommand.get_command_info(), SunoBalanceCommand),
            (SunoHistoryCommand.get_command_info(), SunoHistoryCommand),
            (SunoSwitchAccountCommand.get_command_info(), SunoSwitchAccountCommand),
            (SunoLyricsCommand.get_command_info(), SunoLyricsCommand),
            (SunoHelpCommand.get_command_info(), SunoHelpCommand)
        ]
    
    async def on_enable(self):
        """插件启用时执行"""
        logger.info("SunoAIPlugin 已启用")
    
    async def on_disable(self):
        """插件禁用时执行"""
        logger.info("SunoAIPlugin 已禁用")
