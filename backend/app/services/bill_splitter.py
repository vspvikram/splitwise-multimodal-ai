"""Bill splitting service"""
import re
from typing import Dict, List, Any, Optional
from loguru import logger


class BillSplitterService:
    def parse_bill_input(self, input_string: str) -> Optional[Dict]:
        """
        Parse the formatted bill input string
        
        Returns:
            A dictionary containing parsed data or None if parsing fails
        """
        try:
            persons_section = re.search(r'--- PERSONS ---\n(.*?)\n--- ITEMS ---', input_string, re.DOTALL)
            items_section = re.search(r'--- ITEMS ---\n(.*?)\n--- FEES ---', input_string, re.DOTALL)
            fees_section = re.search(r'--- FEES ---\n(.*?)\n--- SHARES ---', input_string, re.DOTALL)
            shares_section = re.search(r'--- SHARES ---\n(.*)', input_string, re.DOTALL)

            if not all([persons_section, items_section, fees_section, shares_section]):
                logger.error("Could not find all required sections (--- PERSONS ---, --- ITEMS ---, --- FEES ---, --- SHARES ---).")
                return None

            parsed_data = {'persons': {}, 'items': [], 'fees': {}, 'item_shares': {}}

            # Parse Persons
            for line in persons_section.group(1).strip().split('\n'):
                if ':' in line:
                    abbr, full_name = line.split(':', 1)
                    parsed_data['persons'][abbr.strip()] = full_name.strip()
                elif line.strip():
                    logger.warning(f"Skipping malformed person line: {line}")

            if not parsed_data['persons']:
                logger.error("No persons defined in --- PERSONS --- section.")
                return None

            # Parse Items
            for line in items_section.group(1).strip().split('\n'):
                if ':' in line:
                    name, price_str = line.split(':', 1)
                    try:
                        parsed_data['items'].append({
                            'name': name.strip(), 
                            'price': float(price_str.strip())
                        })
                    except ValueError:
                        logger.error(f"Error parsing item price: {line}")
                        return None
                elif line.strip():
                    logger.warning(f"Skipping malformed item line: {line}")

            if not parsed_data['items']:
                logger.warning("No items found in --- ITEMS --- section.")

            # Parse Fees with expected fee validation
            expected_fees = ['Tax', 'Delivery Fee', 'Tip']
            for line in fees_section.group(1).strip().split('\n'):
                if ':' in line:
                    fee_name, amount_str = line.split(':', 1)
                    fee_name = fee_name.strip()
                    if fee_name in expected_fees:
                        try:
                            parsed_data['fees'][fee_name] = float(amount_str.strip())
                        except ValueError:
                            logger.error(f"Error parsing fee amount for {fee_name}: {line}")
                            return None
                    else:
                        logger.warning(f"Skipping unexpected fee line: {line}")
                elif line.strip():
                    logger.warning(f"Skipping malformed fee line: {line}")

            # Check if all expected fees were found, set missing ones to 0.0
            for fee in expected_fees:
                if fee not in parsed_data['fees']:
                    logger.warning(f"Fee '{fee}' not found in input. Assuming 0.00.")
                    parsed_data['fees'][fee] = 0.0

            # Parse Shares with validation
            all_item_names = {item['name'] for item in parsed_data['items']}
            all_person_abbrs = set(parsed_data['persons'].keys())

            for line in shares_section.group(1).strip().split('\n'):
                if ':' in line:
                    item_name, abbrs_str = line.split(':', 1)
                    item_name = item_name.strip()
                    abbr_list = [abbr.strip() for abbr in abbrs_str.split(',') if abbr.strip()]

                    if item_name not in all_item_names:
                        logger.warning(f"Item '{item_name}' in SHARES section not found in ITEMS.")
                        continue  # Skip this share line if item doesn't exist

                    # Validate abbreviations in shares
                    valid_abbrs = []
                    for abbr in abbr_list:
                        if abbr in all_person_abbrs:
                            valid_abbrs.append(abbr)
                        else:
                            logger.warning(f"Unknown person abbreviation '{abbr}' found for item '{item_name}'. Skipping.")

                    if valid_abbrs:
                        parsed_data['item_shares'][item_name] = valid_abbrs
                    else:
                        logger.warning(f"No valid sharers found for item '{item_name}'. This item cost will not be allocated.")

                elif line.strip():
                    logger.warning(f"Skipping malformed shares line: {line}")

            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing bill input: {e}")
            raise

    def calculate_split(
        self, 
        persons_map: Dict[str, str], 
        items: List[Dict], 
        fees: Dict[str, float], 
        item_shares: Dict[str, List[str]]
    ) -> Dict[str, float]:
        """
        Calculate bill split based on item shares with proper tax distribution
        
        Args:
            persons_map: Dictionary mapping person abbreviations to full names
            items: List of item dictionaries [{'name': str, 'price': float}]
            fees: Dictionary of fees {'Tax': float, 'Delivery Fee': float, 'Tip': float}
            item_shares: Dictionary mapping item names to lists of sharer abbreviations
            
        Returns:
            Dictionary where keys are full person names and values are their total bill amount
        """
        try:
            # Create lookup for item prices
            item_price_lookup = {item['name']: item['price'] for item in items}

            # Get the list of all full person names involved
            all_people = list(persons_map.values())
            all_person_abbrs = set(persons_map.keys())

            # 1. Calculate each person's share of the item costs
            person_item_cost_shares = {full_name: 0.0 for full_name in all_people}
            total_shared_item_cost = 0.0  # Sum of costs of items that were actually shared

            for item_name, sharer_abbrs in item_shares.items():
                item_price = item_price_lookup.get(item_name, 0.0)
                num_sharers = len(sharer_abbrs)

                if num_sharers > 0 and item_price > 0:
                    cost_per_sharer = item_price / num_sharers
                    total_shared_item_cost += item_price  # Add full item price to total shared cost
                    for abbr in sharer_abbrs:
                        full_name = persons_map.get(abbr)
                        if full_name:  # Make sure abbr was valid
                            person_item_cost_shares[full_name] += cost_per_sharer

            # 2. Calculate tax shares (proportional to item cost shares)
            total_tax = fees.get('Tax', 0.0)
            person_tax_shares = {full_name: 0.0 for full_name in all_people}

            # Tax is proportional to the person's share of the total cost of the shared items
            if total_shared_item_cost > 0:
                for full_name, item_cost_share in person_item_cost_shares.items():
                    person_tax_shares[full_name] = (item_cost_share / total_shared_item_cost) * total_tax
            elif total_tax > 0:
                logger.warning("Total cost of shared items is 0, but total tax is non-zero. Tax is not allocated proportionally.")

            # 3. Calculate equal shares for delivery and tip
            total_other_fees = fees.get('Delivery Fee', 0.0) + fees.get('Tip', 0.0)
            num_people = len(all_people)
            equal_fee_share = total_other_fees / num_people if num_people > 0 else 0

            # 4. Calculate total bill for each person
            person_total_bills = {}
            
            logger.info("\n--- Bill Breakdown ---")
            for full_name in all_people:
                item_share = person_item_cost_shares.get(full_name, 0.0)
                tax_share = person_tax_shares.get(full_name, 0.0)
                fees_share = equal_fee_share  # Everyone pays the same share of other fees

                total_bill = item_share + tax_share + fees_share
                person_total_bills[full_name] = total_bill

                logger.info(f"{full_name}:")
                logger.info(f"  Item Share: ${item_share:.2f}")
                logger.info(f"  Tax Share: ${tax_share:.2f}")
                logger.info(f"  Delivery/Tip Share: ${fees_share:.2f}")
                logger.info(f"  Total: ${total_bill:.2f}")
                logger.info("-" * 20)

            # 5. Verification
            original_total_item_cost = sum(item['price'] for item in items)
            original_total_bill = original_total_item_cost + total_tax + total_other_fees
            calculated_total_bill = sum(person_total_bills.values())

            logger.info(f"Calculated Total Bill: ${calculated_total_bill:.2f}")
            logger.info(f"Original Total Bill:   ${original_total_bill:.2f}")

            # Allow for minor floating point differences
            if abs(calculated_total_bill - original_total_bill) > 0.01:
                logger.warning("Calculated total does not match original total! There might be unassigned items.")
                unassigned_items = [item['name'] for item in items if item['name'] not in item_shares]
                if unassigned_items:
                    logger.warning(f"Unassigned items (cost not allocated): {', '.join(unassigned_items)}")

            return person_total_bills

        except Exception as e:
            logger.error(f"Error calculating split: {e}")
            raise


# Global service instance
bill_splitter_service = BillSplitterService()