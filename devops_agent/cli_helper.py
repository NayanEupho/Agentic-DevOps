
def process_command_turn(
    session,
    query: str,
    verbose: bool = False,
    no_confirm: bool = False,
    check_llm: bool = False
):
    """
    Process a single command turn:
    1. Log user query.
    2. Prepare history.
    3. Call Agent.
    4. Handle Disambiguation.
    5. Log results.
    6. Print output.
    """
    import typer
    from .agent import process_query_with_status_check
    from .database.session_manager import session_manager
    
    # Legacy safety flags removed in Phase 6
    # from .safety import USE_DETAILED_CONFIRMATION
    # if no_confirm: ... handled in logic below
    
    try:
        # Log user query
        session_manager.add_message(session.id, "user", query)
        
        # Prepare history for the agent
        history = []
        for msg in session.messages:
            if msg.role == "system":
                continue
            
            content = msg.content
            # Truncate large outputs
            if "[System Output]" in content and len(content) > 500:
                content = content[:500] + "... (truncated)"
            
            history.append({"role": msg.role, "content": content})
        
        # Process the query
        result_pkg = process_query_with_status_check(query, history, check_llm=check_llm)
        
        # --- PHASE 6: CLI SAFETY CONFIRMATION ---
        if result_pkg.get("confirmation_request") and not no_confirm:
            req = result_pkg["confirmation_request"]
            tool_name = req["tool"]
            args = req["arguments"]
            risk = req.get("risk", {})
            
            typer.echo("\n" + "="*60)
            typer.echo(f"🚨 APPROVAL REQUIRED: {tool_name}")
            typer.echo(f"⚠️  Risk: {risk.get('risk_level', 'UNKNOWN')}")
            typer.echo(f"   Reason: {risk.get('reason', '')}")
            if risk.get("impact_analysis"):
                typer.echo("\n   Impact:")
                for impact in risk["impact_analysis"]:
                    typer.echo(f"   • {impact}")
                    
            typer.echo("\n   Arguments:")
            typer.echo(f"   {args}")
            typer.echo("="*60)
            
            if typer.confirm("Do you want to proceed?"):
                typer.echo(f"\n🚀 Executing {tool_name}...")
                # Bypass Agent and call directly
                from .mcp.client import call_tool_async
                import asyncio
                from .agent import format_tool_result
                
                # Execute
                raw_result = asyncio.run(call_tool_async(tool_name, args))
                formatted = format_tool_result(tool_name, raw_result)
                
                # Update result_pkg for standard logging downstream
                result_pkg["output"] = formatted
                result_pkg["tool_calls"] = [{"name": tool_name, "arguments": args}]
            else:
                typer.echo("❌ Action cancelled.")
                return

        # --- DISAMBIGUATION HANDLING ---
        if result_pkg.get("disambiguation_needed"):
            options = result_pkg.get("options", {})
            typer.echo("\n🤔 This query is ambiguous. Please select the target:")
            for key, opt in options.items():
                typer.echo(f"   [{key}] {opt['label']}")
            
            choice = typer.prompt("Enter your choice", default="1")
            
            if choice in options:
                # Update tool call
                selected_tool = options[choice]["tool"]
                tool_calls = result_pkg.get("tool_calls", [])
                for tc in tool_calls:
                    if tc["name"] == result_pkg.get("ambiguous_tool"):
                        tc["name"] = selected_tool
                
                # Re-run
                from .agent import execute_tool_calls_async
                import asyncio
                result_pkg = asyncio.run(execute_tool_calls_async(tool_calls))
            else:
                typer.echo("❌ Invalid choice.")
                # We don't exit here, just return failure logic if we were strictly returning
                # But since we are printing, maybe we just stop?
                # In REPL, we shouldn't exit the whole app.
                return

        # 1. Log Assistant Tool Calls
        import json
        tool_calls = result_pkg.get("tool_calls", [])
        if tool_calls:
            session_manager.add_message(session.id, "assistant", json.dumps(tool_calls))
        
        # 2. Log System Output
        clean_result = result_pkg.get("output", "")
        if "----------------------------------------" in clean_result:
             parts = clean_result.split("----------------------------------------")
             if len(parts) > 1:
                 clean_result = parts[-1].strip()
                 if clean_result.startswith("🤖") or clean_result.startswith("✅") or clean_result.startswith("❌") or clean_result.startswith("⚠️"):
                     clean_result = clean_result[1:].strip()

        session_manager.add_message(session.id, "user", f"[System Output] {clean_result}")
        
        # Output the result
        # Check if we should stream this (Casual chat or AI Explanation)
        if "🤖 **AI Explanation:**" in result_pkg.get("output", "") or result_pkg.get("output", "").startswith("🗣️"):
            stream_echo(result_pkg.get("output", ""))
        else:
            typer.echo(result_pkg.get("output", ""))
        
    except Exception as e:
        typer.echo(f"❌ Error: {str(e)}")
    
        pass # Safety cleanup handled automatically

def stream_echo(text: str, speed: float = 0.01):
    """Simulate streaming output like a modern LLM interface."""
    import time
    import sys
    
    # Simple typing effect
    import typer
    for char in text:
        typer.echo(char, nl=False)
        # Random variance for realism
        # time.sleep(speed) 
        # Actually speed is annoying if too slow. 0.005 is better.
        if char == '\n':
             time.sleep(0.01)
        else:
             time.sleep(0.002)
    print() # Newline at end
