import streamlit as st
from PIL import Image
from io import BytesIO
from typing import List


def render_upload_section() -> tuple[List[BytesIO], str]:
    """
    Render the upload section and return uploaded files and description
    
    Returns:
        Tuple of (image_files_as_bytes, user_description)
    """
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
        accept_multiple_files=True,
        help="Upload clear photos of your receipt(s). You can select multiple images. JPG, PNG, and JPEG formats are supported."
    )
    
    # Show image previews
    image_bytes_list = []
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
                    
                    # Convert to bytes for API
                    img_bytes = BytesIO()
                    image.save(img_bytes, format='PNG')
                    image_bytes_list.append(img_bytes)
        
        # Store image files in session state for feedback functionality
        st.session_state.image_files = image_bytes_list
    
    # Description input
    user_description = st.text_area(
        "Describe who shared what",
        placeholder="Example: Vikram and Alice shared the pizza. Vikram had the burger alone. Alice had the salad alone.",
        help="Be specific about which items each person consumed. Use full names for clarity.",
        height=100,
        key="user_description_input"
    )
    
    # Store user description in session state for feedback functionality
    if user_description.strip():
        st.session_state.user_description = user_description
    
    return image_bytes_list, user_description