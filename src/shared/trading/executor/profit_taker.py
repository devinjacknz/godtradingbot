import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProfitTakingState:
    sold_2x: bool = False
    sold_3x: bool = False
    sold_5x: bool = False
    total_sold: Decimal = Decimal("0")
    remaining_position: Decimal = Decimal("0")


class StagedProfitTaker:
    def __init__(self):
        self.states: Dict[str, ProfitTakingState] = {}

    def get_state(self, position_id: str) -> ProfitTakingState:
        if position_id not in self.states:
            self.states[position_id] = ProfitTakingState()
        return self.states[position_id]

    def calculate_sell_amount(
        self,
        position_id: str,
        entry_price: Decimal,
        current_price: Decimal,
        position_size: Decimal,
    ) -> Optional[Decimal]:
        try:
            state = self.get_state(position_id)
            if state.total_sold >= position_size:
                return None

            price_multiple = current_price / entry_price
            remaining = position_size - state.total_sold

            if price_multiple >= Decimal("5.0") and not state.sold_5x:
                sell_amount = position_size * Decimal("0.20")
                state.sold_5x = True
                state.total_sold += sell_amount
                state.remaining_position = remaining - sell_amount
                return min(sell_amount, remaining)

            if price_multiple >= Decimal("3.0") and not state.sold_3x:
                sell_amount = position_size * Decimal("0.25")
                state.sold_3x = True
                state.total_sold += sell_amount
                state.remaining_position = remaining - sell_amount
                return min(sell_amount, remaining)

            if price_multiple >= Decimal("2.0") and not state.sold_2x:
                sell_amount = position_size * Decimal("0.20")
                state.sold_2x = True
                state.total_sold += sell_amount
                state.remaining_position = remaining - sell_amount
                return min(sell_amount, remaining)

            return None

        except Exception as e:
            logger.error(f"Error calculating sell amount: {str(e)}")
            return None

    def reset_state(self, position_id: str) -> None:
        if position_id in self.states:
            del self.states[position_id]
