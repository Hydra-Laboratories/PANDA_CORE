"""Protocol command for pausing execution."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from ..registry import protocol_command

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..protocol import ProtocolContext


@protocol_command("pause")
def pause(
    context: ProtocolContext,
    message: str = "Protocol paused",
    reason: str = "user",
    labware_key: Optional[str] = None,
    capacity_ul: Optional[float] = None,
) -> None:
    """Pause protocol execution.

    Args:
        context: Runtime protocol context.
        message: Message displayed to the operator.
        reason: One of "user", "refill", or "tip_swap".
        labware_key: Labware to refill (only used when reason="refill").
        capacity_ul: Capacity for full refill (only used when reason="refill").
    """
    context.logger.info("PAUSE: %s (reason=%s)", message, reason)
    print(message)

    if reason == "refill" and labware_key is not None:
        _handle_refill(context, labware_key, capacity_ul)
    elif reason == "tip_swap":
        print("Press Enter when new rack is loaded...")
        input()
    else:
        input("Press Enter to continue...")

    context.logger.info("RESUME: continuing after pause")


def _handle_refill(
    context: ProtocolContext,
    labware_key: str,
    capacity_ul: Optional[float],
) -> None:
    """Prompt for refill volume and update the volume tracker."""
    response = input(
        "Enter volume added (uL), or press Enter for full refill: "
    )

    if context.volume_tracker is None:
        return

    if response.strip() == "":
        refill_volume = capacity_ul if capacity_ul is not None else 100_000.0
        context.volume_tracker.refill(labware_key, None, refill_volume)
    else:
        volume = float(response.strip())
        context.volume_tracker.refill(labware_key, None, volume)
