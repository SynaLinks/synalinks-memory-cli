# Synalinks Memory CLI

**Synalinks Memory** is the knowledge and context layer for AI agents. It lets your agents always have the right context at the right time. Unlike retrieval systems that compound LLM errors at every step, Synalinks uses **logical rules** to derive knowledge from your raw data. Every claim can be traced back to evidence, from raw data to insight, no more lies or hallucinations.

This CLI lets you interact with your Synalinks Memory directly from the terminal — add data, ask questions, and query your knowledge base. It also ships with a built-in **MCP server** so any AI assistant that speaks the [Model Context Protocol](https://modelcontextprotocol.io) can use your knowledge base as tools.

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

## Setup

A **Synalinks API key** is required to authenticate with your knowledge base.

When you create a knowledge base on [app.synalinks.com](https://app.synalinks.com), a **default API key** is generated automatically with read/write access and no predicate restrictions — you can use it right away.

To create a key with granular access, go to **Profile icon** (in the header) > **API Keys** > **Create API Key**.

Then set it in your environment:

```bash
export SYNALINKS_API_KEY="synalinks_..."
```

To make it persistent, add it to your shell profile:

```bash
# bash
echo 'export SYNALINKS_API_KEY="synalinks_..."' >> ~/.bashrc

# zsh
echo 'export SYNALINKS_API_KEY="synalinks_..."' >> ~/.zshrc
```

## CLI Usage

### Add a file

```bash
synalinks-memory-cli add data/sales.csv
synalinks-memory-cli add data/events.parquet --name Events --description "Event log" --overwrite
```

### Chat with the agent (while learning concepts and rules)

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

### Insert a row

```bash
synalinks-memory-cli insert Users '{"name": "Alice", "email": "alice@example.com"}'
```

### Update rows

```bash
synalinks-memory-cli update Users '{"name": "Alice"}' '{"email": "alice@new.com"}'
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

## MCP Server

The CLI includes a built-in [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server. This lets AI assistants — Claude, Cursor, Windsurf, and others — use your Synalinks Memory knowledge base as tools.

### Start the server

```bash
# stdio (default) — for Claude Desktop, Claude Code, Cursor, Kiro, etc.
synalinks-memory-cli serve

# SSE over HTTP — for Mistral Le Chat and other remote-only clients
synalinks-memory-cli serve --transport sse --port 8000

# Streamable HTTP
synalinks-memory-cli serve --transport streamable-http --port 8000
```

On startup the server sends a health check to wake up the backend (handles cold starts), then exposes the following tools:

| Tool | Description |
|------|-------------|
| `list_predicates()` | List all tables, concepts, and rules |
| `execute(predicate, limit, offset)` | Fetch rows from a table, concept, or rule |
| `search(predicate, keywords, limit, offset)` | Search rows by keywords (fuzzy matching) |
| `upload(file_path, name, description, overwrite)` | Upload a CSV or Parquet file as a new table |
| `insert_row(predicate, row_json)` | Insert a single row into a table |
| `update_rows(predicate, filter_json, values_json)` | Update rows matching a filter with new values |
| `chat(question)` | Chat with the Synalinks agent (multi-turn, context preserved across calls). Send `"/clear"` to reset conversation history. |

### Connect to your AI assistant

Below are copy-paste configurations for every major AI tool that supports MCP. Replace `your-api-key` with your actual Synalinks API key.

---

#### Claude Desktop

Edit your config file:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "type": "stdio",
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

#### Claude Code

Run this command in your project directory:

```bash
claude mcp add synalinks-memory \
  --transport stdio \
  --env SYNALINKS_API_KEY=your-api-key \
  -- uvx synalinks-memory-cli serve
```

Or add a `.mcp.json` file at the root of your project:

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "type": "stdio",
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

#### Cursor

Edit your config file:
- **Global:** `~/.cursor/mcp.json`
- **Project:** `.cursor/mcp.json`

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

#### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

#### Kiro

Edit your config file:
- **Global:** `~/.kiro/settings/mcp.json`
- **Project:** `.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "${SYNALINKS_API_KEY}"
      }
    }
  }
}
```

> Kiro supports `${VAR}` references — set `SYNALINKS_API_KEY` in your system environment and it will be injected automatically.

---

#### Mistral (Le Chat)

Le Chat supports remote MCP connectors only. Start the server in SSE mode:

```bash
SYNALINKS_API_KEY=your-api-key uvx synalinks-memory-cli serve --transport sse --port 8000
```

Then in Le Chat:
1. Open the **Intelligence** menu and click **Connectors**
2. Click **+ Add Connector** and switch to the **Custom MCP Connector** tab
3. Set:
   - **Name:** `synalinks-memory`
   - **Server URL:** `http://localhost:8000/sse`
4. Click **Connect**

---

#### Cline (VS Code extension)

Open Cline's MCP settings panel, then edit `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "synalinks-memory": {
      "command": "uvx",
      "args": ["synalinks-memory-cli", "serve"],
      "env": {
        "SYNALINKS_API_KEY": "your-api-key"
      }
    }
  }
}
```

---

#### Any MCP-compatible client

The server uses the standard stdio transport. Point your client at:

```
command: uvx synalinks-memory-cli serve
env: SYNALINKS_API_KEY=your-api-key
```

## License

Licensed under Apache 2.0. See the [LICENSE](LICENSE) file for full details.
