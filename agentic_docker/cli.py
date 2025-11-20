# agentic_docker/cli.py
"""
Command-Line Interface (CLI)

This module defines the command-line interface for the Agentic Docker tool.
It uses Typer to create user-friendly commands and handles argument parsing,
help text, and command execution. This is the main entry point for users.
"""

# Import Typer - a modern library for building CLI applications
import typer
# Import typing utilities for type hints
from typing import Optional
# Import our agent that processes queries
from .agent import process_query_with_status_check
# Import the MCP server function
from .mcp.server import start_mcp_server
# Import system status function
from .agent import get_system_status

# Create the main Typer application instance
# This will handle command registration and argument parsing
app = typer.Typer(
    # Application name and description for help text
    name="agentic-docker",
    help="An AI-powered Docker assistant that understands natural language commands.",
    # Add common options like --version, --help
    add_completion=False,  # Disable shell completion for simplicity
    no_args_is_help=True,  # Show help when no arguments are provided
    rich_markup_mode="rich"  # Enable rich formatting for help text
)

@app.command(
    name="run",
    help="Execute a Docker command in natural language."
)
def run_command(
    query: str = typer.Argument(
        ...,
        help="Your natural language Docker command (e.g., 'Start nginx on port 8080')"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed processing information"
    ),
    no_confirm: bool = typer.Option(
        False,
        "--no-confirm",
        "-y",
        help="Skip safety confirmation prompts (use with caution!)"
    )
):
    """
    Execute a Docker command using natural language.
    
    This command takes your natural language request, processes it through
    the AI agent, and executes the appropriate Docker operation.
    
    Examples:
        agentic-docker run "List all containers"
        agentic-docker run "Start nginx on port 8080"
        agentic-docker run "Stop container my-nginx" --verbose
        agentic-docker run "Run redis" --no-confirm
    """
    # Import safety module to potentially modify confirmation behavior
    from .safety import USE_DETAILED_CONFIRMATION
    
    # Handle the --no-confirm flag
    if no_confirm:
        # Temporarily disable detailed confirmation for this run
        # Note: In a real system, you'd want a more robust way to handle this
        import agentic_docker.safety as safety_module
        original_detailed = safety_module.USE_DETAILED_CONFIRMATION
        safety_module.USE_DETAILED_CONFIRMATION = False
        print("⚠️  Safety confirmation disabled with --no-confirm flag")
    
    if verbose:
        print(f"🔍 Processing query: '{query}'")
        print("📊 System status check...")
        status = get_system_status()
        print(f"   LLM: {'✅ Available' if status['llm']['available'] else '❌ Unavailable'}")
        print(f"   MCP Server: {'✅ Available' if status['mcp_server']['available'] else '❌ Unavailable'}")
        print(f"   Tools: {len(status['tools']['available'])} available")
        print("-" * 50)
    
    try:
        # Process the query through our agent
        result = process_query_with_status_check(query)
        
        # Output the result
        typer.echo(result)
        
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        typer.echo("\n❌ Operation cancelled by user (Ctrl+C)")
        raise typer.Exit(code=1)
    
    except Exception as e:
        # Handle any unexpected errors
        typer.echo(f"❌ Error: {str(e)}")
        raise typer.Exit(code=1)
    
    finally:
        # Restore original confirmation setting if --no-confirm was used
        if no_confirm:
            safety_module.USE_DETAILED_CONFIRMATION = original_detailed

@app.command(
    name="server",
    help="Start the MCP (Model Context Protocol) server."
)
def start_server(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host address to bind the server to"
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port number to listen on"
    )
):
    """
    Start the MCP server that exposes Docker tools as JSON-RPC endpoints.
    
    This server must be running before you can execute Docker commands.
    The server runs indefinitely until stopped with Ctrl+C.
    
    Examples:
        agentic-docker server
        agentic-docker server --host 0.0.0.0 --port 9000
    """
    typer.echo("🚀 Starting MCP Server...")
    typer.echo(f"   Host: {host}")
    typer.echo(f"   Port: {port}")
    typer.echo("   Press Ctrl+C to stop the server")
    typer.echo("-" * 50)
    
    try:
        # Start the MCP server
        start_mcp_server(host=host, port=port)
    except KeyboardInterrupt:
        typer.echo("\n🛑 MCP Server stopped by user (Ctrl+C)")
        raise typer.Exit(code=0)
    except Exception as e:
        typer.echo(f"❌ Error starting server: {str(e)}")
        raise typer.Exit(code=1)

@app.command(
    name="status",
    help="Check the status of the Agentic Docker system."
)
def check_status():
    """
    Check the status of all system components.
    
    This command verifies that the LLM, MCP server, and tools are available
    and ready to process commands.
    """
    typer.echo("🔍 Checking Agentic Docker System Status...")
    typer.echo("-" * 50)
    
    status = get_system_status()
    
    # Display LLM status
    llm_status = "✅ Available" if status['llm']['available'] else "❌ Unavailable"
    typer.echo(f"LLM Model ({status['llm']['model']}): {llm_status}")
    
    # Display MCP server status
    mcp_status = "✅ Available" if status['mcp_server']['available'] else "❌ Unavailable"
    typer.echo(f"MCP Server: {mcp_status}")
    
    # Display available tools
    typer.echo(f"Available Tools: {status['tools']['count']}")
    for tool in status['tools']['available']:
        typer.echo(f"   • {tool}")
    
    typer.echo("-" * 50)
    
    # Exit with appropriate code based on system health
    if status['llm']['available'] and status['mcp_server']['available']:
        typer.echo("✅ System is ready to process commands!")
        raise typer.Exit(code=0)
    else:
        typer.echo("❌ System is not ready. Please check the status above.")
        raise typer.Exit(code=1)

@app.command(
    name="list-tools",
    help="List all available Docker tools."
)
def list_tools():
    """
    List all available Docker tools that can be used with natural language.
    
    This shows what Docker operations are currently supported by the system.
    """
    from .tools import get_tools_schema
    
    typer.echo("📋 Available Docker Tools:")
    typer.echo("-" * 50)
    
    tools_schema = get_tools_schema()
    
    for i, tool in enumerate(tools_schema, 1):
        typer.echo(f"{i}. {tool['name']}")
        typer.echo(f"   Description: {tool['description']}")
        
        # Show parameters if available
        params = tool['parameters']
        if 'properties' in params and params['properties']:
            typer.echo("   Parameters:")
            for param_name, param_info in params['properties'].items():
                required = " (required)" if param_name in params.get('required', []) else ""
                typer.echo(f"     • {param_name}: {param_info.get('description', 'No description')}{required}")
        else:
            typer.echo("   Parameters: None required")
        typer.echo()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(None, "--version", "-v", help="Show version and exit")
):
    """
    Agentic Docker - AI-Powered Docker Assistant
    
    Use natural language to control Docker containers.
    """
    if version:
        typer.echo("Agentic Docker v1.0.0")
        raise typer.Exit()
    
    # If no command is provided, show help
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()

# Entry point function
def main():
    """
    Main entry point for the CLI application.
    
    This function is called when the script is executed directly.
    It runs the Typer application which handles command parsing and execution.
    """
    app()

# Example usage patterns:
"""
Terminal 1 (start server):
$ agentic-docker server
$ agentic-docker server --host 0.0.0.0 --port 9000

Terminal 2 (execute commands):
$ agentic-docker run "List all containers"
$ agentic-docker run "Start nginx on port 8080" --verbose
$ agentic-docker run "Stop container my-nginx" --no-confirm
$ agentic-docker status
$ agentic-docker list-tools
"""

if __name__ == "__main__":
    # This allows the script to be run directly for testing
    main()