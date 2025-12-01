import streamlit as st
import pandas as pd
import anthropic
from docx import Document
import io
import json

# Page config
st.set_page_config(page_title="Application Compliance Checker", page_icon="📋", layout="wide")

# Initialize session state
if 'standards' not in st.session_state:
    st.session_state.standards = None
if 'app_content' not in st.session_state:
    st.session_state.app_content = None
if 'findings' not in st.session_state:
    st.session_state.findings = None

def read_docx(file):
    """Extract text from DOCX file"""
    doc = Document(file)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

def read_standards_file(file):
    """Read standards from CSV or Excel file"""
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    elif file.name.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file)
    else:
        st.error("Unsupported file format. Please upload CSV or Excel file.")
        return None
    
    # Standardize column names
    df.columns = df.columns.str.strip()
    
    # Check for required columns (flexible naming)
    required_cols = ['id', 'category', 'requirement']
    col_mapping = {}
    
    for col in df.columns:
        col_lower = col.lower()
        if 'id' in col_lower or 'standard' in col_lower:
            col_mapping[col] = 'ID'
        elif 'category' in col_lower or 'type' in col_lower:
            col_mapping[col] = 'Category'
        elif 'requirement' in col_lower or 'standard' in col_lower:
            col_mapping[col] = 'Requirement'
        elif 'description' in col_lower or 'detail' in col_lower:
            col_mapping[col] = 'Description'
    
    df = df.rename(columns=col_mapping)
    
    # Ensure Description column exists
    if 'Description' not in df.columns:
        df['Description'] = ''
    
    return df[['ID', 'Category', 'Requirement', 'Description']]

def analyze_compliance(app_content, standards_df, api_key):
    """Use Claude API to analyze compliance"""
    
    # Prepare standards text
    standards_text = ""
    for _, row in standards_df.iterrows():
        standards_text += f"\n{row['ID']} - {row['Category']}: {row['Requirement']}\n"
        if row['Description']:
            standards_text += f"Description: {row['Description']}\n"
    
    prompt = f"""You are a compliance analyst. Review the following application documentation against the provided standards and identify any deficiencies.

APPLICATION DOCUMENTATION:
{app_content}

STANDARDS TO CHECK:
{standards_text}

For each standard, determine if the application documentation provides sufficient evidence of compliance. 

Respond ONLY with a JSON array of findings in this exact format, with no markdown backticks or preamble:
[
  {{
    "standardId": "ID of the standard",
    "category": "Category name",
    "requirement": "The requirement text",
    "status": "Deficient" or "Compliant" or "Partial",
    "finding": "Detailed description of the deficiency or compliance status",
    "recommendation": "Specific recommendation to address the deficiency"
  }}
]"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        response_text = message.content[0].text
        
        # Clean up response
        response_text = response_text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.startswith('```'):
            response_text = response_text[3:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        findings = json.loads(response_text)
        return findings
        
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        return None

# Main UI
st.title("📋 Application Compliance Checker")
st.markdown("Upload your application documentation and standards to identify compliance gaps")

# Sidebar for API key
with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("Anthropic API Key", type="password", help="Enter your Anthropic API key")
    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("""
    1. Upload application DOCX
    2. Upload standards file (CSV/Excel)
    3. Review loaded data
    4. Click 'Analyze Compliance'
    5. Export findings
    """)

# Create tabs
tab1, tab2, tab3 = st.tabs(["📁 Upload Files", "📊 Review", "🔍 Analysis Results"])

with tab1:
    st.header("Upload Files")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Application Documentation")
        app_file = st.file_uploader("Upload Application DOCX", type=['docx'], key="app_upload")
        
        if app_file:
            with st.spinner("Reading document..."):
                st.session_state.app_content = read_docx(app_file)
                st.success(f"✓ Loaded: {app_file.name}")
                st.info(f"Content length: {len(st.session_state.app_content)} characters")
    
    with col2:
        st.subheader("Standards File")
        standards_file = st.file_uploader("Upload Standards (CSV or Excel)", type=['csv', 'xlsx', 'xls'], key="standards_upload")
        
        if standards_file:
            with st.spinner("Reading standards..."):
                st.session_state.standards = read_standards_file(standards_file)
                if st.session_state.standards is not None:
                    st.success(f"✓ Loaded: {standards_file.name}")
                    st.info(f"Standards loaded: {len(st.session_state.standards)}")

with tab2:
    st.header("Review Loaded Data")
    
    if st.session_state.app_content:
        st.subheader("Application Content Preview")
        with st.expander("View content (first 1000 characters)"):
            st.text(st.session_state.app_content[:1000] + "...")
    else:
        st.warning("No application document loaded")
    
    if st.session_state.standards is not None:
        st.subheader(f"Standards to Check ({len(st.session_state.standards)} total)")
        st.dataframe(st.session_state.standards, use_container_width=True)
    else:
        st.warning("No standards file loaded")
    
    st.markdown("---")
    
    if st.session_state.app_content and st.session_state.standards is not None:
        if not api_key:
            st.error("⚠️ Please enter your Anthropic API key in the sidebar")
        else:
            if st.button("🔍 Analyze Compliance", type="primary", use_container_width=True):
                with st.spinner("Analyzing compliance... This may take a minute."):
                    findings = analyze_compliance(
                        st.session_state.app_content,
                        st.session_state.standards,
                        api_key
                    )
                    if findings:
                        st.session_state.findings = findings
                        st.success("Analysis complete! View results in the 'Analysis Results' tab.")
                        st.balloons()

with tab3:
    st.header("Analysis Results")
    
    if st.session_state.findings:
        findings_df = pd.DataFrame(st.session_state.findings)
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        deficient = len(findings_df[findings_df['status'] == 'Deficient'])
        partial = len(findings_df[findings_df['status'] == 'Partial'])
        compliant = len(findings_df[findings_df['status'] == 'Compliant'])
        
        col1.metric("🔴 Deficient", deficient)
        col2.metric("🟡 Partial", partial)
        col3.metric("🟢 Compliant", compliant)
        
        st.markdown("---")
        
        # Filter options
        status_filter = st.multiselect(
            "Filter by Status",
            options=['Deficient', 'Partial', 'Compliant'],
            default=['Deficient', 'Partial']
        )
        
        filtered_findings = findings_df[findings_df['status'].isin(status_filter)]
        
        # Display findings
        for idx, finding in filtered_findings.iterrows():
            status_color = {
                'Deficient': '🔴',
                'Partial': '🟡',
                'Compliant': '🟢'
            }
            
            with st.expander(f"{status_color[finding['status']]} {finding['standardId']} - {finding['category']}"):
                st.markdown(f"**Requirement:** {finding['requirement']}")
                st.markdown(f"**Status:** {finding['status']}")
                st.markdown(f"**Finding:** {finding['finding']}")
                st.markdown(f"**Recommendation:** {finding['recommendation']}")
        
        st.markdown("---")
        
        # Export options
        col1, col2 = st.columns(2)
        
        with col1:
            # Export to CSV
            csv = findings_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Findings (CSV)",
                data=csv,
                file_name="compliance_findings.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Export to Excel
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                findings_df.to_excel(writer, index=False, sheet_name='Findings')
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Download Findings (Excel)",
                data=excel_data,
                file_name="compliance_findings.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    else:
        st.info("No analysis results yet. Upload files and run analysis from the 'Review' tab.")

# Footer
st.markdown("---")
st.markdown("*Powered by Claude AI*")