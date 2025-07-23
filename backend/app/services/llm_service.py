"""LLM service for bill processing"""
import asyncio
from typing import List, Tuple, Union, Optional
from loguru import logger
from pydantic_ai import Agent, RunContext, BinaryContent

from ..models.bill_models import SplitwiseFormattedOutput, FeeCategorization, FeeItem, DependencySplitwiseDeps
from .llm_factory import get_model, LLMProviderType


class LLMService:
    def __init__(self):
        """Initialize LLM service with agents"""
        try:
            self.llm_model = get_model(
                model_name="gpt-4o", provider_type=LLMProviderType.AZURE_OPENAI
            )
            
            # Initialize agents
            self._init_bill_parser_agent()
            self._init_fee_categorizer_agent()
            
            logger.info("LLM Service initialized successfully")
            
        except Exception as e:
            logger.error(f"FATAL ERROR: Could not initialize LLM model: {e}")
            raise SystemExit(f"Failed to load the LLM model: {e}")
    
    def _init_bill_parser_agent(self):
        """Initialize bill parser agent"""
        self.bill_parser_agent = Agent(
            self.llm_model,
            output_type=SplitwiseFormattedOutput,
            output_retries=3,
            deps_type=DependencySplitwiseDeps
        )
        
        bill_parser_prompt = """
You are a receipt parser that extracts basic information from bills.

IMPORTANT: You may receive multiple images of the same bill/receipt (different pages, angles, or sections). 
Analyze ALL images together to get the complete picture.

Your task:
1. Extract people from the user description and assign unique abbreviations (V, A, etc.)
2. Read EVERY line item across ALL receipt images, capture name and exact price
3. Extract ALL fees/charges/taxes/discounts from ALL images as raw items - don't categorize them yet
4. Map each item to people who shared it based on the description

For fees/charges/discounts:
- Extract the exact name as shown on receipt(s)
- Extract the exact amount (use negative values for discounts/credits)
- Put ALL fees in the "tax_items" category for now (categorization happens later)
- If you see the same fee in multiple images, only include it ONCE

Note: **Only add fees and items that are explicitly mentioned in the receipt(s).**

Return structured data with:
- persons: dict mapping abbreviations to full names
- items: list of dicts with "name" and "price" keys (NO DUPLICATES across images)
- fees: dict with "Tax", "Delivery Fee", "Tip" all set to 0.0
- item_shares: dict mapping item names to lists of person abbreviations
- raw_fees: FeeCategorization object with all fees in tax_items, delivery_items and tip_items empty

Focus on accuracy of extraction, not categorization. Combine information from all images intelligently.
"""
        
        @self.bill_parser_agent.instructions
        def bill_parser_system_prompt(ctx: RunContext[DependencySplitwiseDeps]):
            return bill_parser_prompt
    
    def _init_fee_categorizer_agent(self):
        """Initialize fee categorizer agent"""
        self.fee_categorizer_agent = Agent(
            self.llm_model,
            output_type=FeeCategorization,
            output_retries=3,
            deps_type=List[FeeItem]
        )
        
        fee_categorizer_prompt = """
You are a fee categorization specialist.

IMPORTANT: You will receive a list of fees that were ALL temporarily placed in the "tax_items" category. Your job is to re-categorize them correctly.

RULES:
1. You must ONLY categorize the exact fees provided to you - DO NOT add any new fees
2. You must categorize ALL provided fees - DO NOT omit any fees
3. Use the exact fee names and amounts as provided

Categorization Rules (STRICT):
- Tax: DEFAULT category - Sales tax, VAT, membership benefits, special offers, coupons, store discounts, promotional discounts, credits, loyalty rewards, cashback, service fees, processing fees, and ANY fee that is NOT explicitly delivery or tip related
- Delivery Fee: ONLY if fee name explicitly contains: "delivery", "shipping", "transport", "courier"
- Tip: ONLY if fee name explicitly contains: "tip", "gratuity"

RULE: When in doubt, always use Tax category. Only use Delivery Fee or Tip if the fee name clearly indicates it.

Examples:
- "Membership Benefit: -$6.00" → Tax
- "Special Offers: -$3.00" → Tax  
- "Service Fee: $2.00" → Tax
- "Processing Fee: $1.50" → Tax
- "Delivery Fee: $4.99" → Delivery Fee
- "Free Delivery: -$4.99" → Delivery Fee
- "Driver Tip: $5.00" → Tip
- "Gratuity: $3.00" → Tip

Return FeeCategorization object with the EXACT SAME fees distributed across tax_items, delivery_items, and tip_items.
"""
        
        @self.fee_categorizer_agent.instructions  
        def fee_categorizer_system_prompt(ctx: RunContext[List[FeeItem]]):
            fees_list = ctx.deps
            fee_details = "\n".join([f"- {fee.name}: ${fee.amount:.2f}" for fee in fees_list])
            
            return f"""{fee_categorizer_prompt}

FEES TO CATEGORIZE (exactly {len(fees_list)} fees):
{fee_details}

You must categorize exactly these {len(fees_list)} fees and no others.
"""
    
    async def process_bill(
        self, 
        image_bytes_list: List[bytes], 
        user_description: str,
        feedback: str = None,
        previous_output: str = None
    ) -> Tuple[SplitwiseFormattedOutput, str]:
        """
        Process bill images using LLM agents
        
        Args:
            image_bytes_list: List of image bytes
            user_description: User's description of who shared what
            feedback: Optional feedback for regeneration
            previous_output: Previous output for comparison
            
        Returns:
            Tuple of (structured_object, formatted_string)
        """
        try:
            logger.info(f"Processing {len(image_bytes_list)} image(s)")
            
            # Handle backward compatibility - convert single bytes to list if needed
            if isinstance(image_bytes_list, bytes):
                image_bytes_list = [image_bytes_list]
            
            # Create dependency object for bill parser
            deps = DependencySplitwiseDeps(
                image_bytes_list=image_bytes_list,
                user_description=user_description,
                feedback=feedback,
                previous_output=previous_output
            )
            
            # Build the user prompt with feedback if provided
            num_images = len(image_bytes_list)
            user_prompt = f"Process these {num_images} receipt image(s) using the split description: {user_description}"
            
            if feedback and previous_output:
                user_prompt += f"\n\nPrevious output had issues: {feedback}\nPrevious output was: {previous_output}\nPlease improve based on this feedback."
            
            # Step 1: Extract basic bill information from all images
            logger.info(f"Step 1: Extracting bill information from {num_images} image(s)...")
            
            # Create message list with user prompt and all images
            messages = [user_prompt]
            for i, image_bytes in enumerate(image_bytes_list):
                messages.append(BinaryContent(data=image_bytes, media_type="image/png"))
            
            bill_result = await self.bill_parser_agent.run(
                messages,
                deps=deps,
            )
            
            bill_data: SplitwiseFormattedOutput = bill_result.output
            
            # Step 2: Categorize extracted fees if any exist
            all_raw_fees = (bill_data.raw_fees.tax_items + 
                           bill_data.raw_fees.delivery_items + 
                           bill_data.raw_fees.tip_items)
            
            if all_raw_fees:
                logger.info(f"Step 2: Categorizing {len(all_raw_fees)} fees...")
                logger.debug(f"Fees to categorize: {[f'{fee.name}: ${fee.amount:.2f}' for fee in all_raw_fees]}")
                
                categorization_result = await self.fee_categorizer_agent.run(
                    f"Categorize these {len(all_raw_fees)} fees according to the strict rules. Do not add or remove any fees.",
                    deps=all_raw_fees
                )
                
                # Validate that no fees were added or removed
                categorized_fees = (categorization_result.output.tax_items + 
                                  categorization_result.output.delivery_items + 
                                  categorization_result.output.tip_items)
                
                if len(categorized_fees) != len(all_raw_fees):
                    logger.warning(f"Fee count mismatch! Input: {len(all_raw_fees)}, Output: {len(categorized_fees)}")
                    logger.warning(f"Input fees: {[f.name for f in all_raw_fees]}")
                    logger.warning(f"Output fees: {[f.name for f in categorized_fees]}")
                    logger.warning("Falling back to original categorization...")
                else:
                    bill_data.raw_fees = categorization_result.output
                    logger.info("Fee categorization successful!")
            
            # Step 3: Calculate totals using the model's method
            calculated_fees = bill_data.raw_fees.calculate_totals()
            bill_data.fees = calculated_fees
            
            # Format as your bill parser expects
            formatted_output = f"""--- PERSONS ---
{chr(10).join([f"{abbr}: {name}" for abbr, name in bill_data.persons.items()])}

--- ITEMS ---
{chr(10).join([f"{item['name']}: {item['price']}" for item in bill_data.items])}

--- FEES ---
Tax: {calculated_fees['Tax']:.2f}
Delivery Fee: {calculated_fees['Delivery Fee']:.2f}
Tip: {calculated_fees['Tip']:.2f}

--- SHARES ---
{chr(10).join([f"{item}: {', '.join(sharers)}" for item, sharers in bill_data.item_shares.items()])}"""
            
            return bill_data, formatted_output
            
        except Exception as e:
            logger.error(f"Error in LLM processing: {e}")
            # Return empty object with error
            empty_object = SplitwiseFormattedOutput(
                persons={}, items=[], fees={}, item_shares={}, 
                raw_fees=FeeCategorization(tax_items=[], delivery_items=[], tip_items=[])
            )
            error_msg = f"Error: Failed to process bill data - {str(e)}"
            return empty_object, error_msg


# Global service instance
llm_service = LLMService()