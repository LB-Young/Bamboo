# Bamboo Knowledge Network

BKN is a business knowledge network for Bamboo. It keeps business objects and relationships in user-maintained files and exposes retrieval through `bkn_retrieval`. The current runtime also provides staged ingestion, topology updates, graph export, and permission-controlled private action execution.

This page documents the compatible legacy `bkn.yaml` package format. For current commands and the platform workflow, see the [user guide](user-guide.md#guide-bkn). Platform packages live in `~/.bamboo/bkn/platforms/<platform_id>/` and use `manifest.yaml`, `schema.json`, and graph data. Architecture documents describe both implemented and planned capabilities.

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

## Current Commands and Boundaries

```bash
bamboo bkn list --all
bamboo bkn validate
bamboo bkn index
bamboo bkn search "Agent Memory" --network personal-media --limit 5 --max-hops 2
bamboo bkn export personal-media --format mermaid
```

- Retrieval is read-only; this does not mean the entire BKN subsystem is read-only.
- `bkn_ingest` creates a staged platform draft; `bkn_ingest_submit` submits it into the active platform directory after permission handling.
- `bkn_update_topology` updates nodes and edges and requires evidence.
- `bkn_action_prepare` returns an execution plan without running it. `bkn_action_execute` runs a platform-private script under runtime execution permissions.
- `bkn_export` and the export CLI produce Mermaid, DOT, or Markdown.
- Package-local paths are validated. Supported source and action behavior depends on the package format and implementation; old first-stage milestone lists are not current capability limits.
