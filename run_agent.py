#!/usr/bin/env python3
"""
QuantResearch Agent — Runner principal
======================================
Executa o agente de pesquisa quantitativa via Anthropic API (Claude).
Os scripts em scripts/ são expostos como ferramentas (tool_use) para o modelo.

Uso:
    python run_agent.py                          # modo interativo
    python run_agent.py "analise BTC/USDT 90d"  # query direta
    python run_agent.py --file query.txt         # query de arquivo

Variáveis de ambiente necessárias (.env):
    ANTHROPIC_API_KEY   — chave da API Anthropic
    Demais chaves opcionais: ver .env.example
"""

import os, sys, json, argparse, textwrap
from pathlib import Path
from datetime import datetime

try:
    import anthropic
except ImportError:
    print("[ERRO] anthropic não instalado. Execute: pip install anthropic")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv opcional; exportar variáveis manualmente funciona também

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ROOT          = Path(__file__).parent
SCRIPTS_DIR   = ROOT / "scripts"
REPORTS_DIR   = ROOT / "reports"
DATA_DIR      = ROOT / "data"
MODEL         = os.getenv("QUANT_MODEL", "claude-opus-4-5")
MAX_TOKENS    = int(os.getenv("QUANT_MAX_TOKENS", "4096"))
MAX_TOOL_ITER = int(os.getenv("QUANT_MAX_TOOL_ITER", "15"))

REPORTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# System Prompt — carregado do SKILL.md
# ---------------------------------------------------------------------------
def load_system_prompt() -> str:
    skill_path = ROOT / "SKILL.md"
    if skill_path.exists():
        raw = skill_path.read_text(encoding="utf-8")
        # Remove frontmatter YAML se presente
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            raw = parts[2] if len(parts) >= 3 else raw
        return raw.strip()
    return (
        "Você é o QuantResearch Agent, especialista em pesquisa quantitativa "
        "de mercados financeiros, criptoativos e mercados de predição."
    )

SYSTEM_PROMPT = load_system_prompt() + f"""

---
**Contexto de execução local (IDE)**
- Data/hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- Diretório de dados: {DATA_DIR}
- Diretório de relatórios: {REPORTS_DIR}
- Scripts disponíveis como ferramentas: data_fetcher, backtest_engine, model_builder, report_generator

Ao executar ferramentas, informe o usuário sobre o progresso.
Salve relatórios em {REPORTS_DIR}/ e dados em {DATA_DIR}/.
"""

# ---------------------------------------------------------------------------
# Ferramentas (tool_use) — wrappers sobre os scripts
# ---------------------------------------------------------------------------
TOOLS = [
    {
        "name": "fetch_market_data",
        "description": (
            "Busca dados históricos de mercado. Suporta: ações (Yahoo Finance), "
            "cripto (CCXT/Binance), Kalshi (contratos de predição), Polymarket. "
            "Retorna caminho do arquivo Parquet salvo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol":     {"type": "string",  "description": "Ex: BTC/USDT, AAPL, BTCUSDT"},
                "source":     {"type": "string",  "enum": ["yfinance", "ccxt", "kalshi", "polymarket"], "description": "Fonte de dados"},
                "interval":   {"type": "string",  "description": "Ex: 1d, 1h, 15m"},
                "days":       {"type": "integer", "description": "Número de dias históricos"},
                "output_path":{"type": "string",  "description": "Caminho de saída (opcional)"},
            },
            "required": ["symbol", "source"],
        },
    },
    {
        "name": "run_backtest",
        "description": (
            "Executa backtest vetorizado de uma estratégia. Suporta estratégias: "
            "momentum, mean_reversion, ml_signal, regime_based. "
            "Retorna métricas (Sharpe, drawdown, CAGR) e gráfico HTML."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data_path":  {"type": "string", "description": "Caminho do Parquet com dados OHLCV"},
                "strategy":   {"type": "string", "enum": ["momentum", "mean_reversion", "ml_signal", "regime_based"]},
                "params":     {"type": "object", "description": "Parâmetros da estratégia (ex: {'window':20, 'threshold':1.5})"},
                "output_path":{"type": "string", "description": "Caminho para salvar resultado HTML"},
            },
            "required": ["data_path", "strategy"],
        },
    },
    {
        "name": "build_model",
        "description": (
            "Treina modelo de ML para geração de sinais de trading. "
            "Algoritmos: gradient_boosting (padrão), random_forest, hmm_regime. "
            "Salva modelo em disco e retorna métricas de validação."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "data_path":    {"type": "string",  "description": "Caminho do Parquet com dados"},
                "algorithm":    {"type": "string",  "enum": ["gradient_boosting", "random_forest", "hmm_regime"], "default": "gradient_boosting"},
                "target":       {"type": "string",  "enum": ["direction", "return_5d", "return_1d"], "default": "direction"},
                "n_splits":     {"type": "integer", "description": "Número de folds walk-forward", "default": 5},
                "output_path":  {"type": "string",  "description": "Caminho para salvar modelo .pkl"},
                "feature_importance": {"type": "boolean", "default": True},
            },
            "required": ["data_path"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Gera relatório HTML completo com tema dark. Combina dados de mercado, "
            "resultados de backtest e análise de modelos em um documento navegável."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":        {"type": "string",  "description": "Título do relatório"},
                "sections":     {"type": "array",   "items": {"type": "string"}, "description": "Seções a incluir"},
                "data_paths":   {"type": "array",   "items": {"type": "string"}, "description": "Lista de arquivos de dados/resultados"},
                "output_path":  {"type": "string",  "description": "Caminho de saída .html"},
                "include_charts":{"type": "boolean", "default": True},
            },
            "required": ["title"],
        },
    },
    {
        "name": "run_script",
        "description": (
            "Executa um script Python arbitrário do diretório scripts/ com argumentos. "
            "Use para operações avançadas não cobertas pelas outras ferramentas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "script":  {"type": "string", "enum": ["data_fetcher", "backtest_engine", "model_builder", "report_generator"]},
                "args":    {"type": "string", "description": "Argumentos CLI (ex: '--symbol BTC/USDT --days 90')"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "read_file",
        "description": "Lê um arquivo de dados, resultado ou relatório do disco.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Caminho do arquivo"},
                "lines": {"type": "integer", "description": "Número de linhas (para arquivos grandes)", "default": 100},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_files",
        "description": "Lista arquivos no diretório de dados ou relatórios.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "enum": ["data", "reports", "scripts", "."], "default": "data"},
                "pattern":   {"type": "string", "description": "Filtro glob (ex: '*.parquet')", "default": "*"},
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Execução de ferramentas
# ---------------------------------------------------------------------------
def execute_tool(name: str, inputs: dict) -> str:
    """Executa a ferramenta e retorna resultado como string."""
    import subprocess, glob

    print(f"  🔧 {name}({json.dumps(inputs, ensure_ascii=False)[:120]}...)")

    try:
        if name == "fetch_market_data":
            script = SCRIPTS_DIR / "data_fetcher.py"
            sym    = inputs["symbol"]
            src    = inputs["source"]
            days   = inputs.get("days", 90)
            intvl  = inputs.get("interval", "1d")
            out    = inputs.get("output_path", str(DATA_DIR / f"{sym.replace('/','_')}_{src}_{days}d.parquet"))
            result = subprocess.run(
                [sys.executable, str(script),
                 "--symbol", sym, "--source", src,
                 "--days", str(days), "--interval", intvl,
                 "--output", out],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return f"Dados salvos em: {out}\n{result.stdout[-500:]}"
            else:
                return f"Erro ao buscar dados:\n{result.stderr[-500:]}"

        elif name == "run_backtest":
            script = SCRIPTS_DIR / "backtest_engine.py"
            out    = inputs.get("output_path", str(REPORTS_DIR / f"backtest_{datetime.now():%Y%m%d_%H%M%S}.html"))
            params = json.dumps(inputs.get("params", {}))
            result = subprocess.run(
                [sys.executable, str(script),
                 "--data", inputs["data_path"],
                 "--strategy", inputs["strategy"],
                 "--params", params,
                 "--output", out],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                return f"Backtest concluído. Relatório: {out}\n{result.stdout[-800:]}"
            else:
                return f"Erro no backtest:\n{result.stderr[-500:]}"

        elif name == "build_model":
            script = SCRIPTS_DIR / "model_builder.py"
            out    = inputs.get("output_path", str(DATA_DIR / f"model_{datetime.now():%Y%m%d_%H%M%S}.pkl"))
            result = subprocess.run(
                [sys.executable, str(script),
                 "--data", inputs["data_path"],
                 "--algorithm", inputs.get("algorithm", "gradient_boosting"),
                 "--target",    inputs.get("target", "direction"),
                 "--n-splits",  str(inputs.get("n_splits", 5)),
                 "--output",    out],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                return f"Modelo salvo em: {out}\n{result.stdout[-800:]}"
            else:
                return f"Erro ao treinar modelo:\n{result.stderr[-500:]}"

        elif name == "generate_report":
            script = SCRIPTS_DIR / "report_generator.py"
            out    = inputs.get("output_path", str(REPORTS_DIR / f"report_{datetime.now():%Y%m%d_%H%M%S}.html"))
            data_args = []
            for p in inputs.get("data_paths", []):
                data_args += ["--data", p]
            result = subprocess.run(
                [sys.executable, str(script),
                 "--title", inputs["title"],
                 "--output", out] + data_args,
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return f"Relatório gerado: {out}\n{result.stdout[-500:]}"
            else:
                return f"Erro ao gerar relatório:\n{result.stderr[-500:]}"

        elif name == "run_script":
            script = SCRIPTS_DIR / f"{inputs['script']}.py"
            args   = inputs.get("args", "").split()
            result = subprocess.run(
                [sys.executable, str(script)] + args,
                capture_output=True, text=True, timeout=300
            )
            out_text = result.stdout[-1000:] if result.stdout else ""
            err_text = result.stderr[-500:]  if result.stderr else ""
            return f"Exit code: {result.returncode}\n{out_text}\n{err_text}".strip()

        elif name == "read_file":
            path  = Path(inputs["path"])
            lines = inputs.get("lines", 100)
            if not path.exists():
                return f"Arquivo não encontrado: {path}"
            if path.suffix == ".parquet":
                try:
                    import pandas as pd
                    df = pd.read_parquet(path)
                    return f"Shape: {df.shape}\nColunas: {list(df.columns)}\n\n{df.head(10).to_string()}"
                except Exception as e:
                    return f"Erro ao ler parquet: {e}"
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                all_lines = content.split("\n")
                return "\n".join(all_lines[:lines]) + (f"\n... (+{len(all_lines)-lines} linhas)" if len(all_lines) > lines else "")

        elif name == "list_files":
            directory = inputs.get("directory", "data")
            pattern   = inputs.get("pattern", "*")
            dirs = {"data": DATA_DIR, "reports": REPORTS_DIR, "scripts": SCRIPTS_DIR, ".": ROOT}
            target = dirs.get(directory, ROOT)
            files  = sorted(target.glob(pattern))
            if not files:
                return f"Nenhum arquivo encontrado em {target} com padrão '{pattern}'"
            lines = [f"{f.name}  ({f.stat().st_size/1024:.1f}KB)  {datetime.fromtimestamp(f.stat().st_mtime):%Y-%m-%d %H:%M}" for f in files]
            return "\n".join(lines)

        else:
            return f"Ferramenta desconhecida: {name}"

    except subprocess.TimeoutExpired:
        return f"Timeout ao executar {name} (limite: 600s)"
    except Exception as e:
        return f"Erro inesperado em {name}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Loop do agente
# ---------------------------------------------------------------------------
def run_agent(query: str, verbose: bool = True) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERRO] ANTHROPIC_API_KEY não definida. Configure em .env ou exporte a variável.")
        sys.exit(1)

    client   = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": query}]

    if verbose:
        print(f"\n{'='*60}")
        print(f"🤖 QuantResearch Agent  |  {MODEL}")
        print(f"{'='*60}")
        print(f"📋 Query: {query}\n")

    iteration = 0
    final_text = ""

    while iteration < MAX_TOOL_ITER:
        iteration += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Coletar texto e tool_use deste turno
        tool_calls   = []
        text_content = []

        for block in response.content:
            if block.type == "text":
                text_content.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        if text_content and verbose:
            print("\n🤖 Agente:")
            for t in text_content:
                print(textwrap.fill(t, width=100, subsequent_indent="  "))

        # Adicionar resposta do assistente ao histórico
        messages.append({"role": "assistant", "content": response.content})

        # Se parou (end_turn ou max_tokens sem tools), sai
        if response.stop_reason in ("end_turn", "max_tokens") and not tool_calls:
            final_text = "\n".join(text_content)
            break

        # Executar ferramentas
        if tool_calls:
            tool_results = []
            for tc in tool_calls:
                result_str = execute_tool(tc.name, tc.input)
                if verbose:
                    preview = result_str[:300].replace("\n", " ")
                    print(f"  ✅ Resultado: {preview}...")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": result_str,
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = "\n".join(text_content)
            break

    if iteration >= MAX_TOOL_ITER:
        print(f"\n⚠️  Limite de {MAX_TOOL_ITER} iterações atingido.")

    return final_text


# ---------------------------------------------------------------------------
# Interface CLI / interativa
# ---------------------------------------------------------------------------
def interactive_mode():
    print("\n" + "="*60)
    print("  🔬 QuantResearch Agent — Modo Interativo")
    print("  Digite 'exit' ou Ctrl+C para sair")
    print("="*60 + "\n")
    print("Exemplos de comandos:")
    print("  • analise o BTC/USDT nos últimos 90 dias")
    print("  • faça backtest de estratégia momentum para AAPL")
    print("  • crie modelo ML para previsão de direção do mercado")
    print("  • gere relatório completo de crypto top 5\n")

    while True:
        try:
            query = input("📝 Query: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nAté logo!")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", "sair"):
            print("Até logo!")
            break

        run_agent(query)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="QuantResearch Agent — Pesquisa quantitativa via Claude API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Exemplos:
              python run_agent.py
              python run_agent.py "analise BTC/USDT 90d com backtest momentum"
              python run_agent.py --file queries/morning_brief.txt
              python run_agent.py --model claude-sonnet-4-5 "quick analysis AAPL"
        """)
    )
    parser.add_argument("query",   nargs="?",  help="Query para o agente (omitir para modo interativo)")
    parser.add_argument("--file",  "-f",        help="Arquivo .txt com a query")
    parser.add_argument("--model", "-m",        help=f"Modelo Claude (padrão: {MODEL})")
    parser.add_argument("--quiet", "-q",        action="store_true", help="Saída mínima")
    args = parser.parse_args()

    if args.model:
        global MODEL
        MODEL = args.model

    if args.file:
        query = Path(args.file).read_text(encoding="utf-8").strip()
        run_agent(query, verbose=not args.quiet)
    elif args.query:
        run_agent(args.query, verbose=not args.quiet)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
