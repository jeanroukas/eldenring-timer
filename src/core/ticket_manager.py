"""
Transaction Ticket System - Event Sourcing for Rune Transactions

This module implements a ticket-based validation system for rune transactions
to resolve OCR ambiguities and enable retroactive corrections.

Key Concepts:
- Tickets are created when runes decrease
- Evidence is collected over time (level changes, stability, recovery)
- Tickets are resolved based on evidence (LEVEL_UP, MERCHANT, GHOST, ERROR)
- Graph updates are deferred until ticket validation
"""

import time
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TransactionTicket:
    """
    Represents a pending rune transaction awaiting validation.
    
    Transaction Types:
    - GAIN: Runes increased (enemy kills, items)
    - SPENDING: Runes decreased (merchant purchases)
    - LEVEL_UP: Runes decreased (level-up cost)
    - DEATH: Runes lost (player death)
    - RECOVERY: Runes recovered (after death)
    
    State Machine:
    PENDING → VALIDATED (GAIN/SPENDING/LEVEL_UP/DEATH/RECOVERY) → APPLIED
           → REJECTED (GHOST or ERROR) → REVERTED
    """
    id: str
    timestamp: float
    amount: int  # Amount of runes changed (positive or negative)
    old_runes: int
    new_runes: int
    
    # Transaction type
    transaction_type: str = "SPENDING"  # GAIN, SPENDING, LEVEL_UP, DEATH, RECOVERY
    
    # State
    state: str = "PENDING"  # PENDING, VALIDATED, REJECTED, APPLIED, REVERTED
    
    # Evidence collection
    evidence: Dict[str, any] = field(default_factory=lambda: {
        "level_up_detected": False,
        "level_cost_match": False,
        "multiple_of_100": False,
        "ghost_recovery": False,
        "hud_hidden": False
    })
    
    # Additional context (type-specific data)
    context: Dict[str, any] = field(default_factory=dict)
    # Examples:
    # LEVEL_UP: {"old_level": 2, "new_level": 3}
    # DEATH: {"death_count": 1}
    # RECOVERY: {"recovery_count": 1}
    
    # Resolution
    resolution: Optional[str] = None  # GAIN, SPENDING, LEVEL_UP, DEATH, RECOVERY, GHOST, ERROR
    resolved_at: Optional[float] = None
    
    def __repr__(self):
        return f"Ticket({self.id}, {self.state}, {self.resolution}, -{self.amount})"


class TicketManager:
    """
    Manages the lifecycle of transaction tickets.
    
    Responsibilities:
    - Create tickets when runes decrease
    - Collect evidence from game events
    - Resolve tickets based on evidence priority
    - Apply validated tickets to game state
    """
    
    def __init__(self, config: dict):
        self.config = config
        self.tickets: Dict[str, TransactionTicket] = {}
        self.next_ticket_id = 1
        self.debug_mode = config.get("debug_mode", False)
    
    def create_ticket(self, amount: int, old_runes: int, new_runes: int, 
                     transaction_type: str = "SPENDING", context: Dict = None) -> TransactionTicket:
        """Create a new transaction ticket."""
        ticket_id = f"T{self.next_ticket_id:04d}"
        self.next_ticket_id += 1
        
        ticket = TransactionTicket(
            id=ticket_id,
            timestamp=time.time(),
            amount=amount,
            old_runes=old_runes,
            new_runes=new_runes,
            transaction_type=transaction_type,
            context=context or {}
        )
        
        # Immediate evidence: Multiple of 100?
        if amount % 100 == 0:
            ticket.evidence["multiple_of_100"] = True
        
        self.tickets[ticket_id] = ticket
        
        if self.debug_mode:
            logger.info(f"TICKET_CREATED: {ticket_id} | Type: {transaction_type} | Amount: {amount:+d} | Old: {old_runes} → New: {new_runes}")
        
        return ticket
    
    def add_evidence(self, ticket_id: str, evidence_type: str, value: any):
        """Add evidence to a ticket."""
        if ticket_id not in self.tickets:
            return
        
        ticket = self.tickets[ticket_id]
        if ticket.state != "PENDING":
            return  # Already resolved
        
        ticket.evidence[evidence_type] = value
        
        if self.debug_mode:
            logger.info(f"TICKET_EVIDENCE: {ticket_id} | {evidence_type} = {value}")
        
        # Try to resolve immediately if we have strong evidence
        self.resolve_ticket(ticket_id)
    
    def resolve_ticket(self, ticket_id: str):
        """
        Resolve a ticket based on collected evidence and transaction type.
        
        Instant Resolution:
        - GAIN: Always instant (no ambiguity)
        - DEATH: Instant (3 conditions already checked)
        - RECOVERY: Instant (exact match)
        - LEVEL_UP: Instant when level changes (cost never multiple of 100)
        
        Delayed Resolution:
        - SPENDING: 0.5-2s validation (wait for level change)
        """
        if ticket_id not in self.tickets:
            return
        
        ticket = self.tickets[ticket_id]
        if ticket.state != "PENDING":
            return  # Already resolved
        
        # Instant resolution for specific transaction types
        if ticket.transaction_type == "GAIN":
            ticket.resolution = "GAIN"
            ticket.state = "VALIDATED"
            ticket.resolved_at = time.time()
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → GAIN (instant)")
            return
        
        if ticket.transaction_type == "DEATH":
            ticket.resolution = "DEATH"
            ticket.state = "VALIDATED"
            ticket.resolved_at = time.time()
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → DEATH (instant)")
            return
        
        if ticket.transaction_type == "RECOVERY":
            ticket.resolution = "RECOVERY"
            ticket.state = "VALIDATED"
            ticket.resolved_at = time.time()
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → RECOVERY (instant)")
            return
        
        # Priority 1: Level-up (instant, no ambiguity)
        if ticket.evidence["level_up_detected"]:
            ticket.resolution = "LEVEL_UP"
            ticket.state = "VALIDATED"
            ticket.resolved_at = time.time()
            
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → LEVEL_UP (cost match)")
            return
        
        # Priority 2: Ghost (quick recovery)
        if ticket.evidence["ghost_recovery"]:
            ticket.resolution = "GHOST"
            ticket.state = "REJECTED"
            ticket.resolved_at = time.time()
            
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → GHOST (OCR error)")
            return
        
        # Priority 3: Merchant (multiple of 100, no level change)
        # Wait at least 0.5s to ensure level change would have been detected
        age = time.time() - ticket.timestamp
        if ticket.evidence["multiple_of_100"] and age > 0.5:
            ticket.resolution = "MERCHANT"
            ticket.state = "VALIDATED"
            ticket.resolved_at = time.time()
            
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → MERCHANT (multiple of 100)")
            return
        
        # Default: Timeout (2s)
        if age > 2.0:
            if ticket.evidence["multiple_of_100"]:
                ticket.resolution = "MERCHANT"
                ticket.state = "VALIDATED"
            else:
                ticket.resolution = "ERROR"
                ticket.state = "REJECTED"
            
            ticket.resolved_at = time.time()
            
            if self.debug_mode:
                logger.info(f"TICKET_RESOLVED: {ticket_id} → {ticket.resolution} (timeout)")
    
    def check_pending_tickets(self):
        """Check all pending tickets and try to resolve them."""
        for ticket_id in list(self.tickets.keys()):
            ticket = self.tickets[ticket_id]
            if ticket.state == "PENDING":
                self.resolve_ticket(ticket_id)
    
    def get_validated_tickets(self) -> List[TransactionTicket]:
        """Get all tickets that have been validated but not yet applied."""
        return [t for t in self.tickets.values() if t.state == "VALIDATED"]
    
    def get_active_tickets(self) -> List[TransactionTicket]:
        """Get all pending tickets."""
        return [t for t in self.tickets.values() if t.state == "PENDING"]
    
    def mark_applied(self, ticket_id: str):
        """Mark a ticket as applied to game state."""
        if ticket_id in self.tickets:
            self.tickets[ticket_id].state = "APPLIED"
    
    def mark_reverted(self, ticket_id: str):
        """Mark a ticket as reverted (ghost/error)."""
        if ticket_id in self.tickets:
            self.tickets[ticket_id].state = "REVERTED"
    
    def cleanup_old_tickets(self, max_age: float = 300.0):
        """Remove tickets older than max_age seconds."""
        now = time.time()
        to_remove = []
        
        for ticket_id, ticket in self.tickets.items():
            if ticket.state in ["APPLIED", "REVERTED"] and (now - ticket.timestamp) > max_age:
                to_remove.append(ticket_id)
        
        for ticket_id in to_remove:
            del self.tickets[ticket_id]
        
        if to_remove and self.debug_mode:
            logger.info(f"TICKET_CLEANUP: Removed {len(to_remove)} old tickets")
