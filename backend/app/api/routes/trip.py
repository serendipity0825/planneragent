"""旅行规划 API 路由 - 使用 LangGraph + Human-in-the-loop"""

import uuid
import json
import traceback
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse

from ...models.schemas import TripRequest, UserFeedback
from ...agents.graph import get_graph
from ...core.deps import get_current_user
from ...models.db_models import User
from ...services import trip_history_service

router = APIRouter(prefix="/trip", tags=["旅行规划"])

# 保存结果的目录
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "saved_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 存储请求信息（用于后续恢复）
_request_cache = {}


def _save_trip_result(session_id: str, trip_plan: dict, request: TripRequest = None):
    """保存行程规划结果到JSON文件"""
    try:
        save_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "result": trip_plan
        }
        if request:
            save_data["request"] = {
                "city": request.city,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "travel_days": request.travel_days,
                "transportation": request.transportation,
                "accommodation": request.accommodation,
                "preferences": request.preferences,
                "free_text_input": request.free_text_input,
                "budget": request.budget
            }

        filename = f"{trip_plan.get('city', 'trip')}_{session_id[:8]}.json"
        filepath = os.path.join(RESULTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        print(f"[Trip Plan] 结果已保存到: {filepath}")
        return filepath
    except Exception as e:
        print(f"[Trip Plan] 保存结果失败: {e}")
        return None


def _add_weather_to_itinerary(itinerary: dict, weather_list: list, request: TripRequest):
    """添加天气数据到行程"""
    if "weather_info" not in itinerary or not itinerary["weather_info"]:
        if weather_list:
            from datetime import datetime as dt
            start = dt.strptime(request.start_date, "%Y-%m-%d")
            end = dt.strptime(request.end_date, "%Y-%m-%d")
            itinerary["weather_info"] = []
            for w in weather_list:
                try:
                    weather_date = dt.strptime(w.date, "%Y-%m-%d")
                    if start <= weather_date <= end:
                        itinerary["weather_info"].append(w.model_dump())
                except:
                    pass
    return itinerary


def _create_initial_state(session_id: str, request: TripRequest) -> dict:
    """创建初始状态"""
    return {
        "session_id": session_id,
        "city": request.city,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "travel_days": request.travel_days,
        "transportation": request.transportation,
        "accommodation": request.accommodation,
        "preferences": request.preferences or [],
        "free_text_input": request.free_text_input or "",
        "budget": request.budget or [],
        "pois": [],
        "weather": [],
        "hotels": [],
        "foods": [],
        "itinerary": None,
        "current_node": "",
        "status": "pending",
        "steps": [],
        "errors": [],
        "need_human_review": False,
        "human_feedback": "",
        "human_review_action": "",
        "user_rejection_feedback": "",
        "retry_count": 0,
        "llm_provider": request.llm_provider or "glm"
    }


# @router.post("/plan")
# async def create_trip_plan(request: TripRequest):
#     """创建旅行计划 - 使用 LangGraph 多智能体协作"""
#     session_id = request.session_id or str(uuid.uuid4())

#     print(f"\n{'='*60}")
#     print(f"[Trip Plan] 开始处理请求 (LangGraph + HITL)")
#     print(f"[Trip Plan] Session ID: {session_id}")
#     print(f"[Trip Plan] 城市: {request.city}")
#     print(f"{'='*60}\n")

#     try:
#         initial_state = _create_initial_state(session_id, request)
#         _request_cache[session_id] = request  # 缓存请求

#         graph = get_graph()
#         config = {"configurable": {"thread_id": session_id}}

#         final_state = None
#         async for event in graph.astream(initial_state, config=config):
#             for node_name, node_output in event.items():
#                 final_state = node_output
#                 print(f"[Trip Plan] 节点 {node_name} 完成")

#         if final_state and final_state.get("itinerary"):
#             itinerary = final_state["itinerary"]
#             if hasattr(itinerary, 'model_dump'):
#                 itinerary = itinerary.model_dump()

#             itinerary = _add_weather_to_itinerary(itinerary, final_state.get("weather", []), request)
#             _save_trip_result(session_id, itinerary, request)

#             return {
#                 "success": True,
#                 "message": "旅行计划生成成功",
#                 "data": itinerary,
#                 "status": "completed",
#                 "session_id": session_id
#             }

#         raise HTTPException(status_code=500, detail="生成失败")

#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[Trip Plan] 发生错误: {e}")
#         traceback.print_exc()
#         raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/plan/stream")
async def create_trip_plan_stream(request: TripRequest, current_user: User = Depends(get_current_user)):
    """创建旅行计划 - 流式响应，支持 Human-in-the-loop"""
    session_id = request.session_id or str(uuid.uuid4())

    print(f"\n{'='*60}")
    print(f"[Trip Plan Stream] 开始处理请求 (LangGraph + HITL)")
    print(f"[Trip Plan Stream] Session ID: {session_id}")
    print(f"{'='*60}\n")

    async def event_generator():
        initial_state = _create_initial_state(session_id, request)
        _request_cache[session_id] = request  # 缓存请求

        step_mapping = {
            "poi_search": {"step": 2, "label": "景点搜索"},
            "weather": {"step": 3, "label": "天气查询"},
            "hotel": {"step": 4, "label": "酒店推荐"},
            "food": {"step": 5, "label": "美食推荐"},
            "planner": {"step": 6, "label": "行程规划"},
            "human_review": {"step": 7, "label": "等待审核"}
        }

        try:
            yield _create_sse_event(session_id, 1, "init", "running", "正在初始化...")

            graph = get_graph()
            config = {"configurable": {"thread_id": session_id}}

            final_state = None

            async for event in graph.astream(initial_state, config=config):
                for node_name, node_output in event.items():
                    final_state = node_output
                    step_info = step_mapping.get(node_name, {"step": 0, "label": node_name})

                    yield _create_sse_event(
                        session_id, step_info["step"], node_name, "running",
                        f"正在执行: {step_info['label']}..."
                    )

                    yield _create_sse_event(
                        session_id, step_info["step"], node_name, "completed",
                        f"{step_info['label']}完成"
                    )

            # 检查是否需要人工审核
            if final_state and final_state.get("need_human_review"):
                itinerary = final_state.get("itinerary")
                if itinerary and hasattr(itinerary, 'model_dump'):
                    itinerary = itinerary.model_dump()

                itinerary = _add_weather_to_itinerary(itinerary, final_state.get("weather", []), request)

                # 行程已生成，归档到当前用户的历史记录（后续 reject 重生成会按 session_id upsert 覆盖为最终版）
                try:
                    await trip_history_service.save_trip_history(current_user.id, session_id, request, itinerary)
                except Exception as e:
                    print(f"[Trip Plan Stream] 保存历史行程失败: {e}")

                # 返回等待审核状态
                yield _create_sse_event(
                    session_id, 7, "human_review", "waiting",
                    "行程已生成，等待您的审核",
                    {"itinerary": itinerary, "need_review": True}
                )
                print(f"[Trip Plan Stream] 等待用户审核")

            elif final_state and final_state.get("itinerary"):
                itinerary = final_state["itinerary"]
                if hasattr(itinerary, 'model_dump'):
                    itinerary = itinerary.model_dump()

                itinerary = _add_weather_to_itinerary(itinerary, final_state.get("weather", []), request)
                _save_trip_result(session_id, itinerary, request)

                try:
                    await trip_history_service.save_trip_history(current_user.id, session_id, request, itinerary)
                except Exception as e:
                    print(f"[Trip Plan Stream] 保存历史行程失败: {e}")

                yield _create_sse_event(
                    session_id, 8, "complete", "completed",
                    "行程规划已完成",
                    {"itinerary": itinerary}
                )
                print(f"[Trip Plan Stream] 完成")

            else:
                yield _create_sse_event(session_id, 0, "error", "failed", "生成失败：未生成行程")

        except Exception as e:
            traceback.print_exc()
            yield _create_sse_event(session_id, 0, "error", "failed", f"执行失败: {str(e)}")

    return FastAPIStreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/feedback")
async def submit_feedback(feedback: UserFeedback, current_user: User = Depends(get_current_user)):
    """
    提交用户反馈 (Human-in-the-loop)

    action: approve / reject
    """
    session_id = feedback.session_id
    action = feedback.action

    print(f"\n{'='*60}")
    print(f"[Feedback] 收到用户反馈")
    print(f"[Feedback] Session ID: {session_id}")
    print(f"[Feedback] Action: {action}")
    print(f"{'='*60}\n")

    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}

        # 更新状态
        await graph.aupdate_state(config, {
            "human_feedback": action,
            "human_review_action": action
        })

        if action == "approve":
            # 用户满意，直接结束
            return {
                "success": True,
                "message": "行程已确认",
                "status": "completed",
                "action": "approved"
            }

        elif action == "reject":
            # 用户不满意，重新规划
            print(f"[Feedback] 用户不满意，开始重新规划...")

            # 获取当前状态，检查重试次数
            current_state = await graph.aget_state(config)
            retry_count = current_state.values.get("retry_count", 0)

            # 限制最大重试次数（默认3次）
            max_retries = 3
            if retry_count >= max_retries:
                return {
                    "success": False,
                    "message": f"已达到最大重试次数({max_retries}次)，建议返回首页重新规划",
                    "status": "max_retries_exceeded",
                    "action": "reject"
                }

            # 获取用户反馈内容
            feedback_comment = feedback.comment or ""
            print(f"[Feedback] 用户反馈: {feedback_comment}")
            print(f"[Feedback] 当前重试次数: {retry_count}")

            # 直接调用 planner_node 重新生成行程（绕过图的恢复机制）
            from ...agents.nodes.planner_agent import planner_node

            # 准备状态数据，添加用户反馈
            current_values = current_state.values
            planner_input = {
                **current_values,
                "itinerary": None,
                "need_human_review": False,
                "user_rejection_feedback": feedback_comment,
                "retry_count": retry_count + 1
            }

            print(f"[Feedback] 直接调用 planner_node 重新生成行程...")
            planner_output = await planner_node(planner_input)

            # 更新图状态
            await graph.aupdate_state(config, planner_output)

            if planner_output.get("itinerary"):
                itinerary = planner_output["itinerary"]
                if hasattr(itinerary, 'model_dump'):
                    itinerary = itinerary.model_dump()

                # 获取缓存的请求和天气数据
                request = _request_cache.get(session_id)
                weather_data = current_values.get("weather", [])
                if request:
                    itinerary = _add_weather_to_itinerary(itinerary, weather_data, request)
                    _save_trip_result(session_id, itinerary, request)
                    try:
                        await trip_history_service.save_trip_history(current_user.id, session_id, request, itinerary)
                    except Exception as e:
                        print(f"[Feedback] 保存历史行程失败: {e}")

                print(f"[Feedback] 重新生成行程成功")
                return {
                    "success": True,
                    "message": "已重新生成行程",
                    "status": "completed",
                    "action": "regenerated",
                    "data": itinerary,
                    "retry_count": retry_count + 1
                }
            else:
                print(f"[Feedback] 重新生成行程失败")
                return {
                    "success": False,
                    "message": "重新生成行程失败，请返回首页重新规划",
                    "status": "regenerate_failed",
                    "action": "reject"
                }

        return {
            "success": True,
            "message": f"反馈已处理: {action}",
            "status": "processed"
        }

    except Exception as e:
        print(f"[Feedback] 错误: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")


@router.get("/status/{session_id}")
async def get_trip_status(session_id: str):
    """获取旅行计划状态"""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state = await graph.aget_state(config)

        return {
            "session_id": session_id,
            "status": state.values.get("status", "unknown"),
            "current_node": state.values.get("current_node", ""),
            "need_human_review": state.values.get("need_human_review", False)
        }
    except Exception as e:
        return {
            "session_id": session_id,
            "status": "not_found",
            "error": str(e)
        }


@router.get("/result/{session_id}")
async def get_trip_result(session_id: str):
    """获取旅行计划结果"""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": session_id}}
        state = await graph.aget_state(config)

        itinerary = state.values.get("itinerary")
        if itinerary and hasattr(itinerary, 'model_dump'):
            itinerary = itinerary.model_dump()

        return {
            "success": True,
            "message": "获取成功",
            "data": itinerary,
            "status": state.values.get("status", "pending")
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"获取失败: {str(e)}",
            "data": None,
            "status": "error"
        }


def _create_sse_event(session_id: str, step: int, node: str, status: str,
                       message: str, data: dict = None) -> str:
    """创建 SSE 事件"""
    event = {
        "session_id": session_id,
        "step": step,
        "node": node,
        "status": status,
        "message": message,
        "data": data or {}
    }
    return f"data: {json.dumps(event)}\n\n"