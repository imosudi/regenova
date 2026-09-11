"""
REAMP Authentication and Authorization Manager.
Handles HMAC-signed token generation, signature validation, anti-replay nonce tracking,
token-bucket rate limiting, and multi-tenant RBAC/ABAC enforcement.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import datetime
import hashlib
import hmac
import uuid
import time

from reamp.security.models import (
    SecurityRole,
    Permission,
    UserIdentity,
    SecurityToken,
    TelemetryPacketSignature,
    ThreatCategory,
    SecurityIncident,
)


class AuthenticationManager:
    """
    Manages cryptographic token creation, device signature verification,
    anti-replay defenses, and rate limiting.
    """

    def __init__(
        self,
        master_secret: str = "reamp-default-production-master-secret-key-32b",
        token_ttl_seconds: int = 3600,
        max_clock_skew_seconds: float = 30.0,
        rate_limit_per_second: float = 100.0,
        burst_capacity: int = 150,
    ) -> None:
        self.master_secret = master_secret.encode("utf-8")
        self.token_ttl = token_ttl_seconds
        self.max_clock_skew = max_clock_skew_seconds

        # Anti-Replay Nonce Cache: maps nonce -> float timestamp
        self._seen_nonces: Dict[str, float] = {}

        # Token-Bucket Rate Limiter state: client_id -> (tokens, last_refill_time)
        self.rate_limit_rate = rate_limit_per_second
        self.burst_capacity = burst_capacity
        self._token_buckets: Dict[str, Tuple[float, float]] = {}

    # -------------------------------------------------------------------------
    # 1. API Token Management (JWT/HMAC)
    # -------------------------------------------------------------------------

    def generate_token(self, user: UserIdentity) -> SecurityToken:
        """Issues an HMAC-signed token bound to user identity and tenant."""
        token_id = f"TOK-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.datetime.now(datetime.timezone.utc)
        exp = now + datetime.timedelta(seconds=self.token_ttl)

        issued_str = now.isoformat()
        exp_str = exp.isoformat()

        # Compute signature: HMAC(token_id | user_id | tenant_id | role | exp)
        payload = f"{token_id}:{user.user_id}:{user.tenant_id}:{user.role.value}:{exp_str}"
        sig = hmac.new(self.master_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

        return SecurityToken(
            token_id=token_id,
            subject_id=user.user_id,
            tenant_id=user.tenant_id,
            role=user.role,
            permissions=list(user.permissions),
            issued_at=issued_str,
            expires_at=exp_str,
            signature=sig,
        )

    def verify_token(self, token: SecurityToken, current_time: Optional[datetime.datetime] = None) -> UserIdentity:
        """
        Validates token authenticity, signature, and expiration.
        Raises PermissionError or ValueError on invalid token.
        """
        # Expiry check
        if token.is_expired(current_time):
            raise PermissionError(f"Security Token '{token.token_id}' has expired.")

        # Signature verification
        payload = f"{token.token_id}:{token.subject_id}:{token.tenant_id}:{token.role.value}:{token.expires_at}"
        expected_sig = hmac.new(self.master_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(token.signature, expected_sig):
            raise PermissionError("Invalid Token Signature: Cryptographic verification failed.")

        return UserIdentity(
            user_id=token.subject_id,
            username=token.subject_id,
            tenant_id=token.tenant_id,
            role=token.role,
            permissions=token.permissions,
        )

    # -------------------------------------------------------------------------
    # 2. Edge Telemetry Signing & Anti-Replay Defense
    # -------------------------------------------------------------------------

    def sign_telemetry_packet(
        self,
        device_id: str,
        device_secret: str,
        payload_str: str,
        timestamp: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> TelemetryPacketSignature:
        """Signs a raw telemetry packet at the edge gateway."""
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        n = nonce or uuid.uuid4().hex
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        sig_data = f"{device_id}:{ts}:{n}:{payload_hash}"
        signature = hmac.new(device_secret.encode("utf-8"), sig_data.encode("utf-8"), hashlib.sha256).hexdigest()

        return TelemetryPacketSignature(
            device_id=device_id,
            timestamp=ts,
            nonce=n,
            payload_hash=payload_hash,
            signature=signature,
        )

    def verify_telemetry_packet(
        self,
        packet_sig: TelemetryPacketSignature,
        device_secret: str,
        payload_str: str,
        current_time: Optional[datetime.datetime] = None,
    ) -> bool:
        """
        Validates payload integrity, freshness window, nonce uniqueness (anti-replay),
        and cryptographic HMAC authenticity.
        """
        now = current_time or datetime.datetime.now(datetime.timezone.utc)
        packet_dt = datetime.datetime.fromisoformat(packet_sig.timestamp.replace("Z", "+00:00"))
        if packet_dt.tzinfo is None:
            packet_dt = packet_dt.replace(tzinfo=datetime.timezone.utc)

        age_seconds = abs((now - packet_dt).total_seconds())

        # 1. Freshness window check
        if age_seconds > self.max_clock_skew:
            raise ValueError(
                f"Packet Freshness Breach: Age {age_seconds:.1f}s exceeds max allowed window ({self.max_clock_skew}s)."
            )

        # 2. Anti-Replay Nonce Check
        self._prune_old_nonces(now)
        if packet_sig.nonce in self._seen_nonces:
            raise ValueError(
                f"Replay Attack Detected: Nonce '{packet_sig.nonce}' has already been processed."
            )

        # 3. Payload Integrity Check
        computed_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(packet_sig.payload_hash, computed_hash):
            raise ValueError("Payload Tampering Detected: Payload SHA-256 hash mismatch.")

        # 4. Cryptographic HMAC Signature Verification
        sig_data = f"{packet_sig.device_id}:{packet_sig.timestamp}:{packet_sig.nonce}:{computed_hash}"
        expected_sig = hmac.new(device_secret.encode("utf-8"), sig_data.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(packet_sig.signature, expected_sig):
            raise PermissionError("Packet Authenticity Failed: Cryptographic signature mismatch.")

        # Record valid nonce
        self._seen_nonces[packet_sig.nonce] = now.timestamp()
        return True

    def _prune_old_nonces(self, now: datetime.datetime) -> None:
        """Removes nonces older than 2x max_clock_skew to preserve memory."""
        cutoff = now.timestamp() - (self.max_clock_skew * 2)
        expired = [n for n, ts in self._seen_nonces.items() if ts < cutoff]
        for n in expired:
            del self._seen_nonces[n]

    # -------------------------------------------------------------------------
    # 3. Rate Limiting & DoS Defense (Token-Bucket)
    # -------------------------------------------------------------------------

    def check_rate_limit(self, client_id: str, current_time_epoch: Optional[float] = None) -> bool:
        """
        Token-bucket rate limiter enforcing ingestion traffic shaping.
        Returns True if request is allowed, False if rate limit exceeded.
        """
        now = current_time_epoch if current_time_epoch is not None else time.time()

        tokens, last_refill = self._token_buckets.get(client_id, (float(self.burst_capacity), now))

        # Refill tokens based on elapsed time
        elapsed = max(0.0, now - last_refill)
        tokens = min(float(self.burst_capacity), tokens + (elapsed * self.rate_limit_rate))

        if tokens >= 1.0:
            self._token_buckets[client_id] = (tokens - 1.0, now)
            return True
        else:
            self._token_buckets[client_id] = (tokens, now)
            return False


class AuthorizationManager:
    """
    Enforces Role-Based Access Control (RBAC) and Multi-Tenant Isolation (ABAC).
    """

    @staticmethod
    def authorize(
        actor: UserIdentity,
        required_permission: Permission,
        target_tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Validates that the actor possesses required permissions and respects tenant boundaries.
        Raises PermissionError on unauthorized attempt.
        """
        # 1. Multi-Tenant Boundary Enforcement (ABAC)
        if target_tenant_id is not None and actor.role != SecurityRole.SECURITY_ADMIN:
            if actor.tenant_id != target_tenant_id:
                raise PermissionError(
                    f"Multi-Tenant Isolation Violation: Actor tenant '{actor.tenant_id}' "
                    f"cannot access resource owned by tenant '{target_tenant_id}'."
                )

        # 2. Permission Capability Enforcement (RBAC)
        if not actor.has_permission(required_permission):
            raise PermissionError(
                f"Access Denied: Role '{actor.role.value}' lacks mandatory permission '{required_permission.value}'."
            )

        return True
