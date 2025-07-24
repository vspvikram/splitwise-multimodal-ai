import streamlit as st
import time
import pandas as pd
from loguru import logger

from services.api_client import get_api_client
from components.upload import render_upload_section
import dotenv

dotenv.load_dotenv()

# Configure logging
logger.add("frontend.log", rotation="1 MB", level="DEBUG")

# Page config
st.set_page_config(
    page_title="Bill Splitter", 
    layout="centered",
    page_icon="🧾",
    initial_sidebar_state="collapsed"
)

# Custom CSS
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

# Initialize API client
api_client = get_api_client()

# Check backend health
if not api_client.health_check():
    st.error("🚨 Backend API is not available. Please make sure the backend server is running.")
    st.stop()

# Session state initialization
if "step" not in st.session_state:
    st.session_state.step = 1
if "structured_object" not in st.session_state:
    st.session_state.structured_object = None
if "formatted_output" not in st.session_state:
    st.session_state.formatted_output = None
if "splits" not in st.session_state:
    st.session_state.splits = None
if "parsed_data" not in st.session_state:
    st.session_state.parsed_data = None
if "feedback_needed" not in st.session_state:
    st.session_state.feedback_needed = False

# Dynamic step indicator based on whether feedback is needed
def get_progress_info():
    """Calculate progress based on whether feedback flow is active"""
    if st.session_state.feedback_needed:
        # 4-step flow: Upload → Review → Feedback → Calculate
        steps = ["📤 Upload & Describe", "🔍 Review Results", "📝 Feedback", "💰 Calculate Split"]
        total_steps = 4
        
        # Map step numbers to positions in feedback flow
        if st.session_state.step == 1:
            current_position = 1
        elif st.session_state.step == 2:
            current_position = 2
        elif st.session_state.step == 4:  # Feedback step
            current_position = 3
        elif st.session_state.step == 3:  # Calculate step (after feedback)
            current_position = 4
        else:
            current_position = 1
            
    else:
        # 3-step flow: Upload → Review → Calculate (no feedback)
        steps = ["📤 Upload & Describe", "🔍 Review Results", "💰 Calculate Split"]
        total_steps = 3
        
        # Map step numbers to positions in normal flow
        if st.session_state.step == 1:
            current_position = 1
        elif st.session_state.step == 2:
            current_position = 2
        elif st.session_state.step == 3:
            current_position = 3
        else:
            current_position = 1
    
    return steps, current_position, total_steps

# Get dynamic progress info
steps, current_position, total_steps = get_progress_info()

# Display step indicator
st.markdown('<div class="step-indicator">', unsafe_allow_html=True)
progress_text = " → ".join([f"**{step}**" if i+1 == current_position else step for i, step in enumerate(steps)])
st.markdown(progress_text, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Calculate and display progress bar
progress = current_position / total_steps
st.progress(progress)

# Step 1: Upload and Process
if st.session_state.step == 1:
    # Reset feedback_needed when starting fresh
    st.session_state.feedback_needed = False
    
    image_bytes_list, user_description = render_upload_section()
    
    can_process = len(image_bytes_list) > 0 and user_description.strip() != ""
    
    if not can_process:
        st.warning("⚠️ Please upload at least one image and provide a description.")
    
    if can_process:
        st.markdown('<div class="success-button">', unsafe_allow_html=True)
        if st.button("🚀 Generate Structured Output"):
            with st.spinner(f"🤖 Processing {len(image_bytes_list)} image(s)..."):
                success, response = api_client.process_bill(
                    image_files=image_bytes_list,
                    user_description=user_description
                )
                
                if success and response.get('success'):
                    st.session_state.structured_object = response.get('structured_object')
                    st.session_state.formatted_output = response.get('formatted_output')
                    st.session_state.step = 2
                    st.success("✅ Receipt processed successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    error_msg = response.get('error', 'Unknown error')
                    st.error(f"❌ Failed to process receipt: {error_msg}")
                    # Show more detailed error information
                    if response.get('error'):
                        st.code(str(response))
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.button("🚀 Generate Structured Output", disabled=True)

# Step 2: Review Results with Tabs
elif st.session_state.step == 2:
    st.subheader("🔍 Step 2: Review AI Results")
    
    # Tabs for better organization
    tab1, tab2, tab3 = st.tabs(["📋 Structured Data", "📊 Visual Breakdown", "🔧 Raw Output"])
    
    with tab1:
        if st.session_state.structured_object:
            obj = st.session_state.structured_object
            
            # Debug: Show raw object structure
            with st.expander("🔍 Debug: Raw API Response"):
                st.json(obj)
            
            # Validate that obj has the expected structure
            if not isinstance(obj, dict):
                st.error("❌ Invalid response format: Expected dictionary")
                st.json(obj)
            elif 'persons' not in obj or 'items' not in obj or 'fees' not in obj:
                st.error("❌ Missing required fields in response")
                st.json(obj)
            else:
                # People section - with proper validation
                st.markdown("### 👥 People")
                if obj.get('persons') and len(obj['persons']) > 0:
                    num_people = len(obj['persons'])
                    cols = st.columns(max(1, num_people))
                    for i, (abbr, name) in enumerate(obj['persons'].items()):
                        with cols[i % len(cols)]:
                            st.markdown(f"""
                            <div style="padding:10px; border:1px solid #ddd; border-radius:5px; text-align:center; margin:5px;">
                                <h4>{abbr}</h4>
                                <p>{name}</p>
                            </div>
                            """, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ No people found in the results")
                
                # Items with sharing information
                st.markdown("### 🛒 Items & Sharing")
                if obj.get('items') and len(obj['items']) > 0:
                    for item in obj['items']:
                        if isinstance(item, dict) and 'name' in item and 'price' in item:
                            item_name = item['name']
                            item_price = item['price']
                            sharers = obj.get('item_shares', {}).get(item_name, [])
                            sharer_names = [obj['persons'].get(abbr, abbr) for abbr in sharers]
                            
                            st.markdown(f"""
                            <div style="padding:10px; border:1px solid #ddd; border-radius:8px; margin:5px 0; background-color:#ffffff; color:#000000;">
                                <strong style="color:#333333;">{item_name}</strong> - <span style="color:#28a745; font-weight:bold;">${item_price:.2f}</span><br>
                                <small style="color:#666666;">👥 Shared by: {', '.join(sharer_names) if sharer_names else 'No one assigned'}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.warning(f"⚠️ Invalid item format: {item}")
                else:
                    st.warning("⚠️ No items found in the results")
                
                # Fee breakdown with explanatory text AND detailed breakdown
                st.markdown("### 💳 Fee Categories (AI Processed)")
                st.markdown("*These are automatically calculated totals from individual receipt fees*")
                
                if obj.get('fees'):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        tax_amount = obj['fees'].get('Tax', 0)
                        st.metric("Tax (Proportional)", f"${tax_amount:.2f}", 
                                 help="Sales tax, discounts, credits - distributed proportionally based on items consumed")
                        
                    with col2:
                        delivery_amount = obj['fees'].get('Delivery Fee', 0)
                        st.metric("Delivery (Equal Split)", f"${delivery_amount:.2f}",
                                 help="Delivery charges and related fees - split equally among all people")
                        
                    with col3:
                        tip_amount = obj['fees'].get('Tip', 0)
                        st.metric("Tip (Equal Split)", f"${tip_amount:.2f}",
                                 help="Tips and gratuity - split equally among all people")
                else:
                    st.warning("⚠️ No fees found in the results")
                
                # Detailed fee breakdown showing what went into each category
                if obj.get('raw_fees'):
                    st.markdown("---")
                    st.markdown("### 🔍 Fee Category Breakdown")
                    st.markdown("*See which original receipt fees were categorized into each type*")
                    
                    raw_fees = obj['raw_fees']
                    
                    # Tax items
                    if raw_fees.get('tax_items'):
                        tax_total = sum(fee['amount'] for fee in raw_fees['tax_items'])
                        with st.expander(f"📊 Tax Items ({len(raw_fees['tax_items'])} fees totaling ${tax_total:.2f})"):
                            for fee in raw_fees['tax_items']:
                                color = "#d32f2f" if fee['amount'] < 0 else "#388e3c"
                                st.markdown(f"""
                                <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                                    <strong style="color:#333333;">{fee['name']}</strong><br>
                                    <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee['amount']:.2f}</span>
                                    <small style="color:#666666; margin-left:10px;">({fee['category']})</small>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("ℹ️ No Tax items found")
                    
                    # Delivery items
                    if raw_fees.get('delivery_items'):
                        delivery_total = sum(fee['amount'] for fee in raw_fees['delivery_items'])
                        with st.expander(f"🚚 Delivery Items ({len(raw_fees['delivery_items'])} fees totaling ${delivery_total:.2f})"):
                            for fee in raw_fees['delivery_items']:
                                color = "#d32f2f" if fee['amount'] < 0 else "#388e3c"
                                st.markdown(f"""
                                <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                                    <strong style="color:#333333;">{fee['name']}</strong><br>
                                    <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee['amount']:.2f}</span>
                                    <small style="color:#666666; margin-left:10px;">({fee['category']})</small>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("ℹ️ No Delivery items found")
                    
                    # Tip items
                    if raw_fees.get('tip_items'):
                        tip_total = sum(fee['amount'] for fee in raw_fees['tip_items'])
                        with st.expander(f"💰 Tip Items ({len(raw_fees['tip_items'])} fees totaling ${tip_total:.2f})"):
                            for fee in raw_fees['tip_items']:
                                color = "#d32f2f" if fee['amount'] < 0 else "#388e3c"
                                st.markdown(f"""
                                <div style="padding:8px; border-left:4px solid {color}; margin:5px 0; background-color:#ffffff;">
                                    <strong style="color:#333333;">{fee['name']}</strong><br>
                                    <span style="color:{color}; font-size:1.1em; font-weight:bold;">${fee['amount']:.2f}</span>
                                    <small style="color:#666666; margin-left:10px;">({fee['category']})</small>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("ℹ️ No Tip items found")
                    
                    # Summary validation
                    if obj.get('fees'):
                        total_from_raw = (sum(fee['amount'] for fee in raw_fees.get('tax_items', [])) + 
                                        sum(fee['amount'] for fee in raw_fees.get('delivery_items', [])) + 
                                        sum(fee['amount'] for fee in raw_fees.get('tip_items', [])))
                        total_from_calculated = sum(obj['fees'].values())
                        
                        if abs(total_from_raw - total_from_calculated) > 0.01:
                            st.warning(f"⚠️ Calculation mismatch: Raw total (${total_from_raw:.2f}) ≠ Calculated total (${total_from_calculated:.2f})")
                        else:
                            st.success(f"✅ Fee categorization verified: Total ${total_from_calculated:.2f}")
        else:
            st.error("❌ No structured data available. Please go back and process the bill again.")
    
    with tab2:
        # Visual breakdown using charts
        if st.session_state.structured_object:
            obj = st.session_state.structured_object
            
            # Items chart
            if obj.get('items') and len(obj['items']) > 0:
                st.subheader("📊 Item Costs")
                try:
                    items_df = pd.DataFrame(obj['items'])
                    st.bar_chart(items_df.set_index('name')['price'])
                except Exception as e:
                    st.error(f"Error creating items chart: {e}")
                    st.json(obj['items'])
            
            # Fees breakdown
            st.subheader("💳 Fee Distribution")
            if obj.get('fees'):
                fees_data = obj['fees']
                non_zero_fees = {k: v for k, v in fees_data.items() if v != 0}
                if non_zero_fees:
                    try:
                        fees_chart_df = pd.DataFrame(list(non_zero_fees.items()), columns=['Fee Type', 'Amount'])
                        st.bar_chart(fees_chart_df.set_index('Fee Type')['Amount'])
                    except Exception as e:
                        st.error(f"Error creating fees chart: {e}")
                        st.json(fees_data)
                else:
                    st.info("No fees to display in chart")
    
    with tab3:
        # Raw structured output
        st.subheader("🔧 Raw Structured Output")
        if st.session_state.formatted_output:
            st.code(st.session_state.formatted_output, language='text')
        else:
            st.warning("No raw output available")
    
    # Action buttons with better spacing
    st.markdown("---")
    st.markdown("### What would you like to do?")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.markdown('<div class="success-button">', unsafe_allow_html=True)
        if st.button("✅ Looks Perfect!"):
            # User is satisfied - go directly to calculation (3-step flow)
            st.session_state.feedback_needed = False
            st.session_state.step = 3
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="warning-button">', unsafe_allow_html=True)
        if st.button("📝 Needs Changes"):
            # User wants to give feedback (4-step flow)
            st.session_state.feedback_needed = True
            st.session_state.step = 4
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        if st.button("🔄 Start Over"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# Step 3: Calculate Split with Enhanced Features
elif st.session_state.step == 3:
    st.subheader("💰 Step 3: Your Bill Split")
    
    if st.session_state.formatted_output:
        with st.spinner("Calculating split..."):
            success, response = api_client.calculate_split(st.session_state.formatted_output)
            
            if success and response.get('success'):
                splits = response.get('splits', {})
                total_bill = response.get('total_bill', 0)
                parsed_data = response.get('parsed_data', {})
                
                st.session_state.splits = splits
                st.session_state.parsed_data = parsed_data
                
                # Display results with better formatting
                st.markdown("### 💸 Who Pays What")
                
                # Create visual payment cards
                for person, amount in splits.items():
                    percentage = (amount / total_bill) * 100 if total_bill > 0 else 0
                    st.markdown(f"""
                    <div style="padding:15px; border:2px solid #28a745; border-radius:10px; margin:10px 0; background-color:#f8fff8;">
                        <h3 style="margin:0; color:#28a745;">{person}</h3>
                        <h2 style="margin:5px 0; color:#28a745;">${amount:.2f}</h2>
                        <p style="margin:0; color:#666;">({percentage:.1f}% of total bill)</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Show completion message based on flow
                if st.session_state.feedback_needed:
                    st.success("🎉 **Process Complete!** Your feedback has been incorporated and the split is calculated.")
                else:
                    st.success("🎉 **Process Complete!** Your bill has been successfully split.")
                
                # Detailed breakdown section
                st.markdown("---")
                st.markdown("### 📋 Detailed Split Breakdown")
                
                with st.expander("🔍 View Detailed Calculation", expanded=False):
                    if parsed_data:
                        # Show items and who shared them
                        st.markdown("#### 🛒 Items & Sharing:")
                        for item in parsed_data.get('items', []):
                            item_name = item['name']
                            item_price = item['price']
                            sharers = parsed_data.get('item_shares', {}).get(item_name, [])
                            sharer_names = [parsed_data.get('persons', {}).get(abbr, abbr) for abbr in sharers]
                            st.markdown(f"• **{item_name}**: ${item_price:.2f} (shared by: {', '.join(sharer_names)})")
                        
                        st.markdown("#### 💳 Fee Distribution:")
                        fees = parsed_data.get('fees', {})
                        st.markdown(f"• **Tax**: ${fees.get('Tax', 0):.2f} (distributed proportionally)")
                        st.markdown(f"• **Delivery Fee**: ${fees.get('Delivery Fee', 0):.2f} (split equally)")
                        st.markdown(f"• **Tip**: ${fees.get('Tip', 0):.2f} (split equally)")
                        
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
{chr(10).join([f"• {item['name']}: ${item['price']:.2f} (shared by: {', '.join([parsed_data.get('persons', {}).get(abbr, abbr) for abbr in parsed_data.get('item_shares', {}).get(item['name'], [])])})" for item in parsed_data.get('items', [])])}

FEES:
• Tax: ${parsed_data.get('fees', {}).get('Tax', 0):.2f} (distributed proportionally)
• Delivery Fee: ${parsed_data.get('fees', {}).get('Delivery Fee', 0):.2f} (split equally)
• Tip: ${parsed_data.get('fees', {}).get('Tip', 0):.2f} (split equally)

Generated by Smart Bill Splitter AI"""
                        
                        st.code(detailed_summary)
            
            else:
                error_msg = response.get('error', 'Unknown error')
                st.error(f"❌ Failed to calculate split: {error_msg}")
                st.code(str(response))
    else:
        st.error("❌ No formatted output available. Please go back and process the bill again.")
    
    # Start over button
    st.markdown("---")
    if st.button("🔄 Calculate Another Bill"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Step 4: Feedback with Regeneration
elif st.session_state.step == 4:
    st.subheader("📝 Step 3: Provide Feedback")  # Now correctly shows as Step 3 in 4-step flow
    
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
                    success, response = api_client.process_bill(
                        image_files=st.session_state.get('image_files', []),
                        user_description=st.session_state.get('user_description', ''),
                        feedback=feedback,
                        previous_output=st.session_state.formatted_output
                    )
                    
                    if success and response.get('success'):
                        st.session_state.structured_object = response.get('structured_object')
                        st.session_state.formatted_output = response.get('formatted_output')
                        st.session_state.step = 3  # Go to calculation after feedback
                        st.success("✅ Results regenerated successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        error_msg = response.get('error', 'Unknown error')
                        st.error(f"❌ Failed to regenerate: {error_msg}")
                except Exception as e:
                    st.error(f"❌ Error regenerating: {str(e)}")
    
    with col2:
        if st.button("← Go Back"):
            st.session_state.step = 2
            st.rerun()