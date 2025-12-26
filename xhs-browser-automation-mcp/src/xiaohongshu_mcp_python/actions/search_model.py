from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# 定义筛选选项的字面量类型，用于类型检查和文档
# Define literals for filter options for type checking and documentation
SortByType = Literal["综合", "最新", "最多点赞", "最多评论", "最多收藏"]
NoteTypeType = Literal["不限", "视频", "图文"]
PublishTimeType = Literal["不限", "一天内", "一周内", "半年内"]
SearchScopeType = Literal["不限", "已看过", "未看过", "已关注"]
LocationType = Literal["不限", "同城", "附近"]

class FilterOption(BaseModel):

    # @classmethod
    # def from_dict(cls, data: Dict[str, Any]):
    #     return cls(**data)
    """
    筛选选项结构体
    对应 Go 代码中的 FilterOption
    """
    sort_by: Optional[SortByType] = Field(
        default='综合', 
        description="排序依据: 综合|最新|最多点赞|最多评论|最多收藏, 默认为'综合'"
    )
    note_type: Optional[NoteTypeType] = Field(
        default='不限', 
        description="笔记类型: 不限|视频|图文, 默认为'不限'"
    )
    publish_time: Optional[PublishTimeType] = Field(
        default='不限', 
        description="发布时间: 不限|一天内|一周内|半年内, 默认为'不限'"
    )
    search_scope: Optional[SearchScopeType] = Field(
        default='不限', 
        description="搜索范围: 不限|已看过|未看过|已关注, 默认为'不限'"
    )
    location: Optional[LocationType] = Field(
        default='不限', 
        description="位置距离: 不限|同城|附近, 默认为'不限'"
    )

class SearchFeedsArgs(BaseModel):
    """
    搜索内容的参数
    对应 Go 代码中的 SearchFeedsArgs
    """
    keyword: str = Field(..., description="搜索关键词")
    filters: Optional[FilterOption] = Field(
        default_factory=FilterOption, 
        description="筛选选项"
    )

class InternalFilterOption(BaseModel):
    """
    内部使用的筛选选项(基于索引)
    对应 Go 代码中的 internalFilterOption
    """
    filters_index: int = Field(..., description="筛选组索引")
    tags_index: int = Field(..., description="标签索引")
    text: str = Field(..., description="标签文本描述")

# 预定义的筛选选项映射表（内部使用）
# 对应 Go 代码中的 filterOptionsMap
FILTER_OPTIONS_MAP: Dict[int, List[InternalFilterOption]] = {
    1: [  # 排序依据
        InternalFilterOption(filters_index=1, tags_index=1, text="综合"),
        InternalFilterOption(filters_index=1, tags_index=2, text="最新"),
        InternalFilterOption(filters_index=1, tags_index=3, text="最多点赞"),
        InternalFilterOption(filters_index=1, tags_index=4, text="最多评论"),
        InternalFilterOption(filters_index=1, tags_index=5, text="最多收藏"),
    ],
    2: [  # 笔记类型
        InternalFilterOption(filters_index=2, tags_index=1, text="不限"),
        InternalFilterOption(filters_index=2, tags_index=2, text="视频"),
        InternalFilterOption(filters_index=2, tags_index=3, text="图文"),
    ],
    3: [  # 发布时间
        InternalFilterOption(filters_index=3, tags_index=1, text="不限"),
        InternalFilterOption(filters_index=3, tags_index=2, text="一天内"),
        InternalFilterOption(filters_index=3, tags_index=3, text="一周内"),
        InternalFilterOption(filters_index=3, tags_index=4, text="半年内"),
    ],
    4: [  # 搜索范围
        InternalFilterOption(filters_index=4, tags_index=1, text="不限"),
        InternalFilterOption(filters_index=4, tags_index=2, text="已看过"),
        InternalFilterOption(filters_index=4, tags_index=3, text="未看过"),
        InternalFilterOption(filters_index=4, tags_index=4, text="已关注"),
    ],
    5: [  # 位置距离
        InternalFilterOption(filters_index=5, tags_index=1, text="不限"),
        InternalFilterOption(filters_index=5, tags_index=2, text="同城"),
        InternalFilterOption(filters_index=5, tags_index=3, text="附近"),
    ],
}

def find_internal_option(filters_index: int, text: str) -> InternalFilterOption:
    """
    根据筛选组索引和文本查找内部筛选选项
    对应 Go 代码中的 findInternalOption
    
    Args:
        filters_index: 筛选组索引
        text: 标签文本描述
        
    Returns:
        InternalFilterOption: 找到的内部筛选选项
        
    Raises:
        ValueError: 如果筛选组不存在或文本未找到
    """
    options = FILTER_OPTIONS_MAP.get(filters_index)
    if options is None:
        # 这里的错误信息解释了为什么查找失败：索引不正确
        raise ValueError(f"筛选组 {filters_index} 不存在")

    for option in options:
        if option.text == text:
            return option

    # 这里的错误信息解释了为什么查找失败：在该组中没有匹配的文本
    raise ValueError(f"在筛选组 {filters_index} 中未找到文本 '{text}'")

def convert_to_internal_filters(filter_option: FilterOption) -> List[InternalFilterOption]:
    """
    将 FilterOption 转换为内部的 internalFilterOption 列表
    对应 Go 代码中的 convertToInternalFilters
    
    为什么需要这个转换：
    前端或调用方传入的是易读的字符串选项（如"最新"），
    但后端或底层搜索接口可能需要特定的数字索引（FiltersIndex, TagsIndex）来执行查询。
    此函数负责将用户友好的字符串映射为系统内部使用的索引结构。
    """
    internal_filters: List[InternalFilterOption] = []

    # 定义映射关系：FilterOption字段名 -> 筛选组索引
    # 使用列表而不是直接硬编码，方便扩展和维护
    mapping = [
        (filter_option.sort_by, 1, "排序依据"),
        (filter_option.note_type, 2, "笔记类型"),
        (filter_option.publish_time, 3, "发布时间"),
        (filter_option.search_scope, 4, "搜索范围"),
        (filter_option.location, 5, "位置距离"),
    ]

    for value, index, name in mapping:
        # 只有当值不为空且不为None时才处理
        # 这样可以支持部分筛选，用户只传关心的筛选条件
        if value:
            try:
                internal = find_internal_option(index, value)
                internal_filters.append(internal)
            except ValueError as e:
                # 捕获查找错误并包装成更具体的错误信息，方便调试
                raise ValueError(f"{name}错误: {e}")

    return internal_filters

def validate_internal_filter_option(filter_opt: InternalFilterOption) -> None:
    """
    验证内部筛选选项是否在有效范围内
    对应 Go 代码中的 validateInternalFilterOption
    
    为什么需要验证：
    确保构造的内部选项是合法的，防止无效索引导致后续搜索逻辑崩溃或产生错误结果。
    """
    # 检查筛选组索引是否有效
    if filter_opt.filters_index < 1 or filter_opt.filters_index > 5:
        raise ValueError(f"无效的筛选组索引 {filter_opt.filters_index}，有效范围为 1-5")

    # 检查标签索引是否在对应筛选组的有效范围内
    options = FILTER_OPTIONS_MAP.get(filter_opt.filters_index)
    if options is None:
        raise ValueError(f"筛选组 {filter_opt.filters_index} 不存在")

    # 获取该组最大的标签索引数
    max_tag_index = len(options)
    
    # 这里的逻辑假设 TagsIndex 是从 1 开始连续的，这符合 map 中的定义
    if filter_opt.tags_index < 1 or filter_opt.tags_index > max_tag_index:
        raise ValueError(
            f"筛选组 {filter_opt.filters_index} 的标签索引 {filter_opt.tags_index} 超出范围，"
            f"有效范围为 1-{max_tag_index}"
        )

# 简单测试代码 (验证逻辑是否正确)
if __name__ == "__main__":
    a = list()
    a.index
    try:
        # 示例：创建一个搜索参数
        args = SearchFeedsArgs(
            keyword="Python学习",
            filters=FilterOption(
                sort_by="最新",
                note_type="视频"
            )
        )
        print(f"搜索参数: {args}")

        # 转换为内部筛选选项
        internal_options = convert_to_internal_filters(args.filters)
        print("\n转换后的内部选项:")
        for opt in internal_options:
            print(opt)
            # 验证每一个选项
            validate_internal_filter_option(opt)
            
        print("\n验证通过！")

    except ValueError as e:
        print(f"\n发生错误: {e}")
