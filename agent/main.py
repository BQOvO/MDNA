import io
import os
import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit
from agent.deploy.deploy import deploy, get_main_py_path
from agent.CustomFile import *

# 导入并注册 sink
from agent.custom.sink.resolution_check import AspectRatioChecker
AgentServer.add_tasker_sink(AspectRatioChecker())

def main():
    socket_id = sys.argv[-1] if len(sys.argv) > 1 else "MAA_AGENT_SOCKET"
    print(f"socket_id: {socket_id}")
    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()

if __name__ == "__main__":
    git_path = get_main_py_path().parent.parent / ".git"
    if git_path.exists():
        print("测试模式,. 不进行部署检查")
        if len(sys.argv) == 1:
            sys.argv.append("MAA_AGENT_SOCKET")
    elif not deploy():
        print("error: 部署检查失败，程序退出")
        sys.exit(1)

    try:
        main()
    except Exception as e:
        print(f"error: 程序运行错误: {e}")
        sys.exit(1)