"""
OmniEconomy v1.0 + TraitMarketplace (MVS)

Sole economy path.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

try:
    from backend.economy.ledger import credit, balance
except Exception:
    credit = lambda *a, **k: None
    balance = lambda a: 0.0


class TraitMarketplace:
    """Real trait marketplace (MVS only)."""
    def __init__(self):
        self.listings: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_trait(self, seller_id: str, trait_name: str, price: float, value: float):
        if trait_name not in self.listings:
            self.listings[trait_name] = {}
        self.listings[trait_name][seller_id] = {"price": price, "value": value}

    def buy_trait(self, buyer_id: str, seller_id: str, trait_name: str, economy: "OmniEconomy", mind: "OmniMind" = None):
        try:
            if trait_name not in self.listings or seller_id not in self.listings.get(trait_name, {}):
                return False
            listing = self.listings[trait_name][seller_id]
            price = float(listing.get("price", 0))
            if economy.get_balance(buyer_id) < price:
                return False
            if not economy.transfer(buyer_id, seller_id, price, reason=f"buy_trait:{trait_name}"):
                return False
            # Trait boost intentionally lightweight in MVS (actual evolution happens via DNA)
            if mind and hasattr(mind, "agents"):
                # best effort
                pass
            self.listings[trait_name].pop(seller_id, None)
            if not self.listings.get(trait_name):
                self.listings.pop(trait_name, None)
            return True
        except Exception:
            return False  # failsafe - never crash economy participation


@dataclass
class OmniEconomy:
    balances: Dict[str, float] = field(default_factory=dict)
    trait_marketplace: TraitMarketplace = field(default_factory=TraitMarketplace)

    def reward(self, agent_id: str, amount: float, reason: str = ""):
        if amount > 0:
            try:
                credit(agent_id, amount, reason=reason or "mvs_reward", source="omni_economy")
            except Exception:
                self.balances[agent_id] = self.get_balance(agent_id) + amount

    def get_balance(self, agent_id: str) -> float:
        try:
            return balance(agent_id)
        except Exception:
            return self.balances.get(agent_id, 0.0)

    def transfer(self, from_id: str, to_id: str, amount: float, reason: str = "") -> bool:
        if self.get_balance(from_id) < amount:
            return False
        self.balances[from_id] = self.get_balance(from_id) - amount
        self.balances[to_id] = self.get_balance(to_id) + amount
        return True

    def trade_trait(self, from_id: str, to_id: str, trait: str, price: float) -> bool:
        return self.trait_marketplace.buy_trait(to_id, from_id, trait, self, None)  # simplified


class MarketplaceAutonomy:
    """Autonomous Trait Marketplace Participation.
    Agents buy/sell traits based on their fitness and balance.
    This creates economic evolution and specialization.
    """

    def __init__(self, economy: "OmniEconomy", mind: "OmniMind"):
        self.economy = economy
        self.mind = mind

    def maybe_buy_traits(self, agent_id: str, dna: OmniDNA, fitness: float):
        try:
            from oss.observability.metrics import (
                record_marketplace_failure,
                record_marketplace_success,
            )
        except ImportError:
            record_marketplace_failure = record_marketplace_success = lambda *_a, **_k: None

        try:
            balance = self.economy.get_balance(agent_id)
            traits = dna.get_traits()

            if fitness < 0.5 and balance > 50.0:
                needed = [t for t, v in traits.items() if v < 0.4]
                for trait_name in needed:
                    listings = getattr(self.economy, 'trait_marketplace', None)
                    if listings and hasattr(listings, 'listings'):
                        listings_dict = listings.listings.get(trait_name, {})
                        if listings_dict:
                            seller_id = list(listings_dict.keys())[0]
                            self.economy.trait_marketplace.buy_trait(
                                buyer_id=agent_id,
                                seller_id=seller_id,
                                trait_name=trait_name,
                                economy=self.economy,
                                mind=self.mind,
                            )
                            record_marketplace_success("buy")
                            break
        except Exception:
            record_marketplace_failure("buy")

    def maybe_list_traits(self, agent_id: str, dna: OmniDNA, fitness: float):
        try:
            from oss.observability.metrics import (
                record_marketplace_failure,
                record_marketplace_success,
            )
        except ImportError:
            record_marketplace_failure = record_marketplace_success = lambda *_a, **_k: None

        try:
            balance = self.economy.get_balance(agent_id)
            traits = dna.get_traits()

            if balance < 20.0 and fitness > 0.6:
                strong = [t for t, v in traits.items() if v > 0.8]
                for trait_name in strong:
                    if hasattr(self.economy, 'trait_marketplace'):
                        self.economy.trait_marketplace.list_trait(
                            seller_id=agent_id,
                            trait_name=trait_name,
                            price=30.0,
                            value=traits[trait_name],
                        )
                        record_marketplace_success("list")
                        break
        except Exception:
            record_marketplace_failure("list")
