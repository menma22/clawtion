---
name: clawtion-search
description: |
  User has a personal knowledge base in clawtion.
  When the user asks about their own notes, past writings, personal documents,
  or "what do I know about X", "what did I write about Y", "find my note on Z" -
  delegate to the clawtion-knowledge subagent rather than answering from
  general knowledge.
---

# clawtion Knowledge Search

The user has a personal knowledge base managed by clawtion (stored locally
with vector + keyword search capabilities).

## When to invoke clawtion-knowledge subagent

Trigger: any question that references the user's personal knowledge or notes:
- "what did I write about..."
- "find my notes on..."
- "what do I know about..."
- "search my notes for..."
- Reference to past discussions, learnings, or saved information
- Any time the user asks about their own thinking, decisions, or records

## How to invoke

Use the Task tool with subagent_type='clawtion-knowledge'. The subagent will:
1. Search the vault with appropriate strategy
2. Return organized results to you
3. Keep raw search noise out of your context

## What NOT to do

- Do NOT call clawtion MCP tools directly. Always delegate to the subagent.
- Do NOT try to answer from general knowledge if the question is about user's
  personal notes.
- Do NOT bypass the subagent even for "simple" lookups - the context isolation
  matters.
