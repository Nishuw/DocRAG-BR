"""DocRAG BR — interface principal: terminal-first, estilo Claude Code.

Uso: python -m src.cli

Nao e um chatbot numa pagina: e um cockpit de auditoria no terminal.
Pergunta em linguagem natural = resposta auditada. Comandos com "/" operam
a plataforma (auditoria autonoma, explorador do indice, evidencias, custo).
"""
import sys
import time
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.chat.pdf_preview import render_source_page
from src.config import LLM_MODEL, OPENROUTER_API_KEY, VISION_MODEL
from src.embeddings.embedder import get_collection, query_chunks
from src.rag import answer_stream
from src.verification.auditor import run_audit
from src.verification.verifier import verify_answer

console = Console()

# precos aproximados do gemini-2.5-flash via OpenRouter (USD por 1M tokens)
_PRICE_IN_PER_M = 0.30
_PRICE_OUT_PER_M = 2.50
_CHARS_PER_TOKEN = 4  # estimativa

_SEVERITY_STYLE = {
    "alerta": ("red", "ALERT"),
    "atencao": ("yellow", "ATTENTION"),
    "destaque": ("dark_orange", "HIGHLIGHT"),
    "info": ("blue", "INFO"),
}

_EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "data" / "evidence"

state = {
    "lang": "en",
    "queries": 0,
    "chars_in": 0,
    "chars_out": 0,
    "seconds": 0.0,
    "openables": [],  # [(source, page, content)] — alvo do /open N
}


# ---------------------------------------------------------------- helpers ---

def _fidelity_bar(confirmed: int, total: int, width: int = 28) -> Text:
    ratio = confirmed / total if total else 0.0
    filled = round(width * ratio)
    bar = Text()
    bar.append("█" * filled, style="green")
    bar.append("░" * (width - filled), style="grey37")
    bar.append(f"  {confirmed}/{total} verified ({round(ratio * 100)}%)",
               style="bold green" if confirmed == total else "bold yellow")
    return bar


def _annotated_text(answer: str, numbers: list[dict]) -> Text:
    """Resposta com cada numero auditado marcado: verde ✓ ou vermelho ⚠."""
    t = Text()
    pos = 0
    for n in sorted(numbers, key=lambda x: x["start"]):
        if n["start"] < pos:
            continue
        t.append(answer[pos:n["start"]])
        if n["verified"]:
            t.append(n["raw"], style="bold green")
            t.append("✓", style="green")
        else:
            t.append(n["raw"], style="bold red")
            t.append("⚠", style="red")
        pos = n["end"]
    t.append(answer[pos:])
    return t


def _cost_line(elapsed: float, chars_in: int, chars_out: int) -> Text:
    tok_in = chars_in // _CHARS_PER_TOKEN
    tok_out = chars_out // _CHARS_PER_TOKEN
    usd = tok_in / 1e6 * _PRICE_IN_PER_M + tok_out / 1e6 * _PRICE_OUT_PER_M
    return Text(
        f"~{tok_in:,} tokens in · ~{tok_out:,} out · est. ${usd:.4f} · {elapsed:.1f}s",
        style="dim",
    )


def _register_usage(elapsed: float, chars_in: int, chars_out: int) -> None:
    state["queries"] += 1
    state["chars_in"] += chars_in
    state["chars_out"] += chars_out
    state["seconds"] += elapsed


def _index_stats() -> dict:
    try:
        col = get_collection()
        res = col.get(include=["metadatas"])
        stats = {"total": 0, "text": 0, "table": 0, "image": 0, "sources": set()}
        for m in res["metadatas"]:
            stats["total"] += 1
            stats[m["type"]] = stats.get(m["type"], 0) + 1
            stats["sources"].add(m["source"])
        return stats
    except Exception:  # noqa: BLE001
        return {"total": 0, "text": 0, "table": 0, "image": 0, "sources": set()}


# ---------------------------------------------------------------- screens ---

def show_header() -> None:
    stats = _index_stats()
    title = Text()
    title.append("DOCRAG BR", style="bold white on dark_green")
    title.append("  the analyst that proves every claim — down to the pixel",
                 style="italic bright_black")

    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="bright_black")
    grid.add_column()
    key_txt = ("[green]configured[/]" if OPENROUTER_API_KEY
               else "[red]missing — set OPENROUTER_API_KEY in .env[/]")
    grid.add_row("index", f"[bold]{stats['total']}[/] chunks  "
                          f"([cyan]{stats['text']}[/] text · "
                          f"[magenta]{stats['table']}[/] table · "
                          f"[yellow]{stats['image']}[/] chart)")
    grid.add_row("docs", ", ".join(sorted(stats["sources"])) or "[red]none — run: python -m src.ingest[/]")
    grid.add_row("llm", f"{LLM_MODEL}  [bright_black]· vision:[/] {VISION_MODEL}")
    grid.add_row("api key", key_txt)
    grid.add_row("language", f"{state['lang']}  [bright_black](/lang en|pt)[/]")

    console.print()
    console.print(Panel(Group(title, Rule(style="dark_green"), grid),
                        border_style="dark_green", padding=(1, 2)))
    console.print(
        "  [bold cyan]ask anything[/] about the indexed documents — or:  "
        "[bold]/audit[/] autonomous audit · [bold]/find[/] search index · "
        "[bold]/open N[/] view evidence · [bold]/stats[/] · [bold]/help[/]\n",
        highlight=False,
    )


def show_help() -> None:
    t = Table(title="command palette", title_style="bold", border_style="bright_black")
    t.add_column("command", style="bold cyan", no_wrap=True)
    t.add_column("what it does")
    t.add_row("<question>", "ask the documents — streamed answer, every number audited against the source")
    t.add_row("/audit", "autonomous audit: the system reads the document and reports verified findings")
    t.add_row("/find <text>", "semantic search over the knowledge index (no LLM, local embeddings)")
    t.add_row("/open <n>", "open evidence #n: the real PDF page with the cited excerpt highlighted")
    t.add_row("/index", "knowledge index status (chunks by type, documents)")
    t.add_row("/lang en|pt", "answer/finding language (numbers always keep the Brazilian source format)")
    t.add_row("/stats", "session metrics: queries, tokens, estimated cost, time")
    t.add_row("/help", "this palette")
    t.add_row("/exit", "quit")
    console.print(t)


def show_stats() -> None:
    tok_in = state["chars_in"] // _CHARS_PER_TOKEN
    tok_out = state["chars_out"] // _CHARS_PER_TOKEN
    usd = tok_in / 1e6 * _PRICE_IN_PER_M + tok_out / 1e6 * _PRICE_OUT_PER_M
    t = Table(border_style="bright_black", show_header=False)
    t.add_column(style="bright_black")
    t.add_column(style="bold")
    t.add_row("queries", str(state["queries"]))
    t.add_row("tokens in (est.)", f"{tok_in:,}")
    t.add_row("tokens out (est.)", f"{tok_out:,}")
    t.add_row("cost (est.)", f"${usd:.4f}")
    t.add_row("llm time", f"{state['seconds']:.1f}s")
    console.print(Panel(t, title="session", border_style="bright_black"))


def show_index() -> None:
    stats = _index_stats()
    t = Table(border_style="bright_black", show_header=False)
    t.add_column(style="bright_black")
    t.add_column(style="bold")
    t.add_row("total chunks", str(stats["total"]))
    t.add_row("text", str(stats["text"]))
    t.add_row("tables", str(stats["table"]))
    t.add_row("charts (vision)", str(stats["image"]))
    t.add_row("documents", ", ".join(sorted(stats["sources"])) or "-")
    console.print(Panel(t, title="knowledge index", border_style="bright_black"))


def do_find(query: str) -> None:
    if not query.strip():
        console.print("[red]usage:[/] /find <text>")
        return
    with console.status("[cyan]searching index (local embeddings)..."):
        hits = query_chunks(query, 6)
    t = Table(border_style="bright_black")
    t.add_column("#", style="bright_black")
    t.add_column("type", style="cyan")
    t.add_column("page", style="magenta")
    t.add_column("match", max_width=70)
    t.add_column("dist", style="bright_black")
    state["openables"] = []
    for i, h in enumerate(hits, 1):
        snippet = " ".join(h["content"].split())[:120]
        t.add_row(str(i), h["type"], str(h["page"]), snippet, f"{h['distance']:.3f}")
        state["openables"].append((h["source"], h["page"], h["content"]))
    console.print(t)
    console.print("[bright_black]/open N shows the real page with the excerpt highlighted[/]")


def do_open(arg: str) -> None:
    try:
        n = int(arg.strip())
        source, page, content = state["openables"][n - 1]
    except (ValueError, IndexError):
        console.print("[red]usage:[/] /open <n>  (after an answer, /audit or /find)")
        return
    with console.status(f"[cyan]rendering page {page} with highlight..."):
        png = render_source_page(source, page, content)
    if not png:
        console.print("[red]could not render this page.[/]")
        return
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out = _EVIDENCE_DIR / f"evidence_p{page}.png"
    out.write_bytes(png)
    import os
    os.startfile(out)  # noqa: S606 — abre no visualizador padrao do SO
    console.print(f"[green]evidence opened:[/] {source} — page {page} [bright_black]({out})[/]")


def do_audit() -> None:
    t0 = time.time()
    with console.status("[bold cyan]autonomous audit — cross-checking narrative × tables × charts...",
                        spinner="dots"):
        findings = run_audit(lang=state["lang"])
    elapsed = time.time() - t0
    if not findings:
        console.print("[yellow]no verified findings (or empty index).[/]")
        return
    state["openables"] = []
    console.print()
    console.print(Rule("[bold]what the auditor found — without being asked[/]",
                       style="dark_green"))
    console.print("[bright_black]only findings whose numbers were confirmed in the source survive[/]\n")
    total_chars = 0
    for i, f in enumerate(findings, 1):
        sev = str(f.get("severidade", "info")).lower()
        color, label = _SEVERITY_STYLE.get(sev, _SEVERITY_STYLE["info"])
        v = f["verification"]
        body = Group(
            _annotated_text(f["descoberta"], v["numbers"]),
            Text(""),
            _fidelity_bar(v["confirmed"], v["total"]) if v["total"] else Text(""),
            Text(f"evidence #{i}: {f.get('arquivo', '?')} — page {f.get('pagina', '?')}"
                 f"   (/open {i})", style="bright_black"),
        )
        console.print(Panel(
            body,
            title=f"[bold {color}]{label}[/] [bold]{f['titulo']}[/]",
            border_style=color,
            padding=(1, 2),
        ))
        state["openables"].append((f.get("arquivo", ""), f.get("pagina", 0), f.get("trecho", "")))
        total_chars += len(f["descoberta"])
    console.print(_cost_line(elapsed, 120_000, total_chars))
    _register_usage(elapsed, 120_000, total_chars)


def do_ask(question: str) -> None:
    t0 = time.time()
    with console.status("[cyan]routing intent → dense retrieval → reranking...", spinner="dots"):
        stream, chunks = answer_stream(question, lang=state["lang"])

    buf = ""
    with Live(console=console, refresh_per_second=12) as live:
        for tok in stream:
            buf += tok
            live.update(Panel(Text(buf), title="[cyan]answer[/]",
                              border_style="cyan", padding=(1, 2)))
        v = verify_answer(buf, chunks)
        body = Group(
            _annotated_text(buf.strip(), v["numbers"]),
            Text(""),
            _fidelity_bar(v["confirmed"], v["total"]) if v["total"] else
            Text("no auditable numbers in this answer", style="bright_black"),
        )
        live.update(Panel(body, title="[cyan]answer — audited[/]",
                          border_style="cyan", padding=(1, 2)))
    elapsed = time.time() - t0

    if chunks:
        t = Table(title="sources", title_style="bright_black",
                  border_style="bright_black")
        t.add_column("#", style="bright_black")
        t.add_column("type", style="cyan")
        t.add_column("document")
        t.add_column("page", style="magenta")
        state["openables"] = []
        for i, c in enumerate(chunks, 1):
            t.add_row(str(i), c["type"], c["source"], str(c["page"]))
            state["openables"].append((c["source"], c["page"], c["content"]))
        console.print(t)
        console.print("[bright_black]/open N shows the real page with the excerpt highlighted[/]")

    chars_in = sum(len(c["content"]) for c in chunks) + len(question)
    console.print(_cost_line(elapsed, chars_in, len(buf)))
    _register_usage(elapsed, chars_in, len(buf))


# ------------------------------------------------------------------- main ---

def main() -> None:
    show_header()
    while True:
        try:
            raw = console.input("[bold dark_green]docrag ›[/] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bright_black]bye.[/]")
            return
        raw = raw.replace('\ufeff', "").strip()  # BOM de entrada via pipe
        if not raw:
            continue
        cmd, _, arg = raw.partition(" ")
        cmd = cmd.lower()
        try:
            if cmd in ("/exit", "/quit", "/q"):
                console.print("[bright_black]bye.[/]")
                return
            elif cmd == "/help":
                show_help()
            elif cmd == "/audit":
                do_audit()
            elif cmd == "/find":
                do_find(arg)
            elif cmd == "/open":
                do_open(arg)
            elif cmd == "/index":
                show_index()
            elif cmd == "/stats":
                show_stats()
            elif cmd == "/lang":
                if arg.strip().lower() in ("en", "pt"):
                    state["lang"] = arg.strip().lower()
                    console.print(f"[green]language set to {state['lang']}[/]")
                else:
                    console.print("[red]usage:[/] /lang en|pt")
            elif cmd.startswith("/"):
                console.print(f"[red]unknown command:[/] {cmd}  ([bold]/help[/] for the palette)")
            else:
                do_ask(raw)
        except Exception as exc:  # noqa: BLE001 — a CLI nunca morre por uma falha de chamada
            console.print(f"[bold red]error:[/] {exc}")


if __name__ == "__main__":
    main()
