"""
backend/utils/logger.py
========================
Structured, colorized logging for all agents and orchestrator.
Uses loguru for production-quality structured output.
"""

import sys
from loguru import logger
from pathlib import Path


def setup_logger(run_id: str, log_dir: Path | None = None) -> None:
    """Configure loguru with structured format and optional file sink."""
    logger.remove()

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        f"<cyan>run={run_id}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    )

    # Console sink
    logger.add(sys.stderr, format=fmt, level="DEBUG", colorize=True, enqueue=True)

    # File sink
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / f"{run_id}.log",
            format=fmt,
            level="DEBUG",
            rotation="50 MB",
            retention="7 days",
            compression="gz",
            enqueue=True,
        )

    logger.info(f"Logger initialized for run_id={run_id}")


__all__ = ["logger", "setup_logger"]
