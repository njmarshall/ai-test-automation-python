"""
models.py : prior authorization domain
-----------------------------------------
Pydantic models for the prior-authorization sandbox.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PriorAuthStatus(str, Enum):
    SUBMITTED      = "SUBMITTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED       = "APPROVED"
    DENIED         = "DENIED"


class NotificationChannel(str, Enum):
    PORTAL = "PORTAL"
    EMAIL  = "EMAIL"


class NotificationRecipient(str, Enum):
    PATIENT  = "PATIENT"
    PROVIDER = "PROVIDER"


class PriorAuthSubmission(BaseModel):
    patient_id:            str = Field(min_length=1)
    patient_name:          str = Field(min_length=1)
    provider_id:           str = Field(min_length=1)
    procedure_code:        str = Field(min_length=1)
    procedure_description: str = Field(min_length=1)
    diagnosis_code:        str = Field(min_length=1)


class PriorAuthRequest(BaseModel):
    request_id:            str
    patient_id:            str
    patient_name:          str
    provider_id:           str
    procedure_code:        str
    procedure_description: str
    diagnosis_code:        str
    status:                PriorAuthStatus
    created_at:            datetime
    authorization_number:  Optional[str] = None
    denial_reason:         Optional[str] = None


class ReviewDecisionRequest(BaseModel):
    approve:     bool
    reviewer_id: str = Field(min_length=1)
    reason:      Optional[str] = None


class NotificationRecord(BaseModel):
    notification_id:               str
    request_id:                    str
    recipient:                     NotificationRecipient
    channel:                       NotificationChannel
    message:                       str
    includes_authorization_number: bool
    includes_denial_reason:        bool
    sent_at:                       datetime
