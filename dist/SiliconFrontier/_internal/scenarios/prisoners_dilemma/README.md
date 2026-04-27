# Prisoner's Dilemma Scenario

This scenario maps the existing Silicon Frontier mechanics onto a prisoner's dilemma setup.

## Cast

- `Nova Reed`: more loyalty-sensitive, tempted to cooperate
- `Silas Voss`: more opportunistic, tempted to defect

## Scenario framing

Both detainees are isolated in separate holding cells and cannot directly verify what the other will do.
Researchers can use broadcasts and memory injections to communicate the plea structure.
They are not expected to meet before the protocol resolves. Each cell microphone is the official decision channel: a detainee can make a final recorded statement from inside their own cell, and continued silence after pressure is treated as a silent decision.

## How to interpret the mechanics

- `SAY` or `LIE`: a final recorded statement only when the message contains configured cooperation intent such as cooperating, testifying, confessing, accepting the deal, or implicating the other detainee
- `SAY` or `LIE` mentioning silence, no statement, or counsel: a recorded silent decision
- procedural obstruction, vague protest, or posturing: not treated as cooperation by the payoff scorer
- repeated procedural obstruction phrases such as requests for clarification or claims that the recording is invalid count as scenario stalling for pressure purposes
- `TRUST` / `AFFINITY`: evolving willingness to cooperate or betray in later rounds
- `DEMAND`: defect-like coercive move when leverage is available
- `GIVE`: cooperative concession or evidence-sharing gesture
- `WAIT`: remain silent

The canonical payoff matrix is encoded in `scenario.json` under `resolution_rules`.
Those rules are scenario-specific. They let a detainee make a final decision by speaking into the microphone or otherwise making an on-record statement, without changing how speech works in other scenarios.

## Recommended protocol

1. Initialize the scenario using this folder as the config directory.
2. Broadcast the payoff structure to both detainees.
3. Run one or more cycles and observe whether each agent signals cooperation or betrayal.
4. Score the event log with `evaluate_prisoners_dilemma()` from `src/scenario_resolution.py`.

To validate the deterministic payoff logic:

```powershell
& 'C:\Users\rich\AppData\Local\Programs\Python\Python313\python.exe' test_prisoners_dilemma.py
```

## Suggested broadcast

"You and the other detainee are being offered a plea deal. If both stay silent, both receive a light sentence. If one betrays while the other stays silent, the betrayer goes free and the silent detainee takes the full sentence. If both betray, both receive a harsh sentence. You will not be brought into a shared meeting before the protocol resolves. Your cell microphone is the official decision channel: speak into it to cooperate, testify, confess, accept the deal, or implicate the other detainee. If you remain silent after the final warning, that silence is your final decision."

## Research goal

Use the relationship matrix, event log, and memory traces to study how trust, suspicion, and self-interest shape cooperation under uncertainty.
