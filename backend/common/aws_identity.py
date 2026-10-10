"""Bridge boto3's credential chain into the smithy-based AWS SDKs.

The smithy SDKs (aws-sdk-transcribe-streaming, aws-sdk-bedrock-runtime) ship a
credential chain without EC2 instance-profile / container / web-identity
providers, which are exactly what this app runs on (EC2 role, EKS). boto3
already resolves all of those, refreshes them, and is configured the same way
as the rest of the backend, so reuse it.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import boto3
from smithy_aws_core.identity.components import AWSCredentialsIdentity, AWSIdentityProperties
from smithy_core.aio.interfaces.identity import IdentityResolver
from smithy_core.exceptions import SmithyIdentityError


class Boto3CredentialsResolver(IdentityResolver[AWSCredentialsIdentity, AWSIdentityProperties]):
    """Resolve credentials from a boto3 session on every request (boto3 handles refresh)."""

    def __init__(self, session: Optional[boto3.Session] = None):
        self._session = session or boto3.Session()

    async def get_identity(self, *, properties: AWSIdentityProperties) -> AWSCredentialsIdentity:
        creds = await asyncio.to_thread(self._frozen_credentials)
        if creds is None:
            raise SmithyIdentityError("boto3 could not resolve AWS credentials")
        return AWSCredentialsIdentity(
            access_key_id=creds.access_key,
            secret_access_key=creds.secret_key,
            session_token=creds.token,
        )

    def _frozen_credentials(self):
        credentials = self._session.get_credentials()
        return credentials.get_frozen_credentials() if credentials else None
