"""
Complete simulation of the Notification Prioritization Engine.
Tests realistic scenarios to showcase all decision paths and rules.
"""

from datetime import datetime, timedelta, timezone
from app.engine import PrioritizationEngine
from app.models import Decision, NotificationEvent, RuleConfig
from app.store import InMemoryStore


def print_result(title: str, event: NotificationEvent, decision, indent=0):
    """Pretty print simulation results."""
    prefix = "  " * indent
    print(f"\n{prefix}📧 {title}")
    print(f"{prefix}   Event: {event.event_type} | {event.message}")
    print(f"{prefix}   Decision: {decision.decision.value} ✓")
    print(f"{prefix}   Reason: {decision.reason}")
    print(f"{prefix}   Risk Score: {decision.risk_score}")


def scenario_1_exact_duplicates():
    """Scenario 1: Same notification sent twice"""
    print("\n" + "="*70)
    print("SCENARIO 1: Exact Duplicates (Same message sent twice)")
    print("="*70)
    
    store = InMemoryStore()
    engine = PrioritizationEngine(store)
    
    event = NotificationEvent(
        user_id="alice",
        event_type="message_direct",
        message="Hey, are you free tomorrow?",
        title="Chat from Bob",
        source="messenger",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="msg_bob_12345"
    )
    
    d1 = engine.decide(event)
    print_result("First message from Bob", event, d1)
    
    d2 = engine.decide(event)
    print_result("Same message again (duplicate)", event, d2)
    
    assert d1.decision == Decision.NOW
    assert d2.decision == Decision.NEVER
    print("\n✅ Scenario 1 passed: Duplicate suppressed")


def scenario_2_near_duplicates():
    """Scenario 2: Similar notifications get batched"""
    print("\n" + "="*70)
    print("SCENARIO 2: Near Duplicates (Similar content, batched for digest)")
    print("="*70)
    
    store = InMemoryStore()
    store.set_rules(RuleConfig(near_duplicate_window_seconds=3600, cooldown_seconds=0))
    engine = PrioritizationEngine(store)
    
    e1 = NotificationEvent(
        user_id="bob",
        event_type="shipping_update",
        message="Your order has shipped and will arrive tomorrow",
        title="Delivery Update",
        source="amazon",
        timestamp=datetime.now(timezone.utc),
        channel="push"
    )
    
    d1 = engine.decide(e1)
    print_result("Order shipped notification", e1, d1)
    
    # Very similar message with slightly different wording
    e2 = NotificationEvent(
        user_id="bob",
        event_type="shipping_update",
        message="Your order shipped and will arrive tomorrow",
        title="Delivery Update",
        source="amazon",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="shipment_xyz789"
    )
    
    d2 = engine.decide(e2)
    print_result("Similar message (near duplicate)", e2, d2)
    
    assert d1.decision == Decision.NOW
    assert d2.decision == Decision.LATER
    print("\n✅ Scenario 2 passed: Near duplicate batched for digest")


def scenario_3_rate_limiting():
    """Scenario 3: Too many notifications in an hour"""
    print("\n" + "="*70)
    print("SCENARIO 3: Rate Limiting (Limit 3 per hour for non-urgent)")
    print("="*70)
    
    store = InMemoryStore()
    # Disable cooldown to isolate rate limiting behavior
    store.set_rules(RuleConfig(max_per_hour=3, cooldown_seconds=0, urgent_event_types=["security_alert"]))
    engine = PrioritizationEngine(store)
    
    # Send 5 notifications on different channels or with sufficient spacing
    for i in range(5):
        event = NotificationEvent(
            user_id="charlie",
            event_type="reminder",
            message=f"Reminder #{i+1}",
            title="Daily Reminder",
            source="calendar",
            timestamp=datetime.now(timezone.utc),
            channel=f"channel_{i}",  # Different channel each time to avoid cooldown
            dedupe_key=f"reminder_{i}"
        )
        
        decision = engine.decide(event)
        status = "NOW" if decision.decision == Decision.NOW else "LATER"
        print(f"   Reminder #{i+1}: {status}")
        
        if i < 3:
            assert decision.decision == Decision.NOW
        else:
            assert decision.decision == Decision.LATER
    
    print("\n✅ Scenario 3 passed: First 3 approved, rest deferred")


def scenario_4_urgent_bypass():
    """Scenario 4: Urgent alerts bypass all limits"""
    print("\n" + "="*70)
    print("SCENARIO 4: Urgent Alerts Bypass Rate Limits")
    print("="*70)
    
    store = InMemoryStore()
    store.set_rules(RuleConfig(max_per_hour=1, urgent_event_types=["security_alert"]))
    engine = PrioritizationEngine(store)
    
    # Fill up the hourly quota with non-urgent
    e1 = NotificationEvent(
        user_id="dave",
        event_type="reminder",
        message="Non-urgent reminder",
        title="Reminder",
        source="app",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="reminder_1"
    )
    d1 = engine.decide(e1)
    print_result("Non-urgent reminder", e1, d1)
    
    # Try urgent alert - should go through despite limit
    e2 = NotificationEvent(
        user_id="dave",
        event_type="security_alert",
        message="Unauthorized access attempt detected on your account!",
        title="⚠️ Security Alert",
        source="security",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="security_alert_1"
    )
    d2 = engine.decide(e2)
    print_result("URGENT security alert (despite hourly limit)", e2, d2)
    
    assert d1.decision == Decision.NOW
    assert d2.decision == Decision.NOW
    print("\n✅ Scenario 4 passed: Urgent alert bypasses rate limit")


def scenario_5_expired_events():
    """Scenario 5: Expired notifications are never sent"""
    print("\n" + "="*70)
    print("SCENARIO 5: Expired Notifications Suppressed")
    print("="*70)
    
    store = InMemoryStore()
    engine = PrioritizationEngine(store)
    
    # Event that expired 1 hour ago
    e1 = NotificationEvent(
        user_id="eve",
        event_type="promotion",
        message="Flash sale ends in 2 hours!",
        title="50% OFF Today Only",
        source="store",
        timestamp=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        channel="push"
    )
    
    d1 = engine.decide(e1)
    print_result("Expired promotion (sale ended)", e1, d1)
    
    # Event that expires in 1 hour
    e2 = NotificationEvent(
        user_id="eve",
        event_type="promotion",
        message="Flash sale ends in 1 hour!",
        title="50% OFF Today Only",
        source="store",
        timestamp=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        channel="push",
        dedupe_key="promo_1"
    )
    
    d2 = engine.decide(e2)
    print_result("Valid promotion (still active)", e2, d2)
    
    assert d1.decision == Decision.NEVER
    assert d2.decision == Decision.NOW
    print("\n✅ Scenario 5 passed: Expired events blocked")


def scenario_6_promotional_daily_cap():
    """Scenario 6: Limit promotional/marketing emails"""
    print("\n" + "="*70)
    print("SCENARIO 6: Promotional Daily Cap (Max 3 per day)")
    print("="*70)
    
    store = InMemoryStore()
    store.set_rules(RuleConfig(
        promotional_cap_per_day=3,
        promotional_event_types=["promotion", "upsell"],
        cooldown_seconds=0  # Disable cooldown to isolate promotional cap testing
    ))
    engine = PrioritizationEngine(store)
    
    # Send 5 promotional emails
    for i in range(5):
        event = NotificationEvent(
            user_id="frank",
            event_type="promotion",
            message=f"Promotional offer #{i+1}",
            title="Special Offer",
            source="marketing",
            timestamp=datetime.now(timezone.utc),
            channel=f"email_{i}",  # Different channel each time to avoid cooldown
            dedupe_key=f"promo_{i}"
        )
        
        decision = engine.decide(event)
        status = "NOW" if decision.decision == Decision.NOW else "NEVER"
        print(f"   Promo #{i+1}: {status}")
        
        if i < 3:
            assert decision.decision == Decision.NOW
        else:
            assert decision.decision == Decision.NEVER
    
    print("\n✅ Scenario 6 passed: Only first 3 promotions sent per day")


def scenario_7_suppressed_events():
    """Scenario 7: Some event types are always suppressed"""
    print("\n" + "="*70)
    print("SCENARIO 7: Suppressed Event Types (Never send)")
    print("="*70)
    
    store = InMemoryStore()
    # passive_tips are in the suppress list by default
    rules = store.get_rules()
    print(f"   Suppressed types: {rules.suppress_event_types}")
    
    engine = PrioritizationEngine(store)
    
    event = NotificationEvent(
        user_id="grace",
        event_type="passive_tip",
        message="Did you know? You can organize notifications by priority!",
        title="Pro Tip",
        source="app",
        timestamp=datetime.now(timezone.utc),
        channel="push"
    )
    
    decision = engine.decide(event)
    print_result("Passive tip (suppressed type)", event, decision)
    
    assert decision.decision == Decision.NEVER
    print("\n✅ Scenario 7 passed: Suppressed event types never sent")


def scenario_8_channel_cooldown():
    """Scenario 8: Per-channel cooldown for non-urgent"""
    print("\n" + "="*70)
    print("SCENARIO 8: Channel Cooldown (Prevent notification spam)")
    print("="*70)
    
    store = InMemoryStore()
    store.set_rules(RuleConfig(cooldown_seconds=300, urgent_event_types=[]))  # 5 min cooldown
    engine = PrioritizationEngine(store)
    
    # First notification on push channel
    e1 = NotificationEvent(
        user_id="henry",
        event_type="message_direct",
        message="Message 1",
        title="Chat",
        source="messenger",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="msg_1"
    )
    
    d1 = engine.decide(e1)
    print_result("Message 1 on push channel", e1, d1)
    
    # Second notification on same channel (within cooldown)
    e2 = NotificationEvent(
        user_id="henry",
        event_type="message_direct",
        message="Message 2",
        title="Chat",
        source="messenger",
        timestamp=datetime.now(timezone.utc),
        channel="push",
        dedupe_key="msg_2"
    )
    
    d2 = engine.decide(e2)
    print_result("Message 2 on same channel (within cooldown)", e2, d2)
    
    # Notification on different channel (should work)
    e3 = NotificationEvent(
        user_id="henry",
        event_type="message_direct",
        message="Email notification",
        title="Chat",
        source="messenger",
        timestamp=datetime.now(timezone.utc),
        channel="email",
        dedupe_key="msg_3"
    )
    
    d3 = engine.decide(e3)
    print_result("Message on different channel (email)", e3, d3)
    
    assert d1.decision == Decision.NOW
    assert d2.decision == Decision.LATER
    assert d3.decision == Decision.NOW
    print("\n✅ Scenario 8 passed: Channel cooldown working correctly")


def main():
    """Run all scenarios."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "NOTIFICATION ENGINE - COMPLETE SIMULATION" + " "*12 + "║")
    print("╚" + "="*68 + "╝")
    
    scenario_1_exact_duplicates()
    scenario_2_near_duplicates()
    scenario_3_rate_limiting()
    scenario_4_urgent_bypass()
    scenario_5_expired_events()
    scenario_6_promotional_daily_cap()
    scenario_7_suppressed_events()
    scenario_8_channel_cooldown()
    
    print("\n" + "="*70)
    print("🎉 ALL SCENARIOS PASSED! Engine is working correctly.")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
