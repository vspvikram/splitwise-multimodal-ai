from pydantic import BaseModel
from typing import Optional, Dict, List
from .bill_models import SplitwiseFormattedOutput


class ProcessBillRequest(BaseModel):
    user_description: str
    feedback: Optional[str] = None
    previous_output: Optional[str] = None


class ProcessBillResponse(BaseModel):
    success: bool
    message: str
    structured_object: Optional[SplitwiseFormattedOutput] = None
    formatted_output: Optional[str] = None
    error: Optional[str] = None


class CalculateSplitRequest(BaseModel):
    formatted_output: str


class CalculateSplitResponse(BaseModel):
    success: bool
    message: str
    splits: Optional[Dict[str, float]] = None
    total_bill: Optional[float] = None
    parsed_data: Optional[Dict] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    message: str
    version: str