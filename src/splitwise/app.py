# app.py
import streamlit as st
from PIL import Image
from loguru import logger
import io
from src.splitwise.llm_handler import call_llm_api_sync  # Import the sync version
from src.splitwise.bill_parser import parse_bill_input, split_instacart_bill

# logger configuration
logger.add("splitwise.log", rotation="1 MB", level="DEBUG")


st.set_page_config(page_title="Bill Splitter", layout="centered")
st.title("🧾 Smart Bill Splitter with AI")

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

# --- Step 1: Upload + Description ---
if st.session_state.step == 1:
    uploaded_file = st.file_uploader("Upload bill image", type=["jpg", "png", "jpeg"])
    user_description = st.text_area("Describe who shared what")

    if st.button("Generate Structured Output") and uploaded_file and user_description:
        logger.info("Processing uploaded bill image")
        logger.debug(f"User description: {user_description}")

        image = Image.open(uploaded_file)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes = image_bytes.getvalue()
        
        # Store in session state for feedback functionality
        st.session_state.image_bytes = image_bytes
        st.session_state.user_description = user_description

        with st.spinner("Calling LLM to extract structured data..."):
            structured_object, structured_output = call_llm_api_sync(image_bytes, user_description)
            st.session_state.structured_object = structured_object
            st.session_state.structured_output = structured_output
            st.session_state.step = 2
            st.rerun()

# --- Step 2: Review Structured Output ---
elif st.session_state.step == 2:
    st.subheader("🧠 AI-Generated Structured Text")
    st.code(st.session_state.structured_output, language='text')
    
    # Display detailed breakdown using the structured object
    if st.session_state.structured_object:
        with st.expander("📊 Detailed Breakdown"):
            obj = st.session_state.structured_object
            
            st.write("**People:**")
            for abbr, name in obj.persons.items():
                st.write(f"- {abbr}: {name}")
            
            st.write("**Items:**")
            for item in obj.items:
                st.write(f"- {item['name']}: ${item['price']:.2f}")
            
            st.write("**Fee Breakdown:**")
            st.write(f"- Tax: ${obj.fees.get('Tax', 0):.2f}")
            st.write(f"- Delivery Fee: ${obj.fees.get('Delivery Fee', 0):.2f}")
            st.write(f"- Tip: ${obj.fees.get('Tip', 0):.2f}")
            
            if obj.raw_fees.tax_items:
                st.write("**Tax Items:**")
                for fee in obj.raw_fees.tax_items:
                    st.write(f"  - {fee.name}: ${fee.amount:.2f}")
            
            if obj.raw_fees.delivery_items:
                st.write("**Delivery Items:**")
                for fee in obj.raw_fees.delivery_items:
                    st.write(f"  - {fee.name}: ${fee.amount:.2f}")
            
            if obj.raw_fees.tip_items:
                st.write("**Tip Items:**")
                for fee in obj.raw_fees.tip_items:
                    st.write(f"  - {fee.name}: ${fee.amount:.2f}")

    st.markdown("Is this correct?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Looks Good"):
            st.session_state.step = 3
            st.rerun()
    with col2:
        if st.button("📝 Regenerate with Feedback"):
            st.session_state.step = 4

# --- Step 3: Run Split Logic ---
elif st.session_state.step == 3:
    st.subheader("💰 Split Calculation")
    
    # Parse the structured output
    parsed_data = parse_bill_input(st.session_state.structured_output)
    
    if parsed_data:
        splits = split_instacart_bill(
            parsed_data['persons'],
            parsed_data['items'], 
            parsed_data['fees'],
            parsed_data['item_shares']
        )
        st.session_state.final_output = splits
        
        # Display results
        for person, amount in splits.items():
            st.write(f"**{person}**: ${amount:.2f}")
    else:
        st.error("Failed to parse structured output")

# --- Step 4: Take Feedback + Regenerate ---
elif st.session_state.step == 4:
    feedback = st.text_area("Describe what was wrong with the structured output")
    if st.button("Regenerate with Feedback"):
        with st.spinner("Regenerating structured data..."):
            structured_object, structured_output = call_llm_api_sync(
                image_bytes=st.session_state.image_bytes,
                user_description=st.session_state.user_description,
                feedback=feedback,
                previous_output=st.session_state.structured_output
            )
            st.session_state.structured_object = structured_object
            st.session_state.structured_output = structured_output
            st.session_state.step = 2
            st.rerun()
