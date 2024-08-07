from __future__ import annotations

"""
Admin API for Hatchet
"""
import json
import grpc

from hatchet_sdk.workflows_pb2 import ( 
    TriggerWorkflowRequest,
    TriggerWorkflowResponse,
)
from hatchet_sdk.metadata import get_metadata
from hatchet_sdk.loader import ClientConfig
from hatchet_sdk.clients.admin import AdminClientImpl as BaseAdminClientImpl
from hatchet_sdk.clients.admin import TriggerWorkflowOptions
from hatchet_sdk.workflows_pb2_grpc import WorkflowServiceStub
from .utils import json_serializer


def new_admin(conn, config: ClientConfig):
    return AdminClientImpl(
        client=WorkflowServiceStub(conn),
        token=config.token,
    )

class AdminClientImpl(BaseAdminClientImpl):
    """
    Admin Client with patched methods
    """

    def run_workflow(
        self,
        workflow_name: str,
        input: any,
        options: TriggerWorkflowOptions = None,
    ):
        """
        Handle the run workflow method
        """
        try:
            payload_data = json_serializer.dumps(input)

            try:
                meta = None if options is None else options.get("additional_metadata")
                options["additional_metadata"] = (
                    None if meta is None else json_serializer.dumps(meta).encode("utf-8")
                )
            except json.JSONDecodeError as e:
                raise ValueError(f"Error encoding payload: {e}") from e

            resp: TriggerWorkflowResponse = self.client.TriggerWorkflow(
                TriggerWorkflowRequest(
                    name=workflow_name, input=payload_data, **(options or {})
                ),
                metadata=get_metadata(self.token),
            )

            return resp.workflow_run_id
        except grpc.RpcError as e:
            raise ValueError(f"gRPC error: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error encoding payload: {e}")
