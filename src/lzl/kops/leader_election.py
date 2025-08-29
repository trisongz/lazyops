from __future__ import annotations

"""
Kubernetes Leader Election for FastAPI Applications

This module provides a leader election mechanism for Kubernetes deployments,
ensuring that only one pod/worker handles specific processes at a time.
"""

import os
import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Any, TYPE_CHECKING
from functools import wraps
from lzl.logging import logger
from lzl import load

if TYPE_CHECKING:
    import kubernetes
    import kubernetes.client.rest
    import kubernetes.client.exceptions
    import fastapi
    # from kubernetes import client, config
    # from kubernetes.client.rest import ApiException

else:
    kubernetes = load.lazy_load('kubernetes')
    fastapi = load.lazy_load('fastapi')



class KubernetesLeaderElection:
    """
    Implements leader election using Kubernetes Lease objects.
    
    This class ensures that only one instance (pod/worker) can hold the leadership
    role at any given time, with automatic failover if the leader fails.
    """
    
    def __init__(
        self,
        lease_name: str,
        namespace: str = None,
        lease_duration_seconds: int = 15,
        renew_deadline_seconds: int = 10,
        retry_period_seconds: int = 2,
        identity: str = None
    ):
        """
        Initialize the leader election manager.
        
        Args:
            lease_name: Name of the Kubernetes Lease object
            namespace: Kubernetes namespace (defaults to current pod's namespace)
            lease_duration_seconds: How long the lease is valid
            renew_deadline_seconds: How long before lease expires to renew
            retry_period_seconds: How often to retry acquiring the lease
            identity: Unique identifier for this instance (defaults to pod name + worker id)
        """
        self.lease_name = lease_name
        self.namespace = namespace or self._get_namespace()
        self.lease_duration_seconds = lease_duration_seconds
        self.renew_deadline_seconds = renew_deadline_seconds
        self.retry_period_seconds = retry_period_seconds
        self.identity = identity or self._generate_identity()
        
        self.is_leader = False
        self._stop_election = False
        self._election_task = None
        
        # Initialize Kubernetes client
        try:
            kubernetes.config.load_incluster_config()
        except kubernetes.config.ConfigException:
            # Fallback for local development
            kubernetes.config.load_kube_config()

        self.coordination_v1 = kubernetes.client.CoordinationV1Api()
    
    def _get_namespace(self) -> str:
        """Get the current pod's namespace."""
        namespace_path = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
        if os.path.exists(namespace_path):
            with open(namespace_path, 'r') as f:
                return f.read().strip()
        return "default"
    
    def _generate_identity(self) -> str:
        """Generate a unique identity for this instance."""
        from lzo.utils.system import get_host_name
        pod_name = os.environ.get("HOSTNAME", f"{get_host_name()}-{uuid.uuid4().hex[:8]}")
        worker_id = os.environ.get("WORKER_ID", str(os.getpid()))
        return f"{pod_name}-{worker_id}"

    def _create_or_get_lease(self) -> Optional['kubernetes.client.V1Lease']:
        """Create or retrieve the lease object."""
        try:
            return self.coordination_v1.read_namespaced_lease(
                name=self.lease_name,
                namespace=self.namespace
            )
        except kubernetes.client.rest.ApiException as e:
            if e.status == 404:
                # Lease doesn't exist, create it
                now = datetime.now(timezone.utc)
                lease = kubernetes.client.V1Lease(
                    metadata=kubernetes.client.V1ObjectMeta(
                        name=self.lease_name,
                        namespace=self.namespace
                    ),
                    spec=kubernetes.client.V1LeaseSpec(
                        holder_identity=self.identity,
                        lease_duration_seconds=self.lease_duration_seconds,
                        acquire_time=now,
                        renew_time=now
                    )
                )
                try:
                    return self.coordination_v1.create_namespaced_lease(
                        namespace=self.namespace,
                        body=lease
                    )
                except kubernetes.client.rest.ApiException as create_error:
                    if create_error.status == 409:
                        # Another instance created it concurrently
                        return self.coordination_v1.read_namespaced_lease(
                            name=self.lease_name,
                            namespace=self.namespace
                        )
                    raise
            raise


    def _parse_k8s_datetime(self, dt_value) -> datetime:
        """Parse datetime from Kubernetes, handling both string and datetime objects."""
        if dt_value is None:
            return None
        
        if isinstance(dt_value, datetime):
            # Already a datetime object
            if dt_value.tzinfo is None:
                # Assume UTC if no timezone
                return dt_value.replace(tzinfo=timezone.utc)
            return dt_value
        
        if isinstance(dt_value, str):
            # Handle various datetime string formats from Kubernetes
            # Remove microseconds if present (everything after the dot before timezone)
            if '.' in dt_value:
                # Split at the dot and reconstruct without microseconds
                base, remainder = dt_value.split('.', 1)
                # Find where timezone info starts (Z, +, or -)
                for i, char in enumerate(remainder):
                    if char in ['Z', '+', '-']:
                        dt_value = base + remainder[i:]
                        break
                else:
                    dt_value = base  # No timezone found
            
            # Replace Z with +00:00 for ISO format compatibility
            dt_value = dt_value.replace('Z', '+00:00')
            
            try:
                return datetime.fromisoformat(dt_value)
            except ValueError:
                # Fallback to parsing without timezone and assume UTC
                try:
                    dt_clean = dt_value.split('+')[0].split('-')[0] if '+' in dt_value or dt_value.count('-') > 2 else dt_value
                    return datetime.fromisoformat(dt_clean).replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.warning(f"Could not parse datetime: {dt_value}, using current time: {e}")
                    return datetime.now(timezone.utc)
        
        # Fallback for unexpected types
        logger.warning(f"Unexpected datetime type: {type(dt_value)}, using current time")
        return datetime.now(timezone.utc)
    
    def _try_acquire_or_renew(self) -> bool:
        # sourcery skip: extract-duplicate-method, hoist-statement-from-if, remove-unnecessary-else, swap-if-else-branches
        """Try to acquire or renew the lease."""
        lease = self._create_or_get_lease()
        if not lease:
            return False
        
        now = datetime.now(timezone.utc)
        
        # Check if we can acquire the lease
        if lease.spec.holder_identity == self.identity:
            # We already hold the lease, renew it
            lease.spec.renew_time = now
        elif lease.spec.renew_time:
            # Check if the current lease has expired
            renew_time = self._parse_k8s_datetime(lease.spec.renew_time)
            expiry_time = renew_time + timedelta(seconds=self.lease_duration_seconds)
            
            if now > expiry_time:
                # Lease has expired, we can acquire it
                lease.spec.holder_identity = self.identity
                lease.spec.acquire_time = now
                lease.spec.renew_time = now
            else:
                # Lease is held by another instance
                return False
        else:
            # No renew time set, acquire the lease
            lease.spec.holder_identity = self.identity
            lease.spec.acquire_time = now
            lease.spec.renew_time = now
        
        # Try to update the lease
        try:
            self.coordination_v1.replace_namespaced_lease(
                name=self.lease_name,
                namespace=self.namespace,
                body=lease
            )
            return lease.spec.holder_identity == self.identity
        except kubernetes.client.rest.ApiException as e:
            if e.status == 409:
                # Conflict - another instance updated the lease
                return False
            raise
    
    async def _election_loop(self):  # sourcery skip: remove-redundant-if
        """Main election loop that runs continuously."""
        retry_count = 0
        max_retries = 5
        
        while not self._stop_election:
            try:
                acquired = self._try_acquire_or_renew()
                retry_count = 0  # Reset retry count on success
                
                if acquired and not self.is_leader:
                    logger.info(f"Leadership acquired: |g|{self.identity}|e|", colored = True)
                    self.is_leader = True
                    if hasattr(self, '_on_elected_callback'):
                        await self._on_elected_callback()
                elif not acquired and self.is_leader:
                    logger.info(f"Leadership lost: |y|{self.identity}|e|", colored = True)
                    self.is_leader = False
                    if hasattr(self, '_on_lost_callback'):
                        await self._on_lost_callback()
                elif acquired and self.is_leader:
                    logger.debug(f"Leadership renewed: |g|{self.identity}|e|", colored = True)

                # Sleep before next attempt
                if self.is_leader:
                    # If we're the leader, renew more frequently
                    await asyncio.sleep(self.renew_deadline_seconds)
                else:
                    # If we're not the leader, check less frequently
                    await asyncio.sleep(self.retry_period_seconds)
                    
            except kubernetes.client.rest.ApiException as e:
                retry_count += 1
                logger.error(f"Kubernetes API error in election loop (attempt {retry_count}/{max_retries}): {e.status} - {e.reason}")
                
                if e.status == 401:
                    logger.error("Authentication failed. Check service account permissions.")
                elif e.status == 403:
                    logger.error("Authorization failed. Check RBAC permissions for leases.")
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) reached. Giving up leadership.")
                    self.is_leader = False
                    retry_count = 0  # Reset for next cycle
                
                await asyncio.sleep(self.retry_period_seconds * retry_count)  # Exponential backoff
                
            except Exception as e:
                retry_count += 1
                logger.error(f"Unexpected error in election loop (attempt {retry_count}/{max_retries}): {e}", exc_info=True)
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) reached. Giving up leadership.")
                    self.is_leader = False
                    retry_count = 0
                
                await asyncio.sleep(self.retry_period_seconds * retry_count)
    
    async def start(
        self,
        on_elected: Optional[Callable] = None,
        on_lost: Optional[Callable] = None
    ):
        """
        Start the leader election process.
        
        Args:
            on_elected: Async callback when leadership is acquired
            on_lost: Async callback when leadership is lost
        """
        if on_elected:
            self._on_elected_callback = on_elected
        if on_lost:
            self._on_lost_callback = on_lost
        
        self._stop_election = False
        self._election_task = asyncio.create_task(self._election_loop())
        logger.info(f"Leader election started for {self.identity}"
                    )
    
    async def stop(self):
        """Stop the leader election process."""
        self._stop_election = True
        if self._election_task:
            await self._election_task
        self.is_leader = False
        logger.info(f"Leader election stopped for {self.identity}")

    def leader_only(self, func: Callable) -> Callable:
        """
        Decorator to ensure a function only runs on the leader.
        
        Usage:
            @leader_election.leader_only
            async def process_batch():
                # This will only run on the leader
                pass
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not self.is_leader:
                raise fastapi.HTTPException(
                    status_code=503,
                    detail="This instance is not the leader"
                )
            return await func(*args, **kwargs)
        return wrapper
    
    @asynccontextmanager
    async def as_leader(self):
        """
        Context manager that only executes if this instance is the leader.
        
        Usage:
            async with leader_election.as_leader():
                # Code here only runs on the leader
                await process_important_task()
        """
        if self.is_leader:
            yield
        else:
            raise fastapi.HTTPException(
                status_code=503,
                detail="This instance is not the leader"
            )


# # FastAPI integration example
# def create_leader_election_app(
#     lease_name: str = "my-app-leader",
#     namespace: str = None
# ) -> tuple[FastAPI, KubernetesLeaderElection]:
#     """
#     Create a FastAPI app with leader election integrated.
    
#     Returns:
#         Tuple of (FastAPI app, KubernetesLeaderElection instance)
#     """
    
#     leader_election = KubernetesLeaderElection(
#         lease_name=lease_name,
#         namespace=namespace
#     )
    
#     @asynccontextmanager
#     async def lifespan(app: FastAPI):
#         # Startup
#         async def on_elected():
#             logger.info("This instance is now the leader!")
#             # Initialize leader-only resources here
        
#         async def on_lost():
#             logger.info("This instance lost leadership!")
#             # Cleanup leader-only resources here
        
#         await leader_election.start(
#             on_elected=on_elected,
#             on_lost=on_lost
#         )
        
#         yield
        
#         # Shutdown
#         await leader_election.stop()
    
#     app = FastAPI(lifespan=lifespan)
    
#     # Health check endpoint
#     @app.get("/health")
#     async def health():
#         return {
#             "status": "healthy",
#             "is_leader": leader_election.is_leader,
#             "identity": leader_election.identity
#         }
    
#     # Leader status endpoint
#     @app.get("/leader")
#     async def leader_status():
#         return {
#             "is_leader": leader_election.is_leader,
#             "identity": leader_election.identity,
#             "lease_name": leader_election.lease_name
#         }
    
#     # Example endpoint that only works on the leader
#     @app.post("/process-batch")
#     @leader_election.leader_only
#     async def process_batch(data: dict):
#         """This endpoint only processes on the leader instance."""
#         # Your batch processing logic here
#         return {
#             "status": "processed",
#             "leader": leader_election.identity,
#             "data": data
#         }
    
#     return app, leader_election

