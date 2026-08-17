# MCP Integration Roadmap

## What is MCP?
Model Context Protocol (MCP) connects the SelfHealingAgent
to external tools — Slack, GitHub, Jira — enabling
human-in-the-loop approval workflows.

## Current State
SelfHealingAgent asks for terminal approval (input prompt).

## Target State

Test fails, SelfHealingAgent generates fix, MCP sends
Slack notification for approval, GitHub PR opened automatically,
CI runs and confirms green.

## Priority Order
1. Slack connector — approval notifications
2. GitHub connector — auto PR creation
3. Jira connector — ticket creation for failures

## Timeline
Next 2-4 sessions
