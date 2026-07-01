# test_sentinel.py
# Test the Omni Sentinel pipeline.

from backend.sentinel.sentinel_core import SentinelCore

# Test event
raw_event = {
    "event_type": "agent_spawn",
    "source": "swarm",
    "payload": {"agent_id": "agent_42", "parent_id": "agent_41"},
    "lineage": ["agent_41"],
    "metadata": {"permissions": ["spawn_agent"]},
}

# Process the event
core = SentinelCore()
core.process_event(raw_event)

print("✅ Test event processed successfully!")