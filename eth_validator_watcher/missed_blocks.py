import functools
from typing import Optional

from prometheus_client import Counter

from eth_validator_watcher.utils import NB_SLOT_PER_EPOCH

from .beacon import Beacon
from .models import DataBlock, SlotWithStatus

print = functools.partial(print, flush=True)


def handle_missed_block_detection(
    beacon: Beacon,
    data_block: DataBlock,
    previous_slot: Optional[int],
    missed_block_proposals_counter: Counter,
    our_pubkeys: set[str],
) -> int:
    """Handle missed block proposals detection

    Print log each time a block is proposed.
    Update prometheus probe for our public keys which did not proposed a block

    Returns the current slot.

    beacon       : Beacon
    data_block   : Data value of a beacon chain block
    previous_slot: Previous slot (Optional)
    missed_block_proposals_counter: Prometheus counter
    our_pubkeys: Set of our validators public keys
    """
    current_slot = data_block.slot

    previous_slot = current_slot - 1 if previous_slot is None else previous_slot

    slots_with_status = [
        SlotWithStatus(number=slot, missed=True)
        for slot in range(previous_slot + 1, current_slot)
    ] + [SlotWithStatus(number=current_slot, missed=False)]

    for slot_with_status in slots_with_status:
        epoch = slot_with_status.number // NB_SLOT_PER_EPOCH

        proposer_duties = beacon.get_proposer_duties(epoch)

        # Get proposer public key for this slot
        proposer_duties_data = proposer_duties.data

        # In `data` list, items seem to be ordered by slot.
        # However, there is no specification for that, so it is wiser to
        # iterate on the list
        proposer_pubkey = next(
            (
                proposer_duty_data.pubkey
                for proposer_duty_data in proposer_duties_data
                if proposer_duty_data.slot == slot_with_status.number
            )
        )

        # Check if the validator that has to propose is ours
        is_our_validator = proposer_pubkey in our_pubkeys
        positive_emoji = "✨" if is_our_validator else "✅"
        negative_emoji = "❌" if is_our_validator else "💩"
        birthday = " - 🎂" if current_slot % NB_SLOT_PER_EPOCH == 0 else ""

        emoji, proposed_or_missed = (
            (negative_emoji, "missed  ")
            if slot_with_status.missed
            else (positive_emoji, "proposed")
        )

        short_proposer_pubkey = proposer_pubkey[:10]

        message = (
            f"{emoji} {'Our ' if is_our_validator else '    '}validator "
            f"{short_proposer_pubkey} {proposed_or_missed} block at epoch {epoch} - "
            f"slot {slot_with_status.number} {emoji} - 🔑 {len(our_pubkeys)} keys "
            f"watched{birthday}"
        )

        print(message)

        if is_our_validator and slot_with_status.missed:
            missed_block_proposals_counter.inc()

    return current_slot
