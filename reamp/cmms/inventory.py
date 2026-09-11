"""
REAMP CMMS Spare Parts Inventory Manager.
Tracks warehouse stock, handles reservation on work order drafting/approval,
deducts consumption upon physical execution, and generates reorder point alerts.
"""

from typing import Dict, Any, List, Optional
import copy
from reamp.cmms.models import SparePart, SparePartUsage


class InventoryManager:
    """
    Manages spare parts catalog, reservation lifecycles, physical stock deduction,
    and supplier procurement threshold monitoring.
    """

    def __init__(self, initial_catalog: Optional[List[SparePart]] = None) -> None:
        self._catalog: Dict[str, SparePart] = {}
        if initial_catalog:
            for part in initial_catalog:
                self.register_part(part)

    def register_part(self, part: SparePart) -> None:
        """Adds or updates a spare part in the warehouse catalog."""
        self._catalog[part.part_sku] = copy.deepcopy(part)

    def get_part(self, part_sku: str) -> Optional[SparePart]:
        """Retrieves a copy of the spare part record."""
        part = self._catalog.get(part_sku)
        return copy.deepcopy(part) if part else None

    def list_parts(self) -> List[SparePart]:
        """Returns all registered spare parts."""
        return [copy.deepcopy(p) for p in self._catalog.values()]

    def check_availability(self, required_skus: List[str]) -> Dict[str, bool]:
        """
        Evaluates availability for a list of part SKUs.
        Returns a mapping of sku -> bool indicating whether at least 1 unit is unreserved.
        """
        availability = {}
        for sku in required_skus:
            part = self._catalog.get(sku)
            if not part:
                availability[sku] = False
            else:
                availability[sku] = part.available_quantity > 0
        return availability

    def reserve_parts(self, requirements: Dict[str, int]) -> bool:
        """
        Tentatively reserves specified quantities of parts for a work order.
        Atomic operation: if any SKU has insufficient available quantity,
        no reservations are made and ValueError is raised.
        """
        # 1. Validation pass
        for sku, qty in requirements.items():
            if qty <= 0:
                continue
            part = self._catalog.get(sku)
            if not part:
                raise ValueError(f"Spare part SKU '{sku}' not found in inventory catalog.")
            if part.available_quantity < qty:
                raise ValueError(
                    f"Insufficient stock for SKU '{sku}': requested {qty}, "
                    f"available {part.available_quantity} (on hand: {part.quantity_on_hand}, "
                    f"reserved: {part.quantity_reserved})."
                )

        # 2. Reservation pass
        for sku, qty in requirements.items():
            if qty > 0:
                self._catalog[sku].quantity_reserved += qty
        return True

    def release_reservation(self, reserved: Dict[str, int]) -> None:
        """Releases reserved quantities back to available stock."""
        for sku, qty in reserved.items():
            if qty <= 0:
                continue
            part = self._catalog.get(sku)
            if part:
                part.quantity_reserved = max(0, part.quantity_reserved - qty)

    def consume_parts(self, consumption: Dict[str, int]) -> List[SparePartUsage]:
        """
        Permanently consumes parts from warehouse stock upon maintenance completion.
        Decrements both quantity_on_hand and quantity_reserved.
        Returns list of SparePartUsage records with audited unit costs.
        """
        usages: List[SparePartUsage] = []
        for sku, qty in consumption.items():
            if qty <= 0:
                continue
            part = self._catalog.get(sku)
            if not part:
                raise ValueError(f"Cannot consume unknown part SKU '{sku}'.")
            if part.quantity_on_hand < qty:
                raise ValueError(
                    f"Cannot consume {qty} units of SKU '{sku}'; only {part.quantity_on_hand} on hand."
                )

            part.quantity_on_hand -= qty
            part.quantity_reserved = max(0, part.quantity_reserved - qty)

            usages.append(SparePartUsage(
                part_sku=sku,
                quantity=qty,
                unit_cost_usd=part.unit_cost_usd
            ))
        return usages

    def restock(self, part_sku: str, quantity: int) -> None:
        """Replenishes warehouse inventory for the given SKU."""
        if quantity <= 0:
            raise ValueError("Restock quantity must be positive.")
        part = self._catalog.get(part_sku)
        if not part:
            raise ValueError(f"Cannot restock unregistered SKU '{part_sku}'.")
        part.quantity_on_hand += quantity

    def check_reorder_alerts(self) -> List[Dict[str, Any]]:
        """
        Identifies all parts whose available quantity has breached reorder safety thresholds.
        """
        alerts = []
        for sku, part in self._catalog.items():
            if part.available_quantity <= part.reorder_threshold:
                alerts.append({
                    "part_sku": sku,
                    "name": part.name,
                    "category": part.category,
                    "available_quantity": part.available_quantity,
                    "quantity_on_hand": part.quantity_on_hand,
                    "reorder_threshold": part.reorder_threshold,
                    "lead_time_days": part.lead_time_days,
                    "unit_cost_usd": part.unit_cost_usd,
                    "reorder_recommended_quantity": max(5, part.reorder_threshold * 3)
                })
        return alerts
