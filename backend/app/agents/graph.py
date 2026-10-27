"""LangGraph 主图定义 - 多 Agent 协作流程"""

from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ..models.schemas import TripStatus
from .nodes.poi_agent import poi_search_node
from .nodes.weather_agent import weather_node
from .nodes.hotel_agent import hotel_node
from .nodes.food_agent import food_node
from .nodes.planner_agent import planner_node
from .nodes.human_review import human_review_node


# 定义状态类型
class GraphState(TypedDict):
    """图状态"""
    session_id: str
    city: str
    start_date: str
    end_date: str
    travel_days: int
    transportation: str
    accommodation: str
    preferences: list
    free_text_input: str
    budget: list  # 新增预算字段
    pois: list
    weather: list
    hotels: list
    foods: list  # 新增美食列表
    itinerary: dict
    current_node: str
    status: str
    steps: list
    errors: list
    need_human_review: bool
    human_feedback: str
    human_review_action: str
    user_rejection_feedback: str  # 用户拒绝时的反馈内容
    retry_count: int  # 重新规划次数
    llm_provider: str


# 注：原 route_node 动态路由已移除，改用线性边（见 create_trip_planner_graph）。
# 旧实现按"数据列表是否为空"决定下一节点，某采集节点返回空列表时会反复回到
# 同一节点，直到撞 LangGraph 默认 recursion_limit(25) 报错。线性边让每个节点
# 只执行一次，空数据时顺序前进至 planner，不再死循环。


def human_review_route(state: GraphState) -> Literal["end", "planner"]:
    """
    人工审核路由 - 决定是结束还是重新规划

    Returns:
        end: 用户满意，结束流程
        planner: 用户不满意，重新规划
    """
    feedback = state.get("human_feedback", "")
    action = state.get("human_review_action", "")
    user_rejection_feedback = state.get("user_rejection_feedback", "")

    # 如果有用户拒绝反馈（通过 /feedback 端点设置的），则需要重新规划
    if user_rejection_feedback:
        print("[Human Review] 检测到用户拒绝反馈 → 重新规划")
        return "planner"

    # 默认自动通过（无用户反馈时）
    if action == "reject" or feedback == "reject":
        print("[Human Review] 用户不满意 → 重新规划")
        return "planner"
    else:
        print("[Human Review] 用户满意 → 结束")
        return "end"


def create_trip_planner_graph():
    """
    创建旅行规划图

    图结构（线性）:
    START → poi_search → weather → hotel → food → planner → human_review → END
                                                              → planner (循环重做)
    说明：采用线性边而非按数据缺失动态路由，避免某采集节点返回空列表时
    route 反复回到同一节点导致 Recursion limit 报错。
    """
    # 创建图
    workflow = StateGraph(GraphState)

    # 添加节点
    workflow.add_node("poi_search", poi_search_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("hotel", hotel_node)
    workflow.add_node("food", food_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("human_review", human_review_node)

    # 入口
    workflow.set_entry_point("poi_search")

    # 线性数据采集链（每个节点只执行一次，避免空数据循环）
    workflow.add_edge("poi_search", "weather")
    workflow.add_edge("weather", "hotel")
    workflow.add_edge("hotel", "food")
    workflow.add_edge("food", "planner")

    # planner → human_review
    workflow.add_edge("planner", "human_review")

    # human_review 条件路由（满意或重做）
    workflow.add_conditional_edges(
        "human_review",
        human_review_route,
        {
            "end": END,
            "planner": "planner"
        }
    )

    # 编译图，添加 checkpointer 用于持久化
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# 全局图实例
_graph_instance = None


def get_graph():
    """获取图实例"""
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = create_trip_planner_graph()
    return _graph_instance