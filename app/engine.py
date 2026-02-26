from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models import Decision, DecisionResponse, NotificationEvent, RuleConfig
from app.store import utc_now

if TYPE_CHECKING:
    from app.store import InMemoryStore


def normalized_text(text: str | None) -> str:
    """Normalize text for near-duplicate detection."""
    if not text:
        return ""
    return text.lower().strip()


def token_fingerprint(text: str) -> str:
    """Create a fingerprint from tokens for near-duplicate detection."""
    if not text:
        return ""
    tokens = set(normalized_text(text).split())
    sorted_tokens = sorted(tokens)
    combined = "|".join(sorted_tokens)
    return combined  # Return the token string, not the hash  


def jaccard_similarity(fp1: str, fp2: str) -> float:
    """Calculate Jaccard similarity between two token fingerprints."""
    if not fp1 or not fp2:
        return 0.0
    tokens1 = set(fp1.split("|"))
    tokens2 = set(fp2.split("|"))
    if not tokens1 and not tokens2:
        return 1.0
    if not tokens1 or not tokens2:
        return 0.0
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)
    return intersection / union if union > 0 else 0.0


class PrioritizationEngine:
    """Decision engine for notification prioritization."""

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def decide(self, event: NotificationEvent) -> DecisionResponse:
        """Process a notification event and return a decision."""
        rules = self.store.get_rules()
        now = utc_now()

        # 1. Check if event is expired
        if event.expires_at and event.expires_at < now:
            return DecisionResponse(
                decision=Decision.NEVER,
                reason="event_expired",
                scheduled_for=None,
                policy_version=rules.policy_version,
                risk_score=0.0,
            )

        # 2. Check if event type is in suppress list
        if event.event_type in rules.suppress_event_types:
            return DecisionResponse(
                decision=Decision.NEVER,
                reason="event_type_suppressed",
                scheduled_for=None,
                policy_version=rules.policy_version,
                risk_score=0.0,
            )

        # 3. Check for exact duplicates
        if event.dedupe_key:
            if self.store.exact_seen_within(event.user_id, event.dedupe_key, rules.cooldown_seconds):
                return DecisionResponse(
                    decision=Decision.NEVER,
                    reason="exact_duplicate",
                    scheduled_for=None,
                    policy_version=rules.policy_version,
                    risk_score=0.0,
                )
            # Mark this exact dedupe key as seen
            self.store.mark_exact_seen(event.user_id, event.dedupe_key, now)

        # 4. Check promotional daily cap
        if event.event_type in rules.promotional_event_types:
            recent = self.store.recent_events(event.user_id, within_seconds=86400)  # 24 hours
            promo_count = sum(
                1 for e in recent if e.event_type in rules.promotional_event_types
            )
            if promo_count >= rules.promotional_cap_per_day:
                return DecisionResponse(
                    decision=Decision.NEVER,
                    reason="promotional_daily_cap_reached",
                    scheduled_for=None,
                    policy_version=rules.policy_version,
                    risk_score=0.0,
                )

        # 5. Check for near duplicates
        is_urgent = event.event_type in rules.urgent_event_types
        if not is_urgent:
            # Create fingerprint for near-duplicate detection
            combined_text = f"{event.title or ''} {event.message or ''}"
            fp = token_fingerprint(combined_text)

            if fp:
                recent_fps = self.store.recent_fingerprints(
                    event.user_id, within_seconds=rules.near_duplicate_window_seconds
                )
                for recent_fp in recent_fps:
                    if recent_fp.event.event_type == event.event_type:
                        similarity = jaccard_similarity(fp, recent_fp.fingerprint)
                        if similarity >= 0.82:
                            return DecisionResponse(
                                decision=Decision.LATER,
                                reason="near_duplicate",
                                scheduled_for=now,  # Will be digested later
                                policy_version=rules.policy_version,
                                risk_score=0.5,
                            )

            # Store this fingerprint for future near-duplicate detection
            self.store.push_fingerprint(event.user_id, fp, event, now)

        # 6. Check hourly rate limit (only for non-urgent events)
        if not is_urgent:
            recent = self.store.recent_events(event.user_id, within_seconds=3600)  # 1 hour
            if len(recent) >= rules.max_per_hour:
                return DecisionResponse(
                    decision=Decision.LATER,
                    reason="hourly_rate_limit_exceeded",
                    scheduled_for=now,
                    policy_version=rules.policy_version,
                    risk_score=0.3,
                )

        # 7. Check per-channel cooldown (only for non-urgent)
        if not is_urgent:
            recent = self.store.recent_events(
                event.user_id, within_seconds=rules.cooldown_seconds
            )
            for r in recent:
                if r.channel == event.channel:
                    return DecisionResponse(
                        decision=Decision.LATER,
                        reason="channel_cooldown_active",
                        scheduled_for=now,
                        policy_version=rules.policy_version,
                        risk_score=0.2,
                    )

        # All checks passed - deliver now
        self.store.add_event(event)
        return DecisionResponse(
            decision=Decision.NOW,
            reason="passed_all_checks",
            scheduled_for=None,
            policy_version=rules.policy_version,
            risk_score=0.0,
        )
