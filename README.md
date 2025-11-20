# Agentic Docker

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Docker](https://img.shields.io/badge/docker-required-blue)
![Ollama](https://img.shields.io/badge/ollama-required-orange)

An AI-powered Docker assistant that understands natural language commands. This project demonstrates the use of local Large Language Models (LLMs) via [Ollama](https://ollama.com/) to interpret human-readable instructions and safely execute corresponding Docker operations using the Model Context Protocol (MCP).

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Available Commands](#available-commands)
- [Safety Features](#safety-features)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Natural Language Processing:** Control Docker using plain English (e.g., "Start nginx on port 8080").
- **Local LLM:** Uses Ollama for privacy and offline capability. No external API calls for inference.
- **MCP Protocol:** Implements the Model Context Protocol for secure and standardized tool calling between the LLM and Docker operations.
- **Safety Layer:** Confirmation prompts for potentially destructive operations (e.g., stopping containers).
- **Modular Design:** Easy to extend with new Docker commands by adding new tool classes.
- **Docker SDK:** Safe, programmatic interaction with Docker using the official Python SDK, avoiding raw shell command injection.

## Architecture

```mermaid
graph TD
    User[User] -->|Natural Language Command| CLI[CLI (Typer)]
    CLI -->|Query| Agent[Agent Orchestrator]
    Agent -->|1. Select Tool| LLM[LLM (Ollama)]
    LLM -->|Tool Call JSON| Agent
    Agent -->|2. Safety Check| Safety[Safety Layer]
    Safety -->|Confirmation?| User
    Safety -->|Approved| MCP[MCP Client]
    MCP -->|JSON-RPC| Server[MCP Server]
    Server -->|Execute| Docker[Docker Engine]
    Docker -->|Result| Server
    Server -->|Result| Agent
    Agent -->|Format Result| User
```

## Prerequisites

- **Python 3.9 or higher:** Required for the project's dependencies.
- **Docker Engine:** Must be installed and running on your machine. The user running the script needs permissions to interact with Docker (e.g., be part of the `docker` group on Linux/macOS).
- **Ollama:** Must be installed to run local LLMs. Download from [https://ollama.com/](https://ollama.com/).
- **`phi3:mini` Model:** The system is configured to use the `phi3:mini` model by default. It's a fast, efficient model suitable for this task.

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd agentic-docker
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    # Create the virtual environment
    python -m venv .venv

    # Activate it on Windows (Command Prompt)
    .\.venv\Scripts\activate

    # OR activate it on Windows (PowerShell)
    .\.venv\Scripts\Activate.ps1

    # OR activate it on macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    # OR install the package in development mode (recommended)
    pip install -e .
    ```

## Usage

The system requires two main components to be running simultaneously: the Ollama service (providing the LLM) and the Agentic Docker MCP server (executing the Docker commands).

### Step 1: Start Ollama Service

Open a **new terminal** window/tab.

1.  Navigate to the project directory and activate the virtual environment.
    ```bash
    cd agentic-docker # Or the path where you cloned the project
    # Activate venv (as shown in Installation step 2)
    .\.venv\Scripts\activate # Windows Command Prompt
    # OR
    source .venv/bin/activate # macOS/Linux
    ```
2.  **Important for Corporate Networks:** Set proxy bypass variables to ensure the application can connect to the local Ollama API.
    ```bash
    # Windows Command Prompt / PowerShell
    set HTTP_PROXY=
    set HTTPS_PROXY=
    set ALL_PROXY=
    set NO_PROXY=localhost,127.0.0.1,0.0.0.0,::1

    # OR on macOS/Linux
    export HTTP_PROXY=""
    export HTTPS_PROXY=""
    export ALL_PROXY=""
    export NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
    ```
3.  Ensure the `phi3:mini` model is downloaded:
    ```bash
    ollama pull phi3:mini
    ```
4.  Start the Ollama service:
    ```bash
    ollama serve
    ```
    Keep this terminal window open. The Ollama service needs to run continuously.

### Step 2: Start the Agentic Docker MCP Server

Open **another new terminal** window/tab.

1.  Navigate to the project directory and activate the virtual environment.
    ```bash
    cd agentic-docker
    # Activate venv
    .\.venv\Scripts\activate # Windows Command Prompt
    # OR
    source .venv/bin/activate # macOS/Linux
    ```
2.  Set the same proxy bypass variables as in Step 1.
    ```bash
    # Windows Command Prompt / PowerShell
    set HTTP_PROXY=
    set HTTPS_PROXY=
    set ALL_PROXY=
    set NO_PROXY=localhost,127.0.0.1,0.0.0.0,::1

    # OR on macOS/Linux
    export HTTP_PROXY=""
    export HTTPS_PROXY=""
    export ALL_PROXY=""
    export NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
    ```
3.  Start the Agentic Docker server:
    ```bash
    agentic-docker server
    # OR if not installed as a package:
    python -m agentic_docker.cli server
    ```
    Keep this terminal window open. The MCP server needs to run continuously.

### Step 3: Run Commands

Open **a third terminal** window/tab for running your commands.

1.  Navigate to the project directory and activate the virtual environment.
    ```bash
    cd agentic-docker
    # Activate venv
    .\.venv\Scripts\activate # Windows Command Prompt
    # OR
    source .venv/bin/activate # macOS/Linux
    ```
2.  Set the same proxy bypass variables as in Steps 1 and 2.
    ```bash
    # Windows Command Prompt / PowerShell
    set HTTP_PROXY=
    set HTTPS_PROXY=
    set ALL_PROXY=
    set NO_PROXY=localhost,127.0.0.1,0.0.0.0,::1

    # OR on macOS/Linux
    export HTTP_PROXY=""
    export HTTPS_PROXY=""
    export ALL_PROXY=""
    export NO_PROXY="localhost,127.0.0.1,0.0.0.0,::1"
    ```
3.  Use natural language to control Docker:
    ```bash
    agentic-docker run "List all containers"
    agentic-docker run "Start nginx on port 8080"
    agentic-docker run "Stop container my-nginx"
    agentic-docker run "List running containers"
    ```

## Configuration

The default LLM model is `phi3:mini`. You can change this by modifying `agentic_docker/llm/ollama_client.py`:

```python
# agentic_docker/llm/ollama_client.py
MODEL = "llama3:8b"  # Change to your preferred model
```

Supported models depend on your Ollama installation. Common options:
- `phi3:mini` (Default, fast, low memory)
- `llama3:8b` (Better reasoning, higher memory)
- `mistral:7b` (Balanced)

## Available Commands

### Core CLI Commands

- `agentic-docker server`: Starts the MCP server. **This must be running for other commands to work.**
- `agentic-docker run "<query>"`: Executes a Docker command based on the natural language query.
- `agentic-docker status`: Checks the status of the LLM connection, MCP server, and available tools.
- `agentic-docker list-tools`: Lists the currently available Docker tools.

### Natural Language Examples (using `agentic-docker run`)

- **Listing:**
  - `"List all containers"`
  - `"Show running containers"`
- **Starting:**
  - `"Start nginx"`
  - `"Start nginx on port 8080"`
  - `"Start redis:latest with name my-cache"`
- **Stopping:**
  - `"Stop container my-nginx"`
  - `"Stop container <container_id_or_name>"`

### Options for `run` Command

- `--verbose, -v`: Show detailed processing information.
- `--no-confirm, -y`: Skip safety confirmation prompts (use with caution!).

## Safety Features

- **Confirmation Prompts:** Operations like `docker_run_container` and `docker_stop_container` will prompt for confirmation before execution to prevent accidental changes.
- **Input Validation:** Arguments passed to Docker commands are validated using Pydantic models before execution.
- **Safe Execution:** The system uses the Docker Python SDK instead of `subprocess` to run Docker commands, reducing the risk of command injection.

## Project Structure

```
agentic-docker/
├── agentic_docker/           # Main Python package
│   ├── __init__.py
│   ├── cli.py                # Command-Line Interface (Typer)
│   ├── agent.py              # Orchestrates LLM, tools, safety
│   ├── safety.py             # Confirmation logic
│   ├── mcp/                  # Model Context Protocol components
│   │   ├── __init__.py
│   │   ├── server.py         # MCP server (JSON-RPC)
│   │   └── client.py         # MCP client
│   ├── tools/                # Docker tool definitions
│   │   ├── __init__.py
│   │   ├── base.py           # Abstract Tool interface
│   │   ├── docker_list.py    # List containers tool
│   │   ├── docker_run.py     # Run container tool
│   │   └── docker_stop.py    # Stop container tool
│   └── llm/                  # LLM interaction components
│       ├── __init__.py
│       └── ollama_client.py  # Ollama API interaction
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Package build configuration
└── README.md                 # This file
```

## Troubleshooting

- **"Cannot connect to MCP server..."**: Ensure `agentic-docker server` is running in another terminal.
- **"LLM not available..." / Proxy Errors**: Ensure `ollama serve` is running and proxy environment variables (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`) are set correctly in the terminal where you run commands and the server.
- **"Permission denied" with Docker**: Ensure your user has permissions to run Docker commands (e.g., is part of the `docker` group on Linux).
- **"Model 'phi3:mini' not found..."**: Run `ollama pull phi3:mini` in a terminal where Ollama is accessible.
