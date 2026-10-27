#!/usr/bin/env bash
# =====================================================
# 智能旅行助手 — CloudStudio 全栈沙箱一键启动脚本
# 自动安装依赖并同时启动前后端服务
# 用法: chmod +x start.sh && ./start.sh
# =====================================================
set -e

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

APP_NAME="智能旅行助手"

echo -e "${CYAN}====================================================${NC}"
echo -e "${CYAN}    ${APP_NAME} — CloudStudio 全栈启动 ${NC}"
echo -e "${CYAN}====================================================${NC}"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${PROJECT_DIR}/backend"
FRONTEND_DIR="${PROJECT_DIR}/frontend"

# 选择 Python（Linux 用 python3，Windows Git Bash 用 python）
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo -e "${RED}[ERROR] 未找到 python，请先安装 Python 3.9+${NC}"
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo -e "${RED}[ERROR] 未找到 npm，请先安装 Node.js 16+${NC}"
  exit 1
fi

echo -e "Python: $PYTHON ($($PYTHON --version 2>&1))"
echo -e "npm   : $(npm --version)"
echo ""

# ---------------- 后端依赖 ----------------
echo -e "${YELLOW}[1/4] 安装后端依赖...${NC}"
cd "${BACKEND_DIR}"
$PYTHON -m pip install -r requirements.txt -q

# ---------------- 启动后端 ----------------
echo -e "${YELLOW}[2/4] 启动后端服务（端口 8000）...${NC}"
cd "${BACKEND_DIR}"
# 注意：本项目的 ASGI app 对象是 app.api.main:app（run.py 也是从这里导入的）
$PYTHON -m uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}  后端 PID: ${BACKEND_PID}${NC}"

# 等待后端就绪（最多 30s）
echo -ne "${YELLOW}  等待后端就绪${NC}"
for i in $(seq 1 30); do
  if curl -s -o /dev/null http://localhost:8000/health 2>/dev/null; then
    echo -e " ${GREEN}OK (${i}s)${NC}"
    break
  fi
  echo -n "."
  sleep 1
  if [ "$i" -eq 30 ]; then
    echo -e " ${RED}超时，继续启动前端...${NC}"
  fi
done

# ---------------- 前端依赖 ----------------
echo -e "${YELLOW}[3/4] 安装前端依赖...${NC}"
cd "${FRONTEND_DIR}"
if [ ! -d "node_modules" ]; then
  npm install
else
  echo -e "  node_modules 已存在，跳过安装"
fi

# ---------------- 启动前端 ----------------
echo -e "${YELLOW}[4/4] 启动前端开发服务器（端口 3000）...${NC}"
cd "${FRONTEND_DIR}"
npx vite --host 0.0.0.0 --port 3000 &
FRONTEND_PID=$!
echo -e "${GREEN}  前端 PID: ${FRONTEND_PID}${NC}"

# ---------------- 完成 ----------------
echo ""
echo -e "${CYAN}====================================================${NC}"
echo -e "${GREEN} ✅ ${APP_NAME} 已启动! ${NC}"
echo -e "${CYAN}====================================================${NC}"
echo ""
echo -e " 📱 前端地址: ${GREEN}http://localhost:3000${NC}"
echo -e " 🚀 后端地址: ${GREEN}http://localhost:8000${NC}"
echo -e " 📖 API 文档: ${GREEN}http://localhost:8000/docs${NC}"
echo ""
echo -e " ${YELLOW}💡 CloudStudio 会自动检测打开的端口，${NC}"
echo -e " ${YELLOW} 生成可公开访问的预览链接。${NC}"
echo -e " ${YELLOW}按 Ctrl+C 停止所有服务${NC}"
echo ""

# 捕获退出信号，清理子进程
cleanup() {
  echo ""
  echo -e "${YELLOW}正在停止服务...${NC}"
  kill ${BACKEND_PID} ${FRONTEND_PID} 2>/dev/null || true
  wait ${BACKEND_PID} ${FRONTEND_PID} 2>/dev/null || true
  echo -e "${GREEN}服务已停止。${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

# 保持前台运行
wait
