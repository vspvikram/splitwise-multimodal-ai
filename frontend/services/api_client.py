import requests
import streamlit as st
from typing import List, Optional, Dict, Any, Tuple
from io import BytesIO
from loguru import logger
import os


class APIClient:
    def __init__(self):
        # Use environment variable for backend URL, fallback to localhost
        self.base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
        self.session = requests.Session()
    
    def health_check(self) -> bool:
        """Check if backend API is healthy"""
        try:
            # Fixed: Correct API path
            response = self.session.get(f"{self.base_url}/api/v1/bills/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def process_bill(
        self, 
        image_files: List[BytesIO], 
        user_description: str,
        feedback: Optional[str] = None,
        previous_output: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Send bill images to backend for processing
        
        Returns:
            Tuple of (success, response_data)
        """
        try:
            # Prepare files for upload
            files = []
            for i, image_file in enumerate(image_files):
                image_file.seek(0)  # Reset file pointer
                files.append(
                    ('files', (f'image_{i}.png', image_file, 'image/png'))
                )
            
            # Prepare form data
            data = {
                'user_description': user_description
            }
            if feedback:
                data['feedback'] = feedback
            if previous_output:
                data['previous_output'] = previous_output
            
            # Make request
            # Fixed: Correct API path
            response = self.session.post(
                f"{self.base_url}/api/v1/bills/process",
                files=files,
                data=data,
                timeout=60  # Longer timeout for LLM processing
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                logger.error(f"API request failed: {response.status_code}")
                return False, {"error": f"Request failed with status {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error calling process_bill API: {e}")
            return False, {"error": str(e)}
    
    def calculate_split(self, formatted_output: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Calculate bill split from formatted output
        
        Returns:
            Tuple of (success, response_data)
        """
        try:
            # Fixed: Correct API path
            response = self.session.post(
                f"{self.base_url}/api/v1/bills/calculate-split",
                json={"formatted_output": formatted_output},
                timeout=30
            )
            
            if response.status_code == 200:
                return True, response.json()
            else:
                logger.error(f"Split calculation failed: {response.status_code}")
                return False, {"error": f"Request failed with status {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error calling calculate_split API: {e}")
            return False, {"error": str(e)}


# Global API client instance
@st.cache_resource
def get_api_client():
    return APIClient()