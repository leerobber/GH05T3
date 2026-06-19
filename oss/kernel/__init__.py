"""Civilization Kernel — self-running, self-funding AI organism."""
from oss.kernel.agents import AgentRole, AgentStage, list_agents
from oss.kernel.schemas import HeartbeatPhase, Pillar
from oss.kernel.shards import ShardType, list_shards
from oss.kernel.state_machines import GlobalCycleState, fsm_spec
from oss.kernel.training_schedule import GlobalPhase, schedule_overview

__all__ = [
    "kernel_status", "tick", "Pillar", "HeartbeatPhase",
    "AgentRole", "AgentStage", "ShardType", "GlobalPhase", "GlobalCycleState",
    "list_agents", "list_shards", "schedule_overview",
    "collaboration_overview", "run_collaboration_loop",
    "fsm_spec", "orchestrator_step", "orchestrator_status",
]


def __getattr__(name: str):
    if name in ("kernel_status", "tick"):
        from oss.kernel.heartbeat import kernel_status, tick
        return kernel_status if name == "kernel_status" else tick
    if name in ("orchestrator_step", "orchestrator_status"):
        from oss.kernel.orchestrator import orchestrator_step, orchestrator_status
        return orchestrator_step if name == "orchestrator_step" else orchestrator_status
    if name in ("collaboration_overview", "run_collaboration_loop"):
        from oss.kernel.collaboration import collaboration_overview, run_collaboration_loop
        return collaboration_overview if name == "collaboration_overview" else run_collaboration_loop
    raise AttributeError(name)