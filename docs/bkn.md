# Bamboo Knowledge Network

BKN is a lightweight business knowledge network for Bamboo. It keeps business objects and relationships in user-maintained files, then exposes them to the agent through the read-only `bkn_retrieval` tool.

First-stage BKN packages live under:

```text
~/.bamboo/bkn/<network-name>/
  bkn.yaml
  schema/ontology.yaml
  graph/entities.yaml
  graph/relations.yaml
  sources/*.yaml
  operators/*.yaml
  actions/*.yaml
  scripts/*
```

## Minimal Package

`bkn.yaml`:

```yaml
schema_version: 1
name: personal-media
description: Personal content assets across platforms.
enabled: true
entrypoints:
  ontology: schema/ontology.yaml
  entities: graph/entities.yaml
  relations: graph/relations.yaml
retrieval:
  default_limit: 5
  max_hops: 2
```

`schema/ontology.yaml`:

```yaml
classes:
  Content:
    description: Articles, videos, notes, and code examples.
    actions: [republish_content]
  Platform:
    description: Publishing platform.
relations:
  PUBLISHED_ON:
    from: Content
    to: Platform
```

`graph/entities.yaml`:

```yaml
entities:
  - id: content:agent-memory-design
    class: Content
    title: Agent Memory Design Notes
    platform: github

  - id: platform:github
    class: Platform
    name: GitHub
```

`graph/relations.yaml`:

```yaml
relations:
  - from: content:agent-memory-design
    type: PUBLISHED_ON
    to: platform:github
```

## Usage

Ask Bamboo about a business object or platform asset. The agent should call `bkn_retrieval` when the request depends on BKN entities, relationships, local source data, operators, or action metadata.

Example tool arguments:

```json
{
  "query": "Agent Memory GitHub performance",
  "network": "personal-media",
  "limit": 5,
  "max_hops": 2,
  "include_dynamic_data": true,
  "include_actions": true
}
```

## First-Stage Limits

- BKN is read-only.
- Actions are metadata only in the first stage. Later action execution should use BKN-private scripts or workflows under the current platform directory, not the main agent's global Tool/Workflow registry.
- Local files must stay inside the BKN package directory.
- HTTP/API sources, graph SQLite, write tools, and cache are later milestones.
