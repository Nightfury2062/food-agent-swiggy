from dataclasses import dataclass, field
from pydantic import BaseModel, ConfigDict


class Item(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    id: str
    name: str
    price: float
    qty: int = 1
    veg: bool | None = None


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
    notes: list[str] = []      # any offer/discount lines Swiggy printed


@dataclass
class Session:
    budget: float = 0.0
    options: dict = field(default_factory=dict)   # option number -> (Candidate, Quote)


SESSION = Session()