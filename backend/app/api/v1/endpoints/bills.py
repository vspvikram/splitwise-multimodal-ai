from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from typing import List, Optional
import aiofiles
from loguru import logger

from ....models.response_models import (
    ProcessBillResponse, 
    CalculateSplitRequest, 
    CalculateSplitResponse
)
from ....services.llm_service import llm_service
from ....services.bill_splitter import bill_splitter_service
from ....core.config import settings

router = APIRouter()


@router.post("/process", response_model=ProcessBillResponse)
async def process_bill(
    files: List[UploadFile] = File(...),
    user_description: str = Form(...),
    feedback: Optional[str] = Form(None),
    previous_output: Optional[str] = Form(None)
):
    """
    Process uploaded bill images and extract structured data
    """
    try:
        # Validate files
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        for file in files:
            if file.content_type not in settings.allowed_file_types:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File type {file.content_type} not allowed"
                )
            
            if file.size > settings.max_file_size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"File size exceeds maximum allowed size"
                )
        
        # Read image bytes
        image_bytes_list = []
        for file in files:
            content = await file.read()
            image_bytes_list.append(content)
        
        # Process with LLM
        structured_object, formatted_output = await llm_service.process_bill(
            image_bytes_list=image_bytes_list,
            user_description=user_description,
            feedback=feedback,
            previous_output=previous_output
        )
        
        return ProcessBillResponse(
            success=True,
            message="Bill processed successfully",
            structured_object=structured_object,
            formatted_output=formatted_output
        )
        
    except Exception as e:
        logger.error(f"Error processing bill: {e}")
        return ProcessBillResponse(
            success=False,
            message="Failed to process bill",
            error=str(e)
        )


@router.post("/calculate-split", response_model=CalculateSplitResponse)
async def calculate_split(request: CalculateSplitRequest):
    """
    Calculate bill split from formatted output
    """
    try:
        # Parse the formatted output
        parsed_data = bill_splitter_service.parse_bill_input(request.formatted_output)
        
        # Calculate splits
        splits = bill_splitter_service.calculate_split(
            persons_map=parsed_data['persons'],
            items=parsed_data['items'],
            fees=parsed_data['fees'],
            item_shares=parsed_data['item_shares']
        )
        
        total_bill = sum(splits.values())
        
        return CalculateSplitResponse(
            success=True,
            message="Split calculated successfully",
            splits=splits,
            total_bill=total_bill,
            parsed_data=parsed_data
        )
        
    except Exception as e:
        logger.error(f"Error calculating split: {e}")
        return CalculateSplitResponse(
            success=False,
            message="Failed to calculate split",
            error=str(e)
        )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "Splitwise API is running",
        "version": settings.app_version
    }