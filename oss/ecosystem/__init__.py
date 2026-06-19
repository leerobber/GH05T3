"""OSS Ecosystem — species-level FSMs for Omni-Mind + Omni-Economy superorganism."""

__all__ = [
    "OssSpeciesState",
    "ecosystem_fsm_spec",
    "ecosystem_step",
    "ecosystem_status",
    "oss_bootstrap_plan",
]


def __getattr__(name: str):
    if name == "OssSpeciesState":
        from oss.ecosystem.fsm import OssSpeciesState
        return OssSpeciesState
    if name == "ecosystem_fsm_spec":
        from oss.ecosystem.fsm import ecosystem_fsm_spec
        return ecosystem_fsm_spec
    if name == "ecosystem_step":
        from oss.ecosystem.orchestrator import ecosystem_step
        return ecosystem_step
    if name == "ecosystem_status":
        from oss.ecosystem.orchestrator import ecosystem_status
        return ecosystem_status
    if name == "oss_bootstrap_plan":
        from oss.ecosystem.bootstrap import oss_bootstrap_plan
        return oss_bootstrap_plan
    raise AttributeError(name)