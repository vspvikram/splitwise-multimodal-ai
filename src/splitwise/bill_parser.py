import re

def parse_bill_input(input_string):
    """
    Parses the input string containing person abbreviations, item details, fees,
    and item-sharing information using abbreviations.

    Args:
        input_string: A multiline string in the specified format.

    Returns:
        A dictionary containing parsed data:
        {'persons': {abbr: full_name, ...},
         'items': [{'name': str, 'price': float}, ...],
         'fees': {'Tax': float, 'Delivery Fee': float, 'Tip': float},
         'item_shares': {item_name: [abbr, ...], ...}}
        Returns None if parsing fails critically.
    """
    persons_section = re.search(r'--- PERSONS ---\n(.*?)\n--- ITEMS ---', input_string, re.DOTALL)
    items_section = re.search(r'--- ITEMS ---\n(.*?)\n--- FEES ---', input_string, re.DOTALL)
    fees_section = re.search(r'--- FEES ---\n(.*?)\n--- SHARES ---', input_string, re.DOTALL)
    shares_section = re.search(r'--- SHARES ---\n(.*)', input_string, re.DOTALL)

    if not all([persons_section, items_section, fees_section, shares_section]):
        print("Error: Could not find all required sections (--- PERSONS ---, --- ITEMS ---, --- FEES ---, --- SHARES ---).")
        return None

    parsed_data = {'persons': {}, 'items': [], 'fees': {}, 'item_shares': {}}

    # Parse Persons
    for line in persons_section.group(1).strip().split('\n'):
        if ':' in line:
            abbr, full_name = line.split(':', 1)
            parsed_data['persons'][abbr.strip()] = full_name.strip()
        elif line.strip():
             print(f"Warning: Skipping malformed person line: {line}")

    if not parsed_data['persons']:
        print("Error: No persons defined in --- PERSONS --- section.")
        return None

    # Parse Items
    for line in items_section.group(1).strip().split('\n'):
        if ':' in line:
            name, price_str = line.split(':', 1)
            try:
                parsed_data['items'].append({'name': name.strip(), 'price': float(price_str.strip())})
            except ValueError:
                print(f"Error parsing item price: {line}")
                return None
        elif line.strip():
             print(f"Warning: Skipping malformed item line: {line}")

    if not parsed_data['items']:
         print("Warning: No items found in --- ITEMS --- section.")


    # Parse Fees
    expected_fees = ['Tax', 'Delivery Fee', 'Tip']
    for line in fees_section.group(1).strip().split('\n'):
        if ':' in line:
            fee_name, amount_str = line.split(':', 1)
            fee_name = fee_name.strip()
            if fee_name in expected_fees:
                try:
                    parsed_data['fees'][fee_name] = float(amount_str.strip())
                except ValueError:
                    print(f"Error parsing fee amount for {fee_name}: {line}")
                    return None
            else:
                 print(f"Warning: Skipping unexpected fee line: {line}")
        elif line.strip():
             print(f"Warning: Skipping malformed fee line: {line}")

    # Check if all expected fees were found
    for fee in expected_fees:
        if fee not in parsed_data['fees']:
            print(f"Warning: Fee '{fee}' not found in input. Assuming 0.00.")
            parsed_data['fees'][fee] = 0.0

    # Parse Shares (Item -> List of Abbrs)
    all_item_names = {item['name'] for item in parsed_data['items']}
    all_person_abbrs = set(parsed_data['persons'].keys())

    for line in shares_section.group(1).strip().split('\n'):
        if ':' in line:
            item_name, abbrs_str = line.split(':', 1)
            item_name = item_name.strip()
            abbr_list = [abbr.strip() for abbr in abbrs_str.split(',') if abbr.strip()]

            if item_name not in all_item_names:
                print(f"Warning: Item '{item_name}' in SHARES section not found in ITEMS.")
                continue # Skip this share line if item doesn't exist

            # Validate abbreviations in shares
            valid_abbrs = []
            for abbr in abbr_list:
                if abbr in all_person_abbrs:
                    valid_abbrs.append(abbr)
                else:
                    print(f"Warning: Unknown person abbreviation '{abbr}' found for item '{item_name}'. Skipping.")

            if valid_abbrs:
                 parsed_data['item_shares'][item_name] = valid_abbrs
            else:
                 print(f"Warning: No valid sharers found for item '{item_name}'. This item cost will not be allocated.")

        elif line.strip():
             print(f"Warning: Skipping malformed shares line: {line}")

    return parsed_data

def split_instacart_bill(persons_map, items, fees, item_shares):
    """
    Calculates each person's share of the Instacart bill based on item shares.

    Args:
        persons_map: Dictionary mapping person abbreviations to full names.
        items: List of item dictionaries [{'name': str, 'price': float}].
        fees: Dictionary of fees {'Tax': float, 'Delivery Fee': float, 'Tip': float}.
        item_shares: Dictionary mapping item names to lists of sharer abbreviations.

    Returns:
        A dictionary where keys are full person names and values are their total bill amount.
        Also prints a breakdown.
    """
    # Create lookup for item prices
    item_price_lookup = {item['name']: item['price'] for item in items}

    # Get the list of all full person names involved (from the PERSONS section)
    all_people = list(persons_map.values())
    all_person_abbrs = set(persons_map.keys()) # Need set for quick lookup

    # 1. Calculate each person's share of the item costs
    # This time, iterate through items first
    person_item_cost_shares = {full_name: 0.0 for full_name in all_people}
    total_shared_item_cost = 0.0 # Sum of costs of items that were actually shared

    for item_name, sharer_abbrs in item_shares.items():
        item_price = item_price_lookup.get(item_name, 0.0) # Use .get for safety
        num_sharers = len(sharer_abbrs)

        if num_sharers > 0 and item_price > 0:
             cost_per_sharer = item_price / num_sharers
             total_shared_item_cost += item_price # Add full item price to total shared cost
             for abbr in sharer_abbrs:
                 full_name = persons_map.get(abbr) # Get full name from abbr
                 if full_name: # Make sure abbr was valid
                      person_item_cost_shares[full_name] += cost_per_sharer
                 # else: Warning was already printed in parse_bill_input


    # 2. Calculate total tax and tax share per person
    total_tax = fees.get('Tax', 0.0)
    person_tax_shares = {full_name: 0.0 for full_name in all_people}

    # Tax is proportional to the person's share of the total cost of the *shared* items
    # The sum of person_item_cost_shares should equal total_shared_item_cost
    # Note: total_item_cost (sum of *all* items) is not used for tax proportionality here,
    # only the sum of items that actually had sharers assigned.
    # If tax applies to the *entire* bill including items nobody claimed, the logic needs adjustment.
    # Assuming tax only applies to items claimed/shared:
    if total_shared_item_cost > 0:
         for full_name, item_cost_share in person_item_cost_shares.items():
            person_tax_shares[full_name] = (item_cost_share / total_shared_item_cost) * total_tax
    elif total_tax > 0:
         print("Warning: Total cost of shared items is 0, but total tax is non-zero. Tax is not allocated proportionally.")


    # 3. Calculate total other fees (Delivery + Tip) and equal share per person
    total_other_fees = fees.get('Delivery Fee', 0.0) + fees.get('Tip', 0.0)
    num_people = len(all_people) # Use the count from the PERSONS section
    equal_fee_share = total_other_fees / num_people if num_people > 0 else 0

    # 4. Calculate total bill for each person
    person_total_bills = {}
    print("\n--- Bill Breakdown ---")
    for full_name in all_people:
        item_share = person_item_cost_shares.get(full_name, 0.0)
        tax_share = person_tax_shares.get(full_name, 0.0)
        fees_share = equal_fee_share # Everyone pays the same share of other fees

        total_bill = item_share + tax_share + fees_share
        person_total_bills[full_name] = total_bill

        print(f"{full_name}:")
        print(f"  Item Share: ${item_share:.2f}")
        print(f"  Tax Share: ${tax_share:.2f}")
        print(f"  Delivery/Tip Share: ${fees_share:.2f}")
        print(f"  Total: ${total_bill:.2f}")
        print("-" * 20)


    # Optional: Verification
    # The sum of person_item_cost_shares + tax + other fees should equal the original total
    original_total_item_cost = sum(item['price'] for item in items)
    original_total_bill = original_total_item_cost + total_tax + total_other_fees
    calculated_total_bill = sum(person_total_bills.values())

    print(f"Calculated Total Bill: ${calculated_total_bill:.2f}")
    print(f"Original Total Bill:   ${original_total_bill:.2f}")

    # Allow for minor floating point differences
    if abs(calculated_total_bill - original_total_bill) > 0.01:
        print("Warning: Calculated total does not match original total! There might be unassigned items.")
        unassigned_items = [item['name'] for item in items if item['name'] not in item_shares]
        if unassigned_items:
             print(f"Unassigned items (cost not allocated): {', '.join(unassigned_items)}")


    return person_total_bills

# --- How to use the script ---

# 1. Paste your bill information into this multiline string
#    Use the new format with --- PERSONS --- and Item: Abbr, Abbr in --- SHARES ---
# bill_input_data = """
# --- PERSONS ---
# A: Alice
# B: Bob
# C: Charlie

# --- ITEMS ---
# Apple: 1.00
# Banana: 2.00
# Orange: 3.00

# --- FEES ---
# Tax: 0.60
# Delivery Fee: 3.00
# Tip: 3.00

# --- SHARES ---
# Apple: A, B
# Banana: B, C
# Orange: A, B, C
# """
if __name__ == "__main__":
    bill_input_data = """--- PERSONS ---
    V: Vikram
    A: Aniket
    --- ITEMS ---
    oat milk: 11.98
    strawberries: 3.49
    tote bag: 2.99
    avocado bag: 4.99
    banana: 2.32
    mandarin bag: 4.99
    raspberries: 6.99
    eggs: 12.29
    cherries: 11.33
    --- FEES ---
    Tax: 0.20
    --- SHARES ---
    oat milk: V, A
    strawberries: V, A
    tote bag: V, A
    avocado bag: A
    banana: V, A
    mandarin bag: V, A
    raspberries: V, A
    eggs: V, A
    cherries: V
    """


    # 2. Parse the input data
    parsed_data = parse_bill_input(bill_input_data)

    # 3. If parsing was successful, split the bill
    if parsed_data:
        persons_map = parsed_data['persons']
        items_list = parsed_data['items']
        fees_dict = parsed_data['fees']
        item_shares_dict = parsed_data['item_shares'] # This is the new structure

        individual_shares = split_instacart_bill(persons_map, items_list, fees_dict, item_shares_dict)

        # You can now use the individual_shares dictionary if needed
        # print("\nSummary:")
        # for person, total in individual_shares.items():
        #     print(f"{person} owes: ${total:.2f}")