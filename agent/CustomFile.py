from maa.agent.agent_server import AgentServer
from agent.custom.action.MacroPlayer import MacroPlayer
from agent.custom.action.Count import Count
from agent.custom.action.Looper import Looper
from agent.custom.action.randomr import randomr
from agent.custom.action.FishFight import FishFight
from agent.custom.action.VoyageClick import VoyageClick
from agent.custom.action.outnoder import Outnoder
from agent.custom.action.Timeout import TimeoutStart,TimeoutReset

from agent.custom.recongition.CheckResolution import CheckResolution
from agent.custom.recongition.CheckResolution_16_9 import CheckResolution16_9


@AgentServer.custom_action("Count")
class Count_Cls(Count):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")


@AgentServer.custom_recognition("CheckResolution")
class CheckResolution_Cls(CheckResolution):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")


@AgentServer.custom_recognition("CheckResolution_16_9")
class CheckResolution_Cls(CheckResolution16_9):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("MacroPlayer")     # 注册名
class MacroPlayer_Cls(MacroPlayer):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("Looper")
class Looper_Cls(Looper):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("randomr")
class randomr_Cls(randomr):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("FishFight")
class FishFight_Cls(FishFight):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("VoyageClick")
class VoyageClick_Cls(VoyageClick):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("outnoder")
class Outnoder_Cls(Outnoder):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("TimeoutStart")
class TimeoutStart_Cls(TimeoutStart):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("TimeoutReset")
class TimeoutReset_Cls(TimeoutReset):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")