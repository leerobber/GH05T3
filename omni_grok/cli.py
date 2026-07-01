import typer
from .agent import (
    ask_omni,
    explain_file,
    plan_task,
    propose_diff,
    omni_context_summary,
    suggest_commands,
    dry_run_command,
)

app = typer.Typer(help="Omni_Grok: Cloud-powered Grok-style CLI agent for the Omni project.")

@app.command()
def ask(prompt: str):
    typer.echo(ask_omni(prompt))

@app.command()
def explain(path: str):
    typer.echo(explain_file(path))

@app.command()
def plan(task: str):
    typer.echo(plan_task(task))

@app.command()
def diff(path: str, task: str):
    typer.echo(propose_diff(path, task))

@app.command()
def context():
    typer.echo(omni_context_summary())

@app.command()
def commands(task: str):
    typer.echo(suggest_commands(task))

@app.command()
def run(cmd: str):
    typer.echo(dry_run_command(cmd))

if __name__ == "__main__":
    app()
