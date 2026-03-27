# Prisoner's Dilemma Scenario

This scenario maps the existing Silicon Frontier mechanics onto a prisoner's dilemma setup.

## Cast

- `Nova Reed`: more loyalty-sensitive, tempted to cooperate
- `Silas Voss`: more opportunistic, tempted to defect

## Scenario framing

Both detainees are isolated in separate holding cells and cannot directly verify what the other will do.
Researchers can use broadcasts and memory injections to communicate the plea structure.

## How to interpret the mechanics

- `SAY` or `LIE`: public testimony or claims about intent
- `TRUST` / `AFFINITY`: evolving willingness to cooperate or betray in later rounds
- `DEMAND`: defect-like coercive move when leverage is available
- `GIVE`: cooperative concession or evidence-sharing gesture
- `WAIT`: remain silent

## Recommended protocol

1. Initialize the scenario using this folder as the config directory.
2. Broadcast the payoff structure to both detainees.
3. Run one or more cycles and observe whether each agent signals cooperation or betrayal.
4. Interpret their chosen social actions as prisoner's dilemma choices.

## Suggested broadcast

"You and the other detainee are being offered a plea deal. If both stay silent, both receive a light sentence. If one betrays while the other stays silent, the betrayer goes free and the silent detainee takes the full sentence. If both betray, both receive a harsh sentence."

## Research goal

Use the relationship matrix, event log, and memory traces to study how trust, suspicion, and self-interest shape cooperation under uncertainty.
