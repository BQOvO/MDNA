# main.py 增强版本校验和初始化
import sys
import os

from maa.agent.agent_server import AgentServer
from maa.toolkit import Toolkit

import my_action
import my_reco

# 新增：显式指定 MaaFramework 版本（用于校验）
EXPECTED_MAA_VERSION = "v5.9.2"

def check_maa_version():
    """校验当前加载的 MaaFramework 版本是否匹配"""
    try:
        # 调用 MaaToolkit 的版本接口（需确认实际接口名，参考 MaaFramework 文档）
        actual_version = Toolkit.get_version()  # 示例接口，需替换为真实接口
        if EXPECTED_MAA_VERSION not in actual_version:
            print(f"⚠️ MaaFramework 版本不匹配！预期 {EXPECTED_MAA_VERSION}，实际 {actual_version}")
            # 非发布环境可选择退出，开发环境可提示
            # sys.exit(1)
        else:
            print(f"✅ MaaFramework 版本验证通过：{actual_version}")
    except Exception as e:
        print(f"❌ 版本校验失败：{e}")
        sys.exit(1)

def main():
    
    
    # 显式指定配置目录，确保加载正确的 MaaFramework 资源
    Toolkit.init_option("./")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)
        
    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    print(f"✅ AgentServer 启动成功（socket_id: {socket_id}）")
    AgentServer.join()
    AgentServer.shut_down()

if __name__ == "__main__":
    main()