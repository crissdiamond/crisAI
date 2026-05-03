# crisAI CLI help

## Core commands

```text
/help
/status
/list servers
/list agents
/history
/clear
/session <name>
/exit
```

## Routing controls

```text
/mode auto
/mode single
/mode pipeline
/mode peer
```

- `/mode auto` clears the mode pin and returns control to the router
- `/mode single`, `/mode pipeline`, and `/mode peer` pin the execution mode

## Agent controls

```text
/agent auto
/agent retrieval_planner
/agent design
/agent review
/agent operations
/agent orchestrator
```

- `/agent auto` clears the agent pin and returns control to the router
- `/agent <agent_id>` pins a single agent

## Review and output controls

```text
/review on
/review off
/verbose on
/verbose off
```

- review is a preference used by routing
- pipeline review runs when the routing decision says it is needed
- verbose controls how much intermediate output is shown

## Reading the chat state

crisAI shows the current session state in chat, including:

- session name
- routing state: `auto` or `pinned:<mode>`
- agent state: `auto` or `pinned:<agent>`
- review preference
- verbose setting

## Reading the router line

You may see output such as:

```text
[router:auto] single • retrieval_planner • review:off • retrieval:on • Prompt primarily asks for finding or inspecting sources.
```

or:

```text
[router:pinned] peer • design_author • review:on • retrieval:on • Mode explicitly set to peer by user.
```

This tells you:
- whether the route was chosen automatically or pinned
- which mode will run
- which agent leads the route
- whether review is needed
- whether retrieval is needed

## Typical usage

Start unpinned when possible:

```text
/status
/list servers
/list agents
```

Then either let the router decide, or pin behaviour when you want tighter control.
