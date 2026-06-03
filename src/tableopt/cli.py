"""Command-line interface for table allocation optimizer."""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table as RichTable

from tableopt.models import FloorState, Party, PartyType
from tableopt.offline.fit_distributions import fit_distributions
from tableopt.optimizer import ScoringConfig, recommend_assignment
from tableopt.priors import PriorDistributions

app = typer.Typer(help="Table allocation optimizer CLI")
console = Console()


@app.command()
def fit(
    csv: str = typer.Option(..., help="Path to historical CSV file"),
    out: str = typer.Option("artifacts/priors.json", help="Output path for priors JSON"),
) -> None:
    """
    Fit probability distributions from historical data.

    Generates walk-in PMFs, dwell-time distributions, and no-show rates.
    """
    console.print(f"[bold blue]Reading historical data from {csv}...[/bold blue]")

    try:
        priors = fit_distributions(csv, out)

        console.print(f"[bold green]✓ Successfully fit distributions![/bold green]\n")

        # Display summary
        console.print("[bold]Summary:[/bold]")
        console.print(
            f"  • Data range: {priors.data_range.start_date} to {priors.data_range.end_date}"
        )
        console.print(f"  • Time slots with walk-in data: {len(priors.walk_in_pmf)}")
        console.print(f"  • Party size bands modeled: {len(priors.dwell_time)}")
        console.print(f"  • Overall no-show rate: {priors.no_show_rate.overall:.1%}")
        console.print(f"\n[bold green]✓ Priors saved to {out}[/bold green]")

    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def recommend(
    state: str = typer.Option(..., help="Path to floor state JSON"),
    priors: str = typer.Option(..., help="Path to priors JSON"),
    party_size: int = typer.Option(..., help="Size of party to seat"),
    party_id: str = typer.Option("P_CLI", help="Party ID"),
    config_file: Optional[str] = typer.Option(None, help="Path to venue config YAML"),
    top_k: int = typer.Option(3, help="Number of recommendations to show"),
) -> None:
    """
    Get table assignment recommendations for a party.

    Scores all available tables and returns ranked recommendations.
    """
    try:
        # Load floor state
        with open(state) as f:
            floor_state = FloorState.model_validate_json(f.read())

        # Load priors
        with open(priors) as f:
            priors_data = PriorDistributions.model_validate_json(f.read())

        # Load config (or use defaults)
        config = ScoringConfig()
        if config_file:
            # TODO: Load from YAML
            pass

        # Create party
        party = Party(id=party_id, size=party_size, type=PartyType.WALK_IN)

        # Get recommendations
        recommendations = recommend_assignment(party, floor_state, priors_data, config, top_k)

        # Display results
        console.print(f"\n[bold blue]🎯 Recommendations for party of {party_size}:[/bold blue]\n")

        if not recommendations:
            console.print("[yellow]No available tables found.[/yellow]")
            raise typer.Exit(0)

        # Top recommendation
        top = recommendations[0]
        if not top.is_feasible:
            console.print(f"[bold red]✗ No feasible assignments found[/bold red]")
            console.print(f"   {top.rationale}")
            raise typer.Exit(1)

        console.print(f"[bold green]Top choice: Table {top.table_id}[/bold green]")
        console.print(f"  Score: {top.total_score:.2f}")
        console.print(f"  {top.rationale}\n")

        console.print("[dim]Score breakdown:[/dim]")
        console.print(f"  • Fit penalty: {top.fit_penalty:.3f}")
        console.print(f"  • Opportunity cost: {top.opportunity_cost:.3f}")
        console.print(f"  • Reservation risk: {top.reservation_risk:.3f}")

        # Show alternatives
        if len(recommendations) > 1:
            console.print("\n[bold]Alternatives:[/bold]")
            table = RichTable(show_header=True, header_style="bold")
            table.add_column("Rank", style="dim")
            table.add_column("Table")
            table.add_column("Score", justify="right")
            table.add_column("Rationale")

            for i, rec in enumerate(recommendations[1:], start=2):
                if rec.is_feasible:
                    table.add_row(
                        f"{i}.",
                        rec.table_id,
                        f"{rec.total_score:.2f}",
                        rec.rationale[:60] + ("..." if len(rec.rationale) > 60 else ""),
                    )

            console.print(table)

    except FileNotFoundError as e:
        console.print(f"[bold red]✗ File not found: {e.filename}[/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def validate_csv(
    csv: str = typer.Argument(..., help="Path to CSV file to validate"),
) -> None:
    """
    Validate that a CSV file has the required columns and format.
    """
    import pandas as pd

    try:
        df = pd.read_csv(csv)

        required = [
            "date",
            "arrival_time",
            "party_size",
            "source",
            "table_id",
            "dwell_minutes",
            "no_show",
        ]
        missing = [col for col in required if col not in df.columns]

        if missing:
            console.print(f"[bold red]✗ Missing required columns:[/bold red]")
            for col in missing:
                console.print(f"  • {col}")
            raise typer.Exit(1)

        console.print(f"[bold green]✓ CSV is valid![/bold green]\n")
        console.print(f"[bold]Summary:[/bold]")
        console.print(f"  • Total rows: {len(df)}")
        console.print(f"  • Walk-ins: {(df['source'] == 'walk_in').sum()}")
        console.print(f"  • Reservations: {(df['source'] == 'reservation').sum()}")
        console.print(f"  • No-shows: {df['no_show'].sum()}")
        console.print(f"  • Date range: {df['date'].min()} to {df['date'].max()}")

    except FileNotFoundError:
        console.print(f"[bold red]✗ File not found: {csv}[/bold red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        raise typer.Exit(1)


@app.command()
def agent(
    priors: str = typer.Option(..., help="Path to priors JSON"),
    state_file: str = typer.Option(..., help="Path to floor state JSON to watch"),
    watch: bool = typer.Option(False, help="Watch file for changes"),
    interval: int = typer.Option(30, help="Polling interval in seconds (if watching)"),
) -> None:
    """
    Run live agent that monitors floor state and makes recommendations.

    In watch mode, monitors the state file and emits recommendations on changes.
    """
    from tableopt.agent.runner import run_agent

    try:
        console.print("[bold blue]Starting table allocation agent...[/bold blue]")
        console.print(f"  • Priors: {priors}")
        console.print(f"  • State file: {state_file}")
        console.print(f"  • Watch mode: {watch}")

        run_agent(priors, state_file, watch, interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[bold red]✗ Error: {e}[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
