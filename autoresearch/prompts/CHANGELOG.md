# Prompt changelog

Prompts evolve in two ways. Each generation, the orchestrator appends one
"Lessons" line (from the measurement report) to the workload and policy agent
prompts; those appends are listed here by generation. Structural rewrites bump
the prompt version in its title and get their own commit.

- v1 (before gen 1): workload_agent.md, policy_agent.md, measurement_agent.md
  written; difficulty ladder, policy contract, report template.
- v1.1 (gen 0): all three prompts now say to reply with text instead of writing
  files (subagents may not write report files; the orchestrator saves outputs).
- gen 0 lessons: workload_agent +"make latency-critical requests compete with each
  other (different deadlines or service times, bursts, or a LOW kind)";
  policy_agent +"the remaining short tail is not queue wait: order HIGH by deadline
  or service hint, or propose a hook against waiting behind a running long request".
