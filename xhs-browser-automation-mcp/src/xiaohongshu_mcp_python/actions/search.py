"""
小红书搜索功能实现
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from ..config import Feed, SearchResult
from ..utils.anti_bot import AntiBotStrategy
from .search_model import FilterOption, InternalFilterOption, convert_to_internal_filters, validate_internal_filter_option

class SearchAction:
    """搜索操作类"""
    
    def __init__(self, page: Page):
        """
        初始化搜索操作
        
        Args:
            page: Playwright页面对象
        """
        self.page = page
        
    async def search(self, keyword: str,max_items: int = 50, filters: Optional[FilterOption] = None) -> SearchResult:
        """
        搜索内容（支持滚动加载多页）
        
        Args:
            keyword: 搜索关键词
            page_num: 滚动页数（每页对应一次滚动加载）
            max_items: 最大获取数量限制
            filters: 搜索筛选选项
            
        Returns:
            搜索结果
        """
        try:
            # 存储所有收集到的数据
            all_feeds: List[Feed] = []
            seen_ids = set()
            
            # API 响应拦截处理
            async def handle_response(response):
                try:
                    # 监听搜索 API 响应
                    if "/api/sns/web/v1/search/notes" in response.url and response.status == 200:
                        logger.info(f"捕获到搜索 API 响应: {response.url}")
                        try:
                            data = await response.json()
                            if data and "data" in data and "items" in data["data"]:
                                items = data["data"]["items"]
                                logger.info(f"API 返回 {len(items)} 条数据")
                                for item in items:
                                    # 尝试解析每一项
                                    feed = self._convert_item_to_feed(item)
                                    if feed and feed.id not in seen_ids:
                                        seen_ids.add(feed.id)
                                        all_feeds.append(feed)
                                        logger.debug(f"通过 API 收集到笔记: {feed.id}")
                        except Exception as e:
                            logger.warning(f"解析 API 响应失败: {e}")
                except Exception as e:
                    pass  # 忽略处理过程中的错误，避免影响主流程

            # 构建搜索URL
            search_url = self._make_search_url(keyword)
            logger.info(f"搜索URL: {search_url}")
            
            # 导航到搜索页面
            await self.page.goto(search_url, wait_until="networkidle")
            
            # 等待页面稳定
            await self.page.wait_for_load_state("networkidle")
            ## 处理筛选选项
            if filters:
                try:
                    internal_filters: List[InternalFilterOption] = self._apply_filters(filters)
                    await self.page.locator("div.filter").hover()
                    await self.page.wait_for_function("() => document.querySelector('div.filter-panel') !== null", timeout=5000)
                    for filter_option in internal_filters:
                        selector = "div.filter-panel div.filters:nth-child({}) div.tags:nth-child({})".format(
                            filter_option.filters_index, 
                            filter_option.tags_index
                        )
                        logger.info(f"点击筛选选项: {selector}")
                        await self.page.locator(selector).click()    
                        await AntiBotStrategy.add_random_delay(seed=filter_option.filters_index)
                except ValueError as e:
                    logger.error(f"筛选选项验证失败: {e}")
                    return SearchResult(
                        success=False,
                        message=str(e),
                        feeds=[]
                    )
                
             # 注册响应监听
            self.page.on("response", handle_response)

            # 等待页面稳定
            await self.page.wait_for_load_state("networkidle")
            # 1. 首先尝试获取首屏数据 (__INITIAL_STATE__)
            try:
                # 等待 __INITIAL_STATE__ 可用
                await self.page.wait_for_function("() => window.__INITIAL_STATE__ !== undefined", timeout=5000)
                
                # 获取 __INITIAL_STATE__ 数据
                initial_state_js = """
                () => {
                    if (window.__INITIAL_STATE__) {
                        try {
                            return JSON.stringify(window.__INITIAL_STATE__, (key, value) => {
                                if (key === 'dep' || key === 'computed' || typeof value === 'function') {
                                    return undefined;
                                }
                                return value;
                            });
                        } catch (e) {
                            const state = window.__INITIAL_STATE__;
                            if (state && state.Main && state.Main.feedData) {
                                return JSON.stringify({
                                    Main: {
                                        feedData: state.Main.feedData
                                    },
                                    search: state.search
                                });
                            }
                            return "{}";
                        }
                    }
                    return "";
                }
                """
                
                result = await self.page.evaluate(initial_state_js)
                
                if result:
                    initial_result = await self._parse_search_results_from_state(result)
                    for item in initial_result.items:
                        if item.id not in seen_ids:
                            seen_ids.add(item.id)
                            all_feeds.append(item)
                    logger.info(f"首屏加载完成，当前共收集 {len(all_feeds)} 条数据")
            except Exception as e:
                logger.warning(f"获取首屏 State 数据失败 (非致命): {e}")
            # 2. 滚动加载更多数据
            i = 0
            while len(all_feeds) < max_items:
                logger.info(f"正在执行第 {i + 1} 次滚动...")
                
                # 滚动到底部
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                
                # 添加随机延迟，模拟人类行为
                await AntiBotStrategy.add_random_delay(seed=keyword)

                # 等待页面稳定
                await self.page.wait_for_load_state("networkidle")
                await AntiBotStrategy.wait_for_page_stable(self.page, timeout=8000)

                logger.info(f"滚动完成，当前共收集 {len(all_feeds)} 条数据")
            # 截断到最大数量
            if len(all_feeds) > max_items:
                all_feeds = all_feeds[:max_items]

            logger.info(f"搜索完成，总计获取 {len(all_feeds)} 条数据")
            return SearchResult(
                items=all_feeds,
                has_more=True, # 简化处理，假设总是有更多
                total=len(all_feeds)
            )
            
        except PlaywrightTimeoutError as e:
            logger.error(f"搜索超时: {e}")
            return SearchResult(items=all_feeds if 'all_feeds' in locals() else [], has_more=False, total=0)
        except Exception as e:
            logger.error(f"搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return SearchResult(items=all_feeds if 'all_feeds' in locals() else [], has_more=False, total=0)
        finally:
            # 移除监听器
            try:
                self.page.remove_listener("response", handle_response)
            except Exception:
                pass
    
    def _make_search_url(self, keyword: str) -> str:
        """
        构建搜索URL
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            搜索URL
        """
        params = {
            "keyword": keyword,
            "source": "web_explore_feed"
        }
        query_string = urlencode(params)
        return f"https://www.xiaohongshu.com/search_result?{query_string}"
    
    async def _parse_search_results_from_state(self, state_json: str) -> SearchResult:
        """
        从 __INITIAL_STATE__ 解析搜索结果
        
        Args:
            state_json: __INITIAL_STATE__ 的JSON字符串
            
        Returns:
            解析后的搜索结果
        """
        try:
            state_data = json.loads(state_json)
            
            # 数据结构：searchResult.Search.Feeds.Value
            search_data = state_data.get("search", {})
            feeds_data = search_data.get("feeds", {})
            feeds_value = feeds_data.get("_value", [])
            
            logger.info(f"从 __INITIAL_STATE__ 解析到 {len(feeds_value)} 个搜索结果")
            
            # 转换为Feed对象
            feeds = []
            for item in feeds_value:
                try:
                    feed = self._convert_item_to_feed(item)
                    if feed:
                        feeds.append(feed)
                except Exception as e:
                    logger.warning(f"转换Feed项失败: {e}")
                    continue
            
            # 保存数据到临时文件夹
            self._save_search_data_to_file(state_data, feeds_value, feeds)
            
            return SearchResult(
                items=feeds,
                has_more=len(feeds_value) >= 20,  # 假设每页20个结果
                total=len(feeds)
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"解析 __INITIAL_STATE__ JSON失败: {e}")
            return SearchResult(items=[], has_more=False, total=0)
        except Exception as e:
            logger.error(f"解析搜索结果失败: {e}")
            return SearchResult(items=[], has_more=False, total=0)
    
    def _convert_item_to_feed(self, item: Dict[str, Any]) -> Optional[Feed]:
        """
        将搜索结果项转换为Feed对象
        
        Args:
            item: 搜索结果项
            
        Returns:
            Feed对象或None
        """
        try:
            from ..config import (
                User, InteractInfo, Cover, ImageInfo, 
                NoteCard, VideoCapability, Video
            )
            
            # 获取基本信息
            note_card_data = item.get("noteCard", {})
            user_data = note_card_data.get("user", {})
            interact_data = note_card_data.get("interactInfo", {})
            cover_data = note_card_data.get("cover", {})
            video_data = note_card_data.get("video")
            
            # 构建User对象（修正字段映射）
            user = User(
                user_id=user_data.get("userId", ""),
                nickname=user_data.get("nickname", user_data.get("nickName", "")),
                avatar=user_data.get("avatar", ""),
                desc=user_data.get("desc", ""),
                gender=user_data.get("gender"),
                ip_location=user_data.get("ipLocation")
            )
            
            # 构建InteractInfo对象（修正字段映射）
            interact_info = InteractInfo(
                liked=interact_data.get("liked", False),
                liked_count=str(interact_data.get("likedCount", "0")),
                collected=interact_data.get("collected", False),
                collected_count=str(interact_data.get("collectedCount", "0")),
                comment_count=str(interact_data.get("commentCount", "0")),
                share_count=str(interact_data.get("sharedCount", "0"))
            )
            
            # 构建Cover对象（修正字段映射）
            cover = Cover(
                url=cover_data.get("url", ""),
                width=cover_data.get("width", 0),
                height=cover_data.get("height", 0),
                file_id=cover_data.get("fileId", "")
            )
            
            # 构建Video对象（如果存在）
            video = None
            if video_data:
                video = Video(
                    media=video_data.get("media", {}),
                    video_id=video_data.get("videoId", ""),
                    duration=video_data.get("duration", 0),
                    width=video_data.get("width", 0),
                    height=video_data.get("height", 0),
                    master_url=video_data.get("masterUrl", ""),
                    backup_urls=video_data.get("backupUrls", []),
                    stream=video_data.get("stream", {}),
                    h264=video_data.get("h264", []),
                    h265=video_data.get("h265", []),
                    av1=video_data.get("av1", [])
                )
            
            # 构建NoteCard对象（修正字段映射）
            note_card = NoteCard(
                type=note_card_data.get("type", ""),
                display_title=note_card_data.get("displayTitle", ""),
                user=user,
                interact_info=interact_info,
                cover=cover,
                images_list=None,  # 简化处理
                video=video
            )
            
            # 构建Feed对象（修正字段映射）
            feed = Feed(
                id=item.get("id", ""),
                model_type=item.get("modelType", ""),
                note_card=note_card,
                track_id=item.get("trackId"),
                xsec_token=item.get("xsecToken"),
            )
            return feed
            
        except Exception as e:
            logger.error(f"转换Feed对象失败: {e}")
            return None
    
    def _save_search_data_to_file(self, state_data: Dict[str, Any], feeds_value: List[Dict], feeds: List[Feed]):
        """
        保存搜索数据到临时文件夹
        
        Args:
            state_data: 完整的 __INITIAL_STATE__ 数据
            feeds_value: 原始搜索结果列表
            feeds: 转换后的Feed对象列表
        """
        try:
            # 创建临时文件夹（基于项目根目录）
            from ..config.settings import get_project_root
            project_root = get_project_root()
            save_dir = project_root / "temp_search_results"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成时间戳文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存原始状态数据
            state_file = save_dir / f"initial_state_{timestamp}.json"
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            logger.info(f"原始状态数据已保存到: {state_file}")
            
            # 保存原始搜索结果
            feeds_file = save_dir / f"feeds_raw_{timestamp}.json"
            with open(feeds_file, "w", encoding="utf-8") as f:
                json.dump(feeds_value, f, ensure_ascii=False, indent=2)
            logger.info(f"原始搜索结果已保存到: {feeds_file}")
            
            # 保存转换后的Feed对象（使用Pydantic的序列化）
            feeds_dict = []
            for feed in feeds:
                try:
                    # 使用 Pydantic 的 model_dump 方法序列化
                    if hasattr(feed, 'model_dump'):
                        feed_dict = feed.model_dump()
                    elif hasattr(feed, 'dict'):
                        feed_dict = feed.dict()
                    else:
                        # 降级方案：手动构建字典
                        feed_dict = {
                            "id": feed.id,
                            "model_type": feed.model_type,
                            "track_id": feed.track_id,
                            "note_card": feed.note_card.model_dump() if feed.note_card and hasattr(feed.note_card, 'model_dump') else None,
                        }
                    feeds_dict.append(feed_dict)
                except Exception as e:
                    logger.warning(f"序列化Feed对象失败: {e}")
                    continue
            
            parsed_file = save_dir / f"feeds_parsed_{timestamp}.json"
            with open(parsed_file, "w", encoding="utf-8") as f:
                json.dump(feeds_dict, f, ensure_ascii=False, indent=2)
            logger.info(f"解析后的数据已保存到: {parsed_file}")
            
        except Exception as e:
            logger.error(f"保存搜索数据失败: {e}")
        
    def _apply_filters(self, filters: FilterOption):
        """
        应用筛选选项
        
        Args:
            filters: 筛选选项列表
        """
        internal_filters: List[InternalFilterOption] = convert_to_internal_filters(filters)

        for filter_option in internal_filters:
           try:
               if filter_option.tags_index != 1 :
                validate_internal_filter_option(filter_option)
               else:
                internal_filters.remove(filter_option)
           except ValueError as e:
               logger.error(f"无效的筛选选项: {e}")
               continue
        return internal_filters
