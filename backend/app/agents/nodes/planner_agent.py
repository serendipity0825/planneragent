"""行程规划 Agent 节点 - 主 Agent"""

import json
from typing import Dict, Any, List, Tuple
from datetime import datetime, timedelta
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from math import radians, sin, cos, sqrt, atan2

from ...core.llm import get_llm
from ...models.schemas import (
    AgentState, AgentStep, NodeType, TripStatus,
    TripPlan, DayPlan, Attraction, Meal, Location, Hotel, Budget
)


# ===========================================
# 距离计算和景点分组工具
# ===========================================

def calculate_distance(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    使用 Haversine 公式计算两个坐标之间的距离（公里）

    Args:
        lon1: 起点经度
        lat1: 起点纬度
        lon2: 终点经度
        lat2: 终点纬度

    Returns:
        距离（公里）
    """
    R = 6371  # 地球半径（公里）

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def group_pois_by_location(pois: list, max_distance_km: float = 5.0) -> List[List]:
    """
    将景点按地理位置分组，同一组内的景点距离不超过 max_distance_km

    使用简单的聚类算法：遍历每个景点，如果与组内已有景点距离都小于阈值，则加入该组

    Args:
        pois: 景点列表
        max_distance_km: 最大距离阈值（公里），默认5公里

    Returns:
        分组后的景点列表
    """
    if not pois:
        return []

    groups = []
    used_indices = set()

    for i, poi in enumerate(pois):
        if i in used_indices:
            continue
        if not poi.location:
            continue

        # 创建新组
        group = [poi]
        used_indices.add(i)

        # 查找附近的其他景点
        for j, other in enumerate(pois):
            if j in used_indices:
                continue
            if not other.location:
                continue

            # 计算与组内已有景点的最小距离
            min_dist_to_group = min(
                calculate_distance(
                    poi.location.longitude, poi.location.latitude,
                    other.location.longitude, other.location.latitude
                )
                for poi in group
            )

            if min_dist_to_group <= max_distance_km:
                group.append(other)
                used_indices.add(j)

        groups.append(group)

    return groups


def get_region_name(avg_lon: float, avg_lat: float, all_pois: list) -> str:
    """
    根据平均坐标判断区域名称

    Args:
        avg_lon: 平均经度
        avg_lat: 平均纬度
        all_pois: 所有景点列表（用于计算相对位置）

    Returns:
        区域名称，如 "市中心东部"、"西北部" 等
    """
    if not all_pois:
        return "市中心"

    # 计算所有景点的中心点
    valid_pois = [p for p in all_pois if p.location]
    if not valid_pois:
        return "市中心"

    center_lon = sum(p.location.longitude for p in valid_pois) / len(valid_pois)
    center_lat = sum(p.location.latitude for p in valid_pois) / len(valid_pois)

    # 判断相对位置
    lon_diff = avg_lon - center_lon
    lat_diff = avg_lat - center_lat

    # 判断东西南北
    directions = []
    if lat_diff > 0.01:
        directions.append("北部")
    elif lat_diff < -0.01:
        directions.append("南部")

    if lon_diff > 0.01:
        directions.append("东部")
    elif lon_diff < -0.01:
        directions.append("西部")

    if not directions:
        return "市中心"

    return "".join(directions)


PLANNER_AGENT_PROMPT = """你是一个专业的旅行规划师。

根据以下信息，生成一份详细的旅行计划。

## 基本信息
- 城市: {city}
- 日期范围: {start_date} 至 {end_date}
- 旅行天数: {travel_days} 天
- 交通方式: {transportation}
- 住宿偏好: {accommodation}
- 用户偏好: {preferences}

## 可用景点 (POI)
{pois_info}

## 天气预报
{weather_info}

## 可用酒店
{hotels_info}

## 推荐美食
{foods_info}

## 用户反馈（⚠️ 重要：如果这是重新规划，必须根据此反馈调整行程！）
{user_feedback}

## 任务要求
1. 从可用景点中选择合适的景点，每天安排 2-3 个
2. 使用景点列表中提供的真实坐标
3. **重要：每天的行程必须不同！**
   - 每天选择不同的景点，不要重复
   - 合理安排路线，减少往返奔波
4. **重要：优化景点路线，减少路程时间！**
   - 每天的景点应该地理位置相近，避免东奔西跑
   - 根据景点的经纬度坐标，计算景点之间的距离
   - 优先选择同一区域或相邻区域的景点
   - 安排合理的游览顺序：从远到近或从近到远
   - 例如：如果上午去景点A（经度116.4, 纬度39.9），下午应该选择附近的景点B，而不是距离很远的景点C
5. **重要：根据天气情况给出穿衣建议！**
   - 根据当天的天气预报（温度、天气状况），给出合适的穿衣建议
   - 如果有雨，提醒用户带伞（need_umbrella = true）
   - 根据温度建议衣物：高温(>30°C)建议轻薄透气、中温(15-30°C)建议舒适休闲、低温(<15°C)建议保暖
   - 根据天气状况建议：晴天注意防晒、阴天舒适出行、雨天注意防滑
6. **重要：为每天安排早餐、午餐、晚餐时，必须从"推荐美食"列表中选择真实餐厅！**
   - 早餐、午餐、晚餐的 name 字段必须是推荐美食列表中的真实餐厅名称
   - 每天选择不同的餐厅
   - 不要使用"早餐"、"午餐"、"晚餐"等通用名称
   - **优先选择靠近当天游览景点或者靠近所住酒店的餐厅**（参考餐厅列表中的距离信息）
   - 午餐应安排在上午游览景点或酒店附近的餐厅
   - 晚餐应安排在下午游览景点或酒店附近的餐厅
7. **重要：从可用酒店列表中选择合适的酒店！**
   - 每天的 hotel 字段必须填写
   - 使用可用酒店列表中的真实酒店名称、地址、评分
   - 如果是多天行程，可以每天推荐同一家酒店
   - 优先选择靠近当天主要游览区域的酒店
8. 生成合理的预算估算
   - 餐厅人均：优先使用"推荐美食"中提供的真实人均消费数据；未提供时按 早餐约30元/午餐约50元/晚餐约80元 估算
   - 酒店每晚价位：高德未提供真实房价，按住宿偏好估值——经济型 150-300元、舒适型 300-600元、豪华型 800-1500元、民宿 200-500元；price_range 填区间文本，estimated_cost 取中位数
   - 景点门票：景点列表未提供票价时，按约 50元/景点 估算
   - 将各项汇总到 budget 字段（景点/酒店/餐饮/交通各项及总计）
9. **重要：如果用户提供了反馈，必须严格按反馈调整行程！**
   - ⚠️ 用户反馈是最高优先级，必须严格执行
   - 如果用户说"不吃XX"，则所有餐食都不能安排XX
   - 如果用户说"不想去XX景点"，则必须更换为其他景点
   - 如果用户不满意某些安排，必须做出实质性改变，不能只是微调
   - 示例：用户反馈"早餐不吃火锅" → 早餐必须换成粥、包子、面条等其他类型

请严格按照以下 JSON 格式输出，不要添加任何其他内容:

{{
  "city": "城市名称",
  "start_date": "开始日期",
  "end_date": "结束日期",
  "days": [
    {{
      "date": "日期",
      "day_index": 0,
      "description": "当日行程描述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {{
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {{"longitude": 0, "latitude": 0}},
        "price_range": "价格范围",
        "rating": "评分",
        "type": "酒店类型",
        "estimated_cost": 300
      }},
      "attractions": [
        {{
          "name": "景点名称",
          "address": "景点地址",
          "location": {{"longitude": 0, "latitude": 0}},
          "visit_duration": 120,
          "description": "景点描述",
          "category": "景点类别",
          "ticket_price": 60
        }}
      ],
      "meals": [
        {{"type": "breakfast", "name": "早餐名称", "description": "描述", "estimated_cost": 30}},
        {{"type": "lunch", "name": "午餐名称", "description": "描述", "estimated_cost": 50}},
        {{"type": "dinner", "name": "晚餐名称", "description": "描述", "estimated_cost": 80}}
      ],
      "weather_advice": "根据天气给出的穿衣建议，如：今天气温较高，建议穿轻薄透气的衣服，注意防晒",
      "need_umbrella": false
    }}
  ],
  "weather_info": [],
  "overall_suggestions": "总体建议",
  "budget": {{
    "total_attractions": 0,
    "total_hotels": 0,
    "total_meals": 0,
    "total_transportation": 0,
    "total": 0
  }}
}}
"""


async def planner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    行程规划节点 - 主 Agent

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    agent_state = AgentState(**state)

    step = AgentStep(
        node=NodeType.PLANNER.value,
        status="running",
        input={
            "pois_count": len(agent_state.pois),
            "weather_count": len(agent_state.weather),
            "hotels_count": len(agent_state.hotels)
        }
    )

    try:
        # 准备上下文信息
        pois_info = _format_pois(agent_state.pois)
        weather_info = _format_weather(agent_state.weather)
        hotels_info = _format_hotels(agent_state.hotels)
        # 美食信息：传入景点和酒店，计算餐厅距离
        foods_info = _format_foods(
            agent_state.foods if hasattr(agent_state, 'foods') else [],
            agent_state.pois,
            agent_state.hotels
        )

        # 获取用户反馈（用于重新规划时调整行程）
        user_feedback = state.get("user_rejection_feedback", "")
        if user_feedback:
            user_feedback_text = f"用户对之前行程不满意，反馈内容：{user_feedback}\n请根据此反馈调整行程安排。"
            print(f"[Planner] ⚠️ 重新规划，用户反馈: {user_feedback}")
            print(f"[Planner] ⚠️ 必须严格按此反馈调整行程！")
        else:
            user_feedback_text = "（首次规划，无用户反馈）"
            print(f"[Planner] 首次规划")

        # 调用 LLM 生成行程
        # 有用户反馈时降低温度，让 LLM 更严格遵循指令
        temperature = 0.3 if user_feedback else 0.7
        print(f"[Planner] LLM temperature: {temperature}")
        llm = get_llm(agent_state.llm_provider, temperature=temperature)

        prompt = ChatPromptTemplate.from_template(PLANNER_AGENT_PROMPT)
        chain = prompt | llm

        response = await chain.ainvoke({
            "city": agent_state.city,
            "start_date": agent_state.start_date,
            "end_date": agent_state.end_date,
            "travel_days": agent_state.travel_days,
            "transportation": agent_state.transportation,
            "accommodation": agent_state.accommodation,
            "preferences": ", ".join(agent_state.preferences) if agent_state.preferences else "无特殊偏好",
            "pois_info": pois_info,
            "weather_info": weather_info,
            "hotels_info": hotels_info,
            "foods_info": foods_info,
            "user_feedback": user_feedback_text
        })

        # 解析 JSON 响应
        trip_plan = _parse_response(response.content, agent_state)

        step.status = "completed"
        step.output = {"plan_generated": True}
        step.duration_ms = 0

        agent_state.itinerary = trip_plan
        agent_state.steps.append(step)
        agent_state.current_node = NodeType.PLANNER.value
        agent_state.status = TripStatus.NEED_CONFIRM  # 需要用户确认
        agent_state.need_human_review = True
        agent_state.updated_at = datetime.now()
        # 清除用户拒绝反馈，防止 human_review_route 再次触发重新规划
        agent_state.user_rejection_feedback = None

        return agent_state.model_dump()

    except Exception as e:
        step.status = "failed"
        step.error = str(e)
        agent_state.errors.append(f"行程规划失败: {str(e)}")
        agent_state.steps.append(step)

        # 尝试生成 fallback 计划
        agent_state.itinerary = _create_fallback_plan(agent_state)
        if agent_state.itinerary:
            agent_state.status = TripStatus.NEED_CONFIRM
            agent_state.need_human_review = True
            # 清除用户拒绝反馈，防止 human_review_route 再次触发重新规划
            agent_state.user_rejection_feedback = None

        return agent_state.model_dump()


def _format_pois(pois: list) -> str:
    """
    格式化 POI 信息，按地理位置分组显示

    将景点按距离分组，同一组内的景点地理位置相近，
    方便 LLM 安排每天的行程时选择同一区域的景点
    """
    if not pois:
        return "暂无景点信息"

    # 按地理位置分组（5公里内的景点归为一组）
    groups = group_pois_by_location(pois, max_distance_km=5.0)

    lines = []
    lines.append("=" * 50)
    lines.append("景点分组说明：同一组内的景点距离较近，建议安排在同一天游览")
    lines.append("=" * 50)
    lines.append("")

    total_count = 0
    for group_idx, group in enumerate(groups, 1):
        # 计算该组的平均坐标
        valid_pois_in_group = [p for p in group if p.location]
        if not valid_pois_in_group:
            continue

        avg_lon = sum(p.location.longitude for p in valid_pois_in_group) / len(valid_pois_in_group)
        avg_lat = sum(p.location.latitude for p in valid_pois_in_group) / len(valid_pois_in_group)

        # 获取区域名称
        region_name = get_region_name(avg_lon, avg_lat, pois)

        lines.append(f"【第{group_idx}组 - {region_name}】")
        lines.append(f"  平均坐标: ({avg_lon:.4f}, {avg_lat:.4f})")
        lines.append(f"  组内景点数: {len(valid_pois_in_group)}个")
        lines.append(f"  建议游览时间: 半天或一天")
        lines.append("")

        # 显示组内景点
        for i, poi in enumerate(valid_pois_in_group, 1):
            total_count += 1
            if total_count > 15:  # 限制总数
                break

            lines.append(f"  {group_idx}-{i}. {poi.name}")
            lines.append(f"      地址: {poi.address}")
            lines.append(f"      坐标: ({poi.location.longitude:.4f}, {poi.location.latitude:.4f})")

            # 计算与组内其他景点的距离
            if len(valid_pois_in_group) > 1:
                distances = []
                for other in valid_pois_in_group:
                    if other.name != poi.name:
                        dist = calculate_distance(
                            poi.location.longitude, poi.location.latitude,
                            other.location.longitude, other.location.latitude
                        )
                        distances.append((other.name, dist))
                if distances:
                    # 显示最近的一个景点
                    nearest = min(distances, key=lambda x: x[1])
                    lines.append(f"      最近景点: {nearest[0]} ({nearest[1]:.1f}公里)")

            if poi.rating:
                lines.append(f"      评分: {poi.rating}")
            lines.append("")

        if total_count > 15:
            break

    # 添加总结信息
    lines.append("-" * 50)
    lines.append(f"共 {len(groups)} 个景点组，{total_count} 个景点")
    lines.append("提示：建议每天安排同一组内的景点，减少路程时间")
    lines.append("-" * 50)

    return "\n".join(lines)


def _format_weather(weather: list) -> str:
    """格式化天气信息"""
    if not weather:
        return "暂无天气信息"

    lines = []
    for w in weather:
        lines.append(f"{w.date}: {w.day_weather} {w.day_temp}°C / {w.night_weather} {w.night_temp}°C")

    return "\n".join(lines)


def _format_hotels(hotels: list) -> str:
    """格式化酒店信息"""
    if not hotels:
        return "暂无酒店信息"

    lines = []
    for i, h in enumerate(hotels[:5], 1):
        lines.append(f"{i}. {h.name} - {h.address}")
        if h.rating:
            lines.append(f"   评分: {h.rating}")

    return "\n".join(lines)


def _format_foods(foods: list, pois: list = None, hotels: list = None) -> str:
    """
    格式化美食推荐信息，按景点/酒店分组显示附近的餐厅

    Args:
        foods: 餐厅列表
        pois: 景点列表
        hotels: 酒店列表

    Returns:
        格式化的美食信息
    """
    if not foods:
        return "暂无美食推荐"

    # 收集参考位置（景点和酒店）
    reference_locations = []

    if pois:
        for poi in pois[:10]:
            if poi.location:
                reference_locations.append({
                    "name": poi.name,
                    "longitude": poi.location.longitude,
                    "latitude": poi.location.latitude,
                    "type": "景点"
                })

    if hotels:
        for hotel in hotels[:5]:
            if hotel.location:
                reference_locations.append({
                    "name": hotel.name,
                    "longitude": hotel.location.longitude,
                    "latitude": hotel.location.latitude,
                    "type": "酒店"
                })

    lines = []
    lines.append("=" * 50)
    lines.append("餐厅推荐（按景点/酒店分组，显示5公里内的餐厅）")
    lines.append("=" * 50)
    lines.append("")

    # 按景点/酒店分组
    for ref in reference_locations:
        lines.append(f"【{ref['name']}({ref['type']})附近的餐厅】")
        lines.append(f"  坐标: ({ref['longitude']:.4f}, {ref['latitude']:.4f})")
        lines.append("")

        # 找出5公里内的餐厅
        nearby_foods = []
        for food in foods:
            if not food.location:
                continue

            dist = calculate_distance(
                food.location.longitude, food.location.latitude,
                ref["longitude"], ref["latitude"]
            )

            if dist <= 5.0:  # 5公里内
                nearby_foods.append((food, dist))

        # 按距离排序
        nearby_foods.sort(key=lambda x: x[1])

        if nearby_foods:
            for food, dist in nearby_foods[:3]:  # 每个景点最多显示3家餐厅
                lines.append(f"  - {food.name}")
                lines.append(f"    地址: {food.address}")
                lines.append(f"    距离: {dist:.1f}公里")
                if food.rating:
                    lines.append(f"    评分: {food.rating}")
                if food.cost:
                    lines.append(f"    人均消费: {int(food.cost)}元")
                lines.append("")
        else:
            lines.append("  暂无5公里内的推荐餐厅")
            lines.append("")

        lines.append("")

    # 添加提示
    lines.append("-" * 50)
    lines.append("提示：根据当天游览的景点，选择该景点附近的餐厅用餐")
    lines.append("-" * 50)

    return "\n".join(lines)


def _parse_response(response: str, state: AgentState) -> TripPlan:
    """解析 LLM 响应"""
    # 提取 JSON
    json_str = response

    if "```json" in response:
        start = response.find("```json") + 7
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()
    elif "```" in response:
        start = response.find("```") + 3
        end = response.find("```", start)
        if end > start:
            json_str = response[start:end].strip()

    # 查找 JSON 对象
    if "{" in json_str:
        start = json_str.find("{")
        brace_count = 0
        end = start
        for i, char in enumerate(json_str[start:], start):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        json_str = json_str[start:end]

    data = json.loads(json_str)

    # 检查并补充缺失的字段
    if "days" in data:
        for day in data["days"]:
            # 确保天气建议字段存在
            if "weather_advice" not in day:
                day["weather_advice"] = ""
                print(f"[Parser] ⚠️ 第{day.get('day_index', 0) + 1}天缺少 weather_advice 字段")
            if "need_umbrella" not in day:
                day["need_umbrella"] = False
                print(f"[Parser] ⚠️ 第{day.get('day_index', 0) + 1}天缺少 need_umbrella 字段")

    print(f"[Parser] 解析成功，共 {len(data.get('days', []))} 天行程")
    return TripPlan(**data)


def _hotel_tier_pricing(accommodation: str) -> Tuple[str, int]:
    """根据住宿偏好估算酒店价位（高德 place API 无真实房价，按档次估值）

    Returns:
        (price_range 文本, estimated_cost 中位数)
    """
    acc = (accommodation or "").strip()
    tiers = [
        ("经济型", "150-300元", 225),
        ("舒适型", "300-600元", 450),
        ("豪华", "800-1500元", 1100),
        ("民宿", "200-500元", 350),
    ]
    for key, pr, ec in tiers:
        if key in acc:
            return pr, ec
    return "300-600元", 450


def _create_fallback_plan(state: AgentState) -> TripPlan:
    """创建 fallback 计划"""
    start_date = datetime.strptime(state.start_date, "%Y-%m-%d")

    # 准备所有可用景点
    all_attractions = []
    for poi in state.pois:
        if poi.location:
            all_attractions.append(Attraction(
                name=poi.name,
                address=poi.address,
                location=poi.location,
                visit_duration=120,
                description=f"{state.city}推荐景点",
                category=poi.category or "景点",
                ticket_price=50
            ))

    # 如果没有景点，使用默认
    if not all_attractions:
        all_attractions = [Attraction(
            name=f"{state.city}市中心景点",
            address=f"{state.city}市中心",
            location=Location(longitude=116.4, latitude=39.9),
            visit_duration=120,
            description="推荐景点",
            category="景点",
            ticket_price=50
        )]

    # 准备所有可用餐厅
    all_foods = []
    if hasattr(state, 'foods') and state.foods:
        for food in state.foods:
            all_foods.append(food)

    # 每天的景点数量
    attractions_per_day = 2
    poi_index = 0
    food_index = 0

    days = []
    for i in range(state.travel_days):
        current_date = start_date + timedelta(days=i)

        # 为这天选择不同的景点
        day_attractions = []
        for j in range(attractions_per_day):
            if poi_index < len(all_attractions):
                day_attractions.append(all_attractions[poi_index])
                poi_index += 1
            else:
                # 如果景点用完了，从头开始但加上不同的描述
                idx = j % len(all_attractions)
                day_attractions.append(Attraction(
                    name=all_attractions[idx].name,
                    address=all_attractions[idx].address,
                    location=all_attractions[idx].location,
                    visit_duration=120,
                    description=f"{state.city}推荐景点",
                    category=all_attractions[idx].category,
                    ticket_price=50
                ))

        # 为这天选择不同的餐厅
        meals = []
        meal_types = ["breakfast", "lunch", "dinner"]
        for j, meal_type in enumerate(meal_types):
            if food_index < len(all_foods):
                food = all_foods[food_index]
                # 优先用高德返回的真实人均，缺失才回退默认（早30/午50/晚70）
                real_cost = getattr(food, "cost", None)
                meal_cost = int(real_cost) if real_cost else (30 + j * 20)
                meals.append(Meal(
                    type=meal_type,
                    name=food.name,
                    description=food.category or "推荐餐厅",
                    estimated_cost=meal_cost
                ))
                food_index += 1
            else:
                # 如果餐厅用完了，使用默认值
                meals.append(Meal(
                    type=meal_type,
                    name=f"当地特色{meal_type}",
                    description="当地特色美食",
                    estimated_cost=30 + j * 20
                ))

        # 选择酒店（使用第一家可用酒店，价位按住宿偏好估值）
        day_hotel = None
        if hasattr(state, 'hotels') and state.hotels:
            hotel = state.hotels[0]
            price_range_str, hotel_cost = _hotel_tier_pricing(state.accommodation)
            day_hotel = Hotel(
                name=hotel.name,
                address=hotel.address,
                location=hotel.location,
                price_range=price_range_str,
                rating=str(hotel.rating) if hotel.rating else "",
                type=hotel.type if hasattr(hotel, 'type') else "酒店",
                estimated_cost=hotel_cost
            )

        days.append(DayPlan(
            date=current_date.strftime("%Y-%m-%d"),
            day_index=i,
            description=f"第{i+1}天 - {state.city}游览",
            transportation=state.transportation,
            accommodation=state.accommodation,
            hotel=day_hotel,
            attractions=day_attractions,
            meals=meals
        ))

    # 汇总预算（基于上面按真实人均/档次估值后的各项费用）
    total_attractions = sum(a.ticket_price for d in days for a in d.attractions)
    total_hotels = sum(d.hotel.estimated_cost for d in days if d.hotel)
    total_meals = sum(m.estimated_cost for d in days for m in d.meals)
    transport_per_day = {"公共交通": 30, "自驾": 100, "步行": 0, "混合": 50}.get(
        state.transportation, 30
    )
    total_transportation = transport_per_day * state.travel_days
    budget = Budget(
        total_attractions=total_attractions,
        total_hotels=total_hotels,
        total_meals=total_meals,
        total_transportation=total_transportation,
        total=total_attractions + total_hotels + total_meals + total_transportation,
    )

    return TripPlan(
        city=state.city,
        start_date=state.start_date,
        end_date=state.end_date,
        days=days,
        weather_info=state.weather,
        overall_suggestions=f"这是{state.city}的{state.travel_days}天旅行计划。",
        budget=budget,
    )
