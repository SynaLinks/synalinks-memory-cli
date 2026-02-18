# Synalinks Memory CLI

**Synalinks Memory** is the knowledge and context layer for AI agents. It lets your agents always have the right context at the right time. Unlike retrieval systems that compound LLM errors at every step, Synalinks uses **logical rules** to derive knowledge from your raw data. Every claim can be traced back to evidence, from raw data to insight, no more lies or hallucinations.

This CLI lets you interact with your Synalinks Memory directly from the terminal — add data, ask questions, and query your knowledge base.

## Installation

```bash
pip install synalinks-memory-cli
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add synalinks-memory-cli
```

Or run directly without installing using [uvx](https://docs.astral.sh/uv/concepts/tools/):

```bash
uvx synalinks-memory-cli list
uvx synalinks-memory-cli execute Users --format csv -o users.csv
```

## Usage

Set your API key:

```bash
export SYNALINKS_API_KEY="synalinks_..."
```

### Add a file

```bash
synalinks-memory-cli add data/sales.csv
synalinks-memory-cli add data/events.parquet --name Events --description "Event log" --overwrite
```

### Ask a question (while learning concepts and rules)

```bash
synalinks-memory-cli "What were the top 5 products by revenue last month?"
synalinks-memory-cli How are sales doing this quarter
```

### List predicates

```bash
synalinks-memory-cli list
```

### Execute a predicate

```bash
synalinks-memory-cli execute Users
synalinks-memory-cli execute Users --limit 50 --offset 10
```

### Search

```bash
synalinks-memory-cli search Users "alice"
```

### Export data as a file

```bash
synalinks-memory-cli execute Users --format csv
synalinks-memory-cli execute Users --format parquet -o users.parquet
synalinks-memory-cli execute Users -f json --limit 500
```

### Options

```
--api-key TEXT   API key (or set SYNALINKS_API_KEY)
--base-url TEXT  Override API base URL
--help           Show help message
```

## License

Licensed under Apache 2.0. See the [LICENSE](LICENSE) file for full details.