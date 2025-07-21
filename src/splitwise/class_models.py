from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


@dataclass
class DependencySplitwiseDeps:
    """Dependencies for splitwise structured data extractor and bill splitter."""
    image_bytes: bytes
    user_description: str
    feedback: Optional[str] = None
    previous_output: Optional[str] = None

class FeeItem(BaseModel):
    """Individual fee or discount item."""
    name: str
    amount: float
    category: str  # "Tax", "Delivery Fee", or "Tip"

class FeeCategorization(BaseModel):
    """Categorized fees before aggregation."""
    tax_items: List[FeeItem]
    delivery_items: List[FeeItem] 
    tip_items: List[FeeItem]
    
    def calculate_totals(self) -> Dict[str, float]:
        """Calculate total for each category."""
        return {
            "Tax": sum(item.amount for item in self.tax_items),
            "Delivery Fee": sum(item.amount for item in self.delivery_items),
            "Tip": sum(item.amount for item in self.tip_items)
        }

class SplitwiseFormattedOutput(BaseModel):
    """Structured output format for splitwise bill processing."""
    persons: Dict[str, str]  # abbr -> full name
    items: List[Dict[str, Any]]  # [{"name": str, "price": float}]
    fees: Dict[str, float]  # {"Tax": float, "Delivery Fee": float, "Tip": float}
    item_shares: Dict[str, List[str]]  # item_name -> [abbr1, abbr2, ...]
    raw_fees: FeeCategorization  # Keep original fee breakdown for transparency
