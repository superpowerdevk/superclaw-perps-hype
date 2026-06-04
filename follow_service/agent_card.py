"""
Curated-agent info card (SuperClaw).

Fetches the public Moss agent metadata endpoint and formats the metrics users
ask for before committing capital: ROI, overall PnL, max profit, max drawdown,
win rate, profit factor, trade count, status, days running.

Drawdown and win rate are ALWAYS shown alongside ROI — a headline ROI without
the downside is the kind of cherry-picked stat that misleads. This is not
investment advice; the user bears all risk.

Field mapping confirmed against the live endpoint:
  performance.roi, performance.pnl, performance.max_profit_percent,
  performance.max_drawdown, performance.overall_win_rate,
  performance.profit_factor, performance.total_trades, bot.status,
  bot.running_days, bot.name_i18n / prompt.brief_i18n (en|zh).
"""

import logging

from . import config as cfg
from .moss_client import MossClient

logger = logging.getLogger("follow_agent.agent_card")


def _num(d: dict, *path, default="-"):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur not in (None, "") else default


def fetch_card(lang: str = "en") -> dict | None:
    """Fetch + map agent metrics. Returns a flat dict, or None on failure."""
    moss_cfg = cfg.get_moss_source_config()
    agent_id = str(moss_cfg.get("agent_id", "") or "").strip()
    base_url = str(moss_cfg.get("base_url", "") or "").strip()
    if not agent_id or not base_url:
        logger.error("agent-info: missing agent_id or base_url")
        return None
    try:
        client = MossClient(base_url=base_url, agent_id=agent_id, private_key=cfg.get("private_key", ""))
        data = client.get_agent_info()
    except Exception as exc:  # noqa: BLE001
        logger.error("agent-info fetch failed: %s", exc)
        return None
    if not isinstance(data, dict):
        return None

    bot = data.get("bot", {}) if isinstance(data.get("bot"), dict) else {}
    perf = data.get("performance", {}) if isinstance(data.get("performance"), dict) else {}
    acct = data.get("account", {}) if isinstance(data.get("account"), dict) else {}
    lang = "zh" if lang == "zh" else "en"

    name = _num(bot, "name_i18n", lang) or bot.get("name", agent_id)
    brief = _num(data, "prompt", "brief_i18n", lang)

    return {
        "agent_id": agent_id,
        "name": name,
        "brief": brief,
        "status": bot.get("status", "-"),
        "running_days": bot.get("running_days", "-"),
        "roi_pct": perf.get("roi", "-"),
        "pnl": perf.get("pnl", acct.get("realized_pnl", "-")),
        "max_profit_pct": perf.get("max_profit_percent", "-"),
        "max_drawdown_pct": perf.get("max_drawdown", "-"),
        "win_rate_pct": perf.get("overall_win_rate", "-"),
        "profit_factor": perf.get("profit_factor", "-"),
        "total_trades": perf.get("total_trades", "-"),
        "liquidation_count": perf.get("liquidation_count", "-"),
    }


def render_text(card: dict, lang: str = "en") -> str:
    """Plain-text card for CLI / Bot output. Drawdown + win rate always shown."""
    if lang == "zh":
        lines = [
            f"Agent：{card['name']}  ({card['status']}，运行 {card['running_days']} 天)",
        ]
        if card.get("brief") and card["brief"] != "-":
            lines.append(f"策略：{card['brief']}")
        lines += [
            "",
            f"  ROI(收益率)      : {card['roi_pct']}%",
            f"  累计盈亏          : {card['pnl']} USDC",
            f"  历史最大盈利      : {card['max_profit_pct']}%",
            f"  最大回撤          : {card['max_drawdown_pct']}%   ← 风险",
            f"  胜率              : {card['win_rate_pct']}%",
            f"  盈亏比 / 交易数    : {card['profit_factor']} / {card['total_trades']}",
            f"  爆仓次数          : {card['liquidation_count']}",
            "",
            "注意：官方为你挑选 Agent 不构成投资建议，也不保证收益；过往业绩不代表未来表现，盈亏与风险由你自担。",
        ]
        return "\n".join(lines)

    lines = [
        f"Agent: {card['name']}  ({card['status']}, running {card['running_days']} days)",
    ]
    if card.get("brief") and card["brief"] != "-":
        lines.append(f"Strategy: {card['brief']}")
    lines += [
        "",
        f"  ROI               : {card['roi_pct']}%",
        f"  Overall PnL       : {card['pnl']} USDC",
        f"  Max profit        : {card['max_profit_pct']}%",
        f"  Max drawdown      : {card['max_drawdown_pct']}%   <- risk",
        f"  Win rate          : {card['win_rate_pct']}%",
        f"  Profit factor / trades : {card['profit_factor']} / {card['total_trades']}",
        f"  Liquidations      : {card['liquidation_count']}",
        "",
        "Note: the platform selecting an agent for you is not investment advice and "
        "guarantees no profit; past performance does not predict future results, and "
        "you bear all trading risk.",
    ]
    return "\n".join(lines)
