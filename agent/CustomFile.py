from maa.agent.agent_server import AgentServer
from agent.custom.action.MacroPlayer import MacroPlayer
from agent.custom.action.Count import Count,CountPrint,CountCleanup
from agent.custom.action.Looper import Looper
from agent.custom.action.randomr import randomr
from agent.custom.action.FishFight import FishFight
from agent.custom.action.VoyageClick import VoyageClick
from agent.custom.action.outnoder import Outnoder
from agent.custom.action.Timeout import TimeoutStart,TimeoutReset,CheckTimeout


from agent.custom.sink.aspect_ratio import AspectRatioChecker
from agent.custom.sink.count_cleanup import CountAutoCleanup

from agent.custom.recongition.CheckResolution import CheckResolution


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

@AgentServer.custom_action("CountPrint")
class CountPrint_Cls(CountPrint):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("CheckTimeout")
class CheckTimeout_Cls(CheckTimeout):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("CountCleanup")
class CountCleanup_Cls(CountCleanup):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")