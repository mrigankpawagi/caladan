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
- gen 1 lessons: workload_agent +"stress what deadline order cannot fix (a LOW kind,
  bursts, or wrong service hints); keep the top load near the headline";
  policy_agent +"order HIGH by earliest deadline; expect about 52 us at best on w2"
  (with its outcome noted).
- v1.2 (between gen 2's workload proposal and its measurement): workload_agent
  learns that bursts are supported (the `burst` field) and gets a burst ladder.
- gen 2 (before the policy proposal): policy_agent's acceptance section adds rule 6,
  other kinds with a deadline may lose at most 1 point of deadline-met.
- gen 2 lessons: workload_agent +"make the LOW rule or inaccurate run-time hints bind";
  policy_agent +"let the run-time hint order HIGH work with a slack guard" (with outcomes).
- gen 2 (after): policy_agent's rule 5 now uses w0's p99 one level below the headline and its sustained throughput when overloaded.
- gen 3 lessons: workload_agent +"size backlogs from measured depth and sent rate" (with the
  client-bug note); policy_agent +"let gets pass urgent queries with slack / stop promoting
  lost queries" (with p4's rejected outcome).
- v1.2 measurement / notes for all (gen 4): prompts describe the new per-kind runqueue-wait columns.
- gen 4 lessons: workload_agent +"check per-kind wait gaps" and policy_agent +"get wait is 43 of 98.5 us" (with p5's outcome, which disproved the report's bound).
- gen 5 lessons: workload_agent +"a too-long hint on the scored kind is a clean lever"; policy_agent +"learn in both directions, lost threads keep their place" with p6's outcome (protect every kind with a deadline).
- gen 6 lessons: workload_agent +"a missing run-time hint is a clean lever" (repaired by p7); policy_agent +"keep hinted kinds at their hint; an unhinted HIGH thread counts about 8 µs" with p7's accepted outcome and the paired confirmation; measurement_agent +"compare runs from one session" (its first lesson).
- gen 7 lessons: workload_agent +"folding a long kind into a short kind's hint value defeats fixed rankings and per-hint learning" (answered by p8); policy_agent +"cap how far a learned length rises above its hint" with p8's accepted outcome; measurement_agent +"report the floor of runqueue wait and the tail outside it".
- gen 8 lessons: workload_agent +"a mixed label hurts most when its long members rank level with its short ones" (answered by p9); policy_agent +"learn per run-time hint and coarse deadline" with p9's paired-confirmed outcome; measurement_agent +"name missing counters as owner requests".
- gen 9 lessons: workload_agent +"state predictions at both top loads" (with p10's outcome); policy_agent +"order capped labels by measurement" with p10's accepted outcome and a note to build offline models; measurement_agent +"compare capped labels' averages and say who trades waiting".
- gen 10 lessons: workload_agent +"size load levels from measured light-load medians" (with p11's outcome); policy_agent +"scale the constants together" with p11's rejected outcome and the warning about ready times that the runtime resets; measurement_agent +"a candidate that matches the champion probably never changed its decisions".
- gen 11 lessons: workload_agent +"a second time scale tests only how a policy chooses its unit" (answered by p12); policy_agent +"read the unit from the median deadline" with p12's accepted outcome and the time-slice finding; measurement_agent +"grep the raw counters when behaviour is unexplained".
- gen 12 lessons: workload_agent +"changing a deadline also shifts urgency order" (with p13's outcome); policy_agent +"take the unit per label or from short-hinted labels" with p13's accepted outcome; measurement_agent +"report remaining rule margins for kinds that keep paying".
- v1.3 workload agent (before gen 13, at the owner's request to keep going and widen the search): coverage requirement (each workload moves a dimension no earlier workload moved: tails, conns, kthreads, antagonist, load), real-workload inspiration with named sources, and proposals chosen by probe.py.
- gen 13 lessons: workload_agent +"fewer cores stretch the tail" with the probe results of the other two proposals and p14's outcome; policy_agent +"urgent long requests passing short ones" with p14's accepted outcome; measurement_agent +"compare at matched load per core, means vs tails".
- gen 14 lessons: workload_agent +"a rare hidden long request hurts only label-trusting policies, in the tail" (with the probe results and p15's outcome); policy_agent +"use runtime-maintained fields such as total_cycles" with p15's accepted outcome; measurement_agent +"tell mechanisms apart by which kinds should move".
