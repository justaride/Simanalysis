"""Utility XML snippets for tests."""

from __future__ import annotations

from textwrap import dedent


def basic_interaction(
    tuning_id: str = "Example.Tuning",
    *,
    loot_value: str | None = None,
    test_value: str | None = None,
) -> str:
    """Return a simple interaction tuning XML snippet."""

    loot = loot_value or f"{tuning_id}.Loot"
    test = test_value or f"{tuning_id}.Test"
    return dedent(
        f"""
        <I n='{tuning_id}'>
            <T n='loot'>
                <T>{loot}</T>
            </T>
            <L n='tests'>
                <T>{test}</T>
            </L>
        </I>
        """
    ).strip()


def loot_variation(tuning_id: str, loot_value: str) -> str:
    """Return a tuning XML snippet with a single loot entry."""

    return dedent(
        f"""
        <I n='{tuning_id}'>
            <T n='loot'>
                <T>{loot_value}</T>
            </T>
        </I>
        """
    ).strip()
