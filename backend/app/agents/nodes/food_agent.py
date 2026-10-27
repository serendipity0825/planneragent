"""美食推荐 Agent 节点"""

from typing import Dict, Any
from datetime import datetime

from ...services.amap_service import get_amap_service
from ...models.schemas import AgentState, AgentStep, NodeType


async def food_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    美食推荐节点

    简化版：只搜索城市内的餐厅，不做距离筛选
    距离计算和匹配由 planner_agent 处理

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    agent_state = AgentState(**state)

    step = AgentStep(
        node="food",
        status="running",
        input={
            "city": agent_state.city,
            "preferences": agent_state.preferences
        }
    )

    try:
        print(f"\n{'='*60}")
        print(f"[Food Agent] 开始美食推荐")
        print(f"[Food Agent] 城市: {agent_state.city}")

        amap = get_amap_service()

        # 确定搜索关键词
        food_keywords = ["美食", "特色小吃", "餐厅"]

        # 根据用户偏好添加美食类型
        preference_food_map = {
            "美食": ["美食", "特色小吃"],
            "历史文化": ["老字号", "传统菜"],
            "休闲": ["咖啡馆", "茶楼"],
        }

        for pref in agent_state.preferences:
            if pref in preference_food_map:
                food_keywords.extend(preference_food_map[pref])

        food_keywords = list(set(food_keywords))[:3]  # 去重，最多3个
        print(f"[Food Agent] 搜索关键词: {food_keywords}")

        # 搜索餐厅
        all_restaurants = []
        for keyword in food_keywords:
            try:
                restaurants = await amap.search_poi(
                    keywords=keyword,
                    city=agent_state.city,
                    citylimit=True,
                    page_size=10
                )

                # 过滤餐饮类型的POI
                for r in restaurants:
                    category = r.category or ""
                    if any(food_type in category for food_type in ["餐饮", "美食", "餐厅", "小吃", "咖啡", "茶楼"]):
                        all_restaurants.append(r)

            except Exception as e:
                print(f"[Food Agent] 搜索 {keyword} 失败: {e}")

        # 去重
        seen = set()
        unique_restaurants = []
        for restaurant in all_restaurants:
            if restaurant.name not in seen:
                seen.add(restaurant.name)
                unique_restaurants.append(restaurant)

        # 限制数量
        final_restaurants = unique_restaurants[:20]

        # 更新状态
        step.status = "completed"
        step.output = {
            "restaurants_count": len(final_restaurants),
            "keywords_used": food_keywords
        }

        agent_state.foods = final_restaurants
        agent_state.steps.append(step)
        agent_state.current_node = "food"
        agent_state.updated_at = datetime.now()

        print(f"[Food Agent] 推荐餐厅数: {len(final_restaurants)}")
        print(f"{'='*60}\n")

        return agent_state.model_dump()

    except Exception as e:
        step.status = "failed"
        step.error = str(e)
        agent_state.errors.append(f"美食推荐失败: {str(e)}")
        agent_state.steps.append(step)

        print(f"[Food Agent] 错误: {e}")
        return agent_state.model_dump()