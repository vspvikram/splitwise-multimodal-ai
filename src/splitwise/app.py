# app.py
import streamlit as st
from PIL import Image
from loguru import logger
import io
import time
from src.splitwise.llm_handler import call_llm_api_sync
from src.splitwise.bill_parser import parse_bill_input, split_instacart_bill

# logger configuration
logger.add("splitwise.log", rotation="1 MB", level="DEBUG")

st.set_page_config(
    page_title="Bill Splitter", 
    layout="centered",
    page_icon="🧾",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        border-radius: 10px;
        border: 2px solid #f0f2f6;
        background-color: white;
        color: #262730;
        font-weight: 500;
    }
    .stButton > button:hover {
        border-color: #ff6b6b;
        color: #ff6b6b;
    }
    .success-button > button {
        background-color: #28a745;
        color: white;
        border-color: #28a745;
    }
    .warning-button > button {
        background-color: #ffc107;
        color: #212529;
        border-color: #ffc107;
    }
    .step-indicator {
        text-align: center;
        margin: 20px 0;
        padding: 10px;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    .item-share-card {
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 8px;
        margin: 5px 0;
        background-color: #f9f9f9;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧾 Smart Bill Splitter with AI")

# Step indicator
steps = ["📤 Upload & Describe", "🔍 Review Results", "💰 Calculate Split", "📝 Feedback"]
current_step = st.session_state.get("step", 1)

st.markdown('<div class="step-indicator">', unsafe_allow_html=True)
progress_text = " → ".join([f"**{step}**" if i+1 == current_step else step for i, step in enumerate(steps)])
st.markdown(progress_text, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Add progress bar
progress = min(current_step / len(steps), 1.0)
st.progress(progress)

# --- Session State ---
if "step" not in st.session_state:
    st.session_state.step = 1
if "structured_output" not in st.session_state:
    st.session_state.structured_output = None
if "structured_object" not in st.session_state:
    st.session_state.structured_object = None
if "final_output" not in st.session_state:
    st.session_state.final_output = None
if "image_bytes" not in st.session_state:
    st.session_state.image_bytes = None
if "user_description" not in st.session_state:
    st.session_state.user_description = ""

# --- Session State - Update to handle multiple images ---
if "image_bytes_list" not in st.session_state:
    st.session_state.image_bytes_list = None

# --- Step 1: Upload + Description ---
if st.session_state.step == 1:
    st.subheader("📤 Step 1: Upload Your Bill")
    
    # Help section
    with st.expander("💡 How to use this app"):
        st.markdown("""
        1. **Upload clear photos** of your bill/receipt (you can upload multiple images)
        2. **Describe who shared what** - be specific!
        3. **Review the AI results** and provide feedback if needed
        4. **Get your split calculation** automatically
        
        **Multiple Images:** If your bill spans multiple pages or you have separate receipt images, upload them all!
        
        **Example description:**
        "Vikram and Alice shared the pizza and drinks. Vikram had the salad alone. Alice had the dessert alone."
        """)
    
    # Multiple file upload
    uploaded_files = st.file_uploader(
        "Upload bill images", 
        type=["jpg", "png", "jpeg"],
        accept_multiple_files=True,  # Enable multiple file upload
        help="Upload clear photos of your receipt(s). You can select multiple images. JPG, PNG, and JPEG formats are supported."
    )
    
    # Show image previews for all uploaded files
    if uploaded_files:
        st.markdown(f"**📸 Uploaded Images ({len(uploaded_files)} files):**")
        
        # Create columns for image display (max 3 per row)
        cols_per_row = 3
        for i in range(0, len(uploaded_files), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, uploaded_file in enumerate(uploaded_files[i:i+cols_per_row]):
                with cols[j]:
                    image = Image.open(uploaded_file)
                    st.image(image, caption=f"Image {i+j+1}: {uploaded_file.name}", use_container_width=True)
    
    # Description with better prompts
    user_description = st.text_area(
        "Describe who shared what",
        placeholder="Example: Vikram and Alice shared the pizza. Vikram had the burger alone. Alice had the salad alone.",
        help="Be specific about which items each person consumed. Use full names for clarity.",
        height=100,
        key="user_description_input"
    )
    
    # Validation for multiple files
    can_process = uploaded_files is not None and len(uploaded_files) > 0 and st.session_state.user_description_input.strip() != ""
    
    if not can_process:
        if not uploaded_files or len(uploaded_files) == 0:
            st.warning("⚠️ Please upload at least one image.")
        if st.session_state.user_description_input.strip() == "":
            st.warning("⚠️ Please provide a description to continue.")
    
    # Process multiple images
    if can_process:
        st.markdown('<div class="success-button">', unsafe_allow_html=True)
        if st.button("🚀 Generate Structured Output"):
            logger.info(f"Processing {len(uploaded_files)} uploaded bill images")
            logger.debug(f"User description: {st.session_state.user_description_input}")

            # Convert all images to bytes
            image_bytes_list = []
            for uploaded_file in uploaded_files:
                image = Image.open(uploaded_file)
                image_bytes = io.BytesIO()
                image.save(image_bytes, format='PNG')
                image_bytes_list.append(image_bytes.getvalue())
            
            # Store in session state for feedback functionality
            st.session_state.image_bytes_list = image_bytes_list
            st.session_state.user_description = st.session_state.user_description_input

            with st.spinner(f"🤖 AI is analyzing your {len(uploaded_files)} receipt image(s)..."):
                try:
                    structured_object, structured_output = call_llm_api_sync(
                        image_bytes_list, st.session_state.user_description_input
                    )
                    if structured_object and structured_output:
                        st.session_state.structured_object = structured_object
                        st.session_state.structured_output = structured_output
                        st.session_state.step = 2
                        st.success("✅ Receipt(s) processed successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to process receipt(s). Please try again.")
                except Exception as e:
                    st.error(f"❌ Error processing receipt(s): {str(e)}")
                    logger.error(f"Processing error: {e}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.button("🚀 Generate Structured Output", disabled=True)

# --- Step 2: Review Structured Output ---
elif st.session_state.step == 2:
    st.subheader("🔍 Step 2: Review AI Results")
    
    # Tabs for better organization
    tab1, tab2, tab3 = st.tabs(["📋 Structured Data", "📊 Visual Breakdown", "🔧 Raw Output"])
    
    with tab1:
        if st.session_state.structured_object:
            obj = st.session_state.structured_object
            
            # People section with cards
            st.markdown("### 👥 People")
            cols = st.columns(len(obj.persons))
            for i, (abbr, name) in enumerate(obj.persons.items()):
                with cols[i]:
                    st.markdown(f"""
                    <div style="padding:10px; border:1px solid #ddd; border-radius:5px; text-align:center; margin:5px;">
                        <h4>{abbr}</h4>
                        <p>{name}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # FIX #1: Items with sharing information - Fix card text visibility
            st.markdown("### 🛒 Items & Sharing")
            for item in obj.items:
                item_name = item['name']
                item_price = item['price']
                
                # Get who shares this item
                sharers = obj.item_shares.get(item_name, [])
                sharer_names = [obj.persons.get(abbr, abbr) for abbr in sharers]
                
                st.markdown(f"""
                <div style="padding:10px; border:1px solid #ddd; border-radius:8px; margin:5px 0; background-color:#ffffff; color:#000000;">
                    <strong style="color:#333333;">{item_name}</strong> - <span style="color:#28a745; font-weight:bold;">${item_price:.2f}</span><br>
                    <small style="color:#666666;">👥 Shared by: {', '.join(sharer_names) if sharer_names else 'No one assigned'}</small>
                </div>
                """, unsafe_allow_html=True)
            
            # FIX #5: Fee breakdown with explanatory text AND detailed breakdown
            st.markdown("### 💳 Fee Categories (AI Processed)")
            st.markdown("*These are automatically calculated totals from individual receipt fees*")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                tax_amount = obj.fees.get('Tax', 0)
                st.metric("Tax (Proportional)", f"${tax_amount:.2f}", 
                         help="Sales tax, discounts, credits - distributed proportionally based on items consumed")
                
            with col2:
                delivery_amount = obj.fees.get('Delivery Fee', 0)
                st.metric("Delivery (Equal Split)", f"${delivery_amount:.2f}",
                         help="Delivery charges and related fees - split equally among all people")
                
            with col3:
                tip_amount = obj.fees.get('Tip', 0)
                st.metric("Tip (Equal Split)", f"${tip_amount:.2f}",
                         help="Tips and gratuity - split equally among all people")
            
            # NEW: Detailed fee breakdown showing what went into each category
            st.markdown("---")
            st.markdown("### 🔍 Fee Category Breakdown")
            st.markdown("*See which original receipt fees were categorized into each type*")
            
            # Create expandable sections for each fee category
            if obj.raw_fees.tax_items:
                with st.expander(f"📊 Tax Items ({len(obj.raw_fees.tax_items)} fees totaling ${sum(fee.amount for fee in obj.raw_fees.tax_items):.2f})"):
                    for fee in obj.raw_fees.tax_items:
                        color = "#d32f2f" if fee.amount < 0 else "#388e3c"
                        st.markdown(f"""
                        <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                            <strong style="color:#333333;">{fee.name}</strong><br>
                            <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee.amount:.2f}</span>
                            <small style="color:#666666; margin-left:10px;">({fee.category})</small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ No Tax items found")
            
            if obj.raw_fees.delivery_items:
                with st.expander(f"🚚 Delivery Items ({len(obj.raw_fees.delivery_items)} fees totaling ${sum(fee.amount for fee in obj.raw_fees.delivery_items):.2f})"):
                    for fee in obj.raw_fees.delivery_items:
                        color = "#d32f2f" if fee.amount < 0 else "#388e3c"
                        st.markdown(f"""
                        <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                            <strong style="color:#333333;">{fee.name}</strong><br>
                            <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee.amount:.2f}</span>
                            <small style="color:#666666; margin-left:10px;">({fee.category})</small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ No Delivery items found")
            
            if obj.raw_fees.tip_items:
                with st.expander(f"💰 Tip Items ({len(obj.raw_fees.tip_items)} fees totaling ${sum(fee.amount for fee in obj.raw_fees.tip_items):.2f})"):
                    for fee in obj.raw_fees.tip_items:
                        color = "#d32f2f" if fee.amount < 0 else "#388e3c"
                        st.markdown(f"""
                        <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                            <strong style="color:#333333;">{fee.name}</strong><br>
                            <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee.amount:.2f}</span>
                            <small style="color:#666666; margin-left:10px;">({fee.category})</small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("ℹ️ No Tip items found")
            
            # Summary validation
            total_from_raw = (sum(fee.amount for fee in obj.raw_fees.tax_items) + 
                            sum(fee.amount for fee in obj.raw_fees.delivery_items) + 
                            sum(fee.amount for fee in obj.raw_fees.tip_items))
            total_from_calculated = sum(obj.fees.values())
            
            if abs(total_from_raw - total_from_calculated) > 0.01:  # Allow for small rounding differences
                st.warning(f"⚠️ Calculation mismatch: Raw total (${total_from_raw:.2f}) ≠ Calculated total (${total_from_calculated:.2f})")
            else:
                st.success(f"✅ Fee categorization verified: Total ${total_from_calculated:.2f}")
    
    with tab2:
        # Visual breakdown using charts
        if st.session_state.structured_object:
            import pandas as pd
            
            obj = st.session_state.structured_object
            
            # Items chart
            if obj.items:
                st.subheader("📊 Item Costs")
                items_df = pd.DataFrame(obj.items)
                st.bar_chart(items_df.set_index('name')['price'])
            
            # FIX #4: Fees breakdown - include all fees, even negative ones
            st.subheader("💳 Fee Distribution")
            fees_data = obj.fees
            if fees_data:
                # Display as metrics for better visibility of negative values
                col1, col2, col3 = st.columns(3)
                with col1:
                    tax_val = fees_data.get('Tax', 0)
                    st.metric("Tax", f"${tax_val:.2f}", delta=f"${tax_val:.2f}" if tax_val != 0 else None)
                
                with col2:
                    delivery_val = fees_data.get('Delivery Fee', 0)
                    st.metric("Delivery", f"${delivery_val:.2f}", delta=f"${delivery_val:.2f}" if delivery_val != 0 else None)
                
                with col3:
                    tip_val = fees_data.get('Tip', 0)
                    st.metric("Tip", f"${tip_val:.2f}", delta=f"${tip_val:.2f}" if tip_val != 0 else None)
                
                # Show chart with ALL fees (including negative ones)
                fees_chart_data = {
                    'Tax': fees_data.get('Tax', 0),
                    'Delivery Fee': fees_data.get('Delivery Fee', 0),
                    'Tip': fees_data.get('Tip', 0)
                }
                
                # Only show chart if there are non-zero values
                non_zero_fees = {k: v for k, v in fees_chart_data.items() if v != 0}
                if non_zero_fees:
                    import pandas as pd
                    fees_chart_df = pd.DataFrame(list(non_zero_fees.items()), columns=['Fee Type', 'Amount'])
                    st.bar_chart(fees_chart_df.set_index('Fee Type')['Amount'])
                else:
                    st.info("No fees to display in chart")
            
            # Show sharing breakdown
            st.subheader("👥 Item Sharing Breakdown")
            for item_name, sharers in obj.item_shares.items():
                sharer_names = [obj.persons.get(abbr, abbr) for abbr in sharers]
                st.write(f"**{item_name}**: {', '.join(sharer_names)}")
    
    with tab3:
        st.code(st.session_state.structured_output, language='text')
    
    # Action buttons with better spacing
    st.markdown("---")
    st.markdown("### What would you like to do?")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown('<div class="success-button">', unsafe_allow_html=True)
        if st.button("✅ Looks Perfect!"):
            st.session_state.step = 3
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="warning-button">', unsafe_allow_html=True)
        if st.button("📝 Needs Changes"):
            st.session_state.step = 4
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        if st.button("🔄 Start Over"):
            # Reset all session state
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# --- Step 3: Run Split Logic ---
elif st.session_state.step == 3:
    st.subheader("💰 Step 3: Your Bill Split")
    
    # Parse and calculate
    parsed_data = parse_bill_input(st.session_state.structured_output)
    
    if parsed_data:
        splits = split_instacart_bill(
            parsed_data['persons'],
            parsed_data['items'], 
            parsed_data['fees'],
            parsed_data['item_shares']
        )
        st.session_state.final_output = splits
        
        # Display results with better formatting
        st.markdown("### 💸 Who Pays What")
        
        # Create visual payment cards
        total_bill = sum(splits.values())
        
        for person, amount in splits.items():
            percentage = (amount / total_bill) * 100 if total_bill > 0 else 0
            
            st.markdown(f"""
            <div style="padding:15px; border:2px solid #28a745; border-radius:10px; margin:10px 0; background-color:#f8fff8;">
                <h3 style="margin:0; color:#28a745;">{person}</h3>
                <h2 style="margin:5px 0; color:#28a745;">${amount:.2f}</h2>
                <p style="margin:0; color:#666;">({percentage:.1f}% of total bill)</p>
            </div>
            """, unsafe_allow_html=True)
        
        # NEW: Detailed breakdown section
        st.markdown("---")
        st.markdown("### 📋 Detailed Split Breakdown")
        
        with st.expander("🔍 View Detailed Calculation", expanded=False):
            # Show items and who shared them
            st.markdown("#### 🛒 Items & Sharing:")
            for item in parsed_data['items']:
                item_name = item['name']
                item_price = item['price']
                sharers = parsed_data['item_shares'].get(item_name, [])
                sharer_names = [parsed_data['persons'].get(abbr, abbr) for abbr in sharers]
                st.markdown(f"• **{item_name}**: ${item_price:.2f} (shared by: {', '.join(sharer_names)})")
            
            st.markdown("#### 💳 Fee Distribution:")
            st.markdown(f"• **Tax**: ${parsed_data['fees'].get('Tax', 0):.2f} (distributed proportionally)")
            st.markdown(f"• **Delivery Fee**: ${parsed_data['fees'].get('Delivery Fee', 0):.2f} (split equally)")
            st.markdown(f"• **Tip**: ${parsed_data['fees'].get('Tip', 0):.2f} (split equally)")
            
            st.markdown("#### 🧮 Individual Contributions:")
            for person, amount in splits.items():
                st.markdown(f"• **{person}**: ${amount:.2f}")
        
        # Summary
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Bill", f"${total_bill:.2f}")
        with col2:
            st.metric("Number of People", len(splits))
        
        # Enhanced export options
        st.markdown("### 📤 Export Options")
        col1, col2 = st.columns(2)
        
        with col1:
            # Simple copy button
            summary_text = "\n".join([f"{person}: ${amount:.2f}" for person, amount in splits.items()])
            if st.button("📋 Copy Simple Summary"):
                st.code(summary_text)
        
        with col2:
            # Detailed copy button
            if st.button("📋 Copy Summary with Details"):
                detailed_summary = f"""Bill Split Summary
==================

WHO PAYS WHAT:
{chr(10).join([f"{person}: ${amount:.2f} ({(amount/total_bill)*100:.1f}%)" for person, amount in splits.items()])}

TOTAL: ${total_bill:.2f}

DETAILED BREAKDOWN:
==================

ITEMS & SHARING:
{chr(10).join([f"• {item['name']}: ${item['price']:.2f} (shared by: {', '.join([parsed_data['persons'].get(abbr, abbr) for abbr in parsed_data['item_shares'].get(item['name'], [])])})" for item in parsed_data['items']])}

FEES:
• Tax: ${parsed_data['fees'].get('Tax', 0):.2f} (distributed proportionally)
• Delivery Fee: ${parsed_data['fees'].get('Delivery Fee', 0):.2f} (split equally)
• Tip: ${parsed_data['fees'].get('Tip', 0):.2f} (split equally)

Generated by Smart Bill Splitter AI"""
                
                st.code(detailed_summary)
        
        # Start over button
        st.markdown("---")
        if st.button("🔄 Calculate Another Bill"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    else:
        st.error("❌ Failed to parse structured output. Please go back and regenerate.")
        if st.button("← Go Back"):
            st.session_state.step = 2
            st.rerun()

# --- Step 4: Take Feedback + Regenerate ---
elif st.session_state.step == 4:
    st.subheader("📝 Step 4: Provide Feedback")
    
    st.markdown("Please describe what was wrong with the AI results:")
    feedback = st.text_area(
        "Feedback",
        placeholder="Example: The AI missed the dessert item, or incorrectly assigned the pizza to only one person.",
        height=100
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Regenerate with Feedback") and feedback.strip():
            with st.spinner("🤖 Regenerating structured data with your feedback..."):
                try:
                    structured_object, structured_output = call_llm_api_sync(
                        image_bytes_list=st.session_state.image_bytes_list,  # Use multiple images
                        user_description=st.session_state.user_description,
                        feedback=feedback,
                        previous_output=st.session_state.structured_output
                    )
                    if structured_object and structured_output:
                        st.session_state.structured_object = structured_object
                        st.session_state.structured_output = structured_output
                        st.session_state.step = 2
                        st.success("✅ Results regenerated successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to regenerate. Please try again.")
                except Exception as e:
                    st.error(f"❌ Error regenerating: {str(e)}")
    
    with col2:
        if st.button("← Go Back"):
            st.session_state.step = 2
            st.rerun()
