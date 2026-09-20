from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict, Field


class Item(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    name: str
    price: float
    qty: int = 1
    veg: bool | None = None
    cart_item: dict | None = None   # exact entry for update_food_cart's cartItems

class Candidate(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    restaurant_id: str
    restaurant_name: str
    items: list[Item]
    eta: str | None = None


class Quote(BaseModel):
    restaurant: str
    items: list[str]
    item_total: float
    delivery_fee: float
    taxes_and_charges: float
    other_adjustments: float   # negative = discount applied, positive = extra fee
    final_total: float
    eta: str | None = None
    notes: list[str] = Field(default_factory=list)  # any offer/discount lines Swiggy printed


@dataclass
class Session:
    budget: float = 0.0
    address_id: str = ""
    options: dict = field(default_factory=dict)   # option number -> (Candidate, Quote)

SESSION = Session()
