import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path


# Page configuration
st.set_page_config(
    page_title="HDB Properties Browser",
    page_icon="🏢",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# Helper functions
def parse_floor_data(floor_str):
    """Parse floor data string like '#05:1; #06:1' to extract floors and counts"""
    if pd.isna(floor_str) or floor_str == '':
        return []
    
    floors = []
    parts = floor_str.split(';')
    for part in parts:
        part = part.strip()
        if ':' in part:
            floor_num, count = part.split(':')
            floor_num = floor_num.replace('#', '').strip()
            try:
                count = int(count.strip())
                floors.append({'floor': floor_num, 'count': count})
            except:
                pass
    return floors

def get_total_units_from_floor_data(floor_str):
    """Calculate total units from floor data string"""
    floors = parse_floor_data(floor_str)
    return sum(f['count'] for f in floors)

@st.cache_data
def load_estate_data(base_path='./data/by_estate_mrt'):
    """Load all estate CSV files from by_estate folder"""
    estates = {}
    estate_path = Path(base_path)
    
    if estate_path.exists():
        for csv_file in estate_path.rglob('*.csv'):
            estate_name = str(csv_file.relative_to(base_path)).replace('.csv', '')
            try:
                df = pd.read_csv(csv_file)
                df.columns = df.columns.str.strip()
                
                # Convert room counts to numeric
                room_columns = ['2-room Flexi', '3-room', '3Gen', '4-room', '5-room']
                for col in room_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                
                estates[estate_name] = df
            except Exception as e:
                st.sidebar.error(f"Error loading {csv_file.name}: {str(e)}")
    return estates

@st.cache_data
def load_project_data(base_path='./data/by_project'):
    """Load all project CSV files from by_project folder"""
    projects = {}
    project_path = Path(base_path)
    
    if project_path.exists():
        for project_folder in project_path.iterdir():
            project_name = project_folder.stem
            csv_file = project_folder / 'floor_price_detailed.csv'
            try:
                df = pd.read_csv(csv_file)
                df.columns = df.columns.str.strip()
                projects[project_name] = df
            except Exception as e:
                st.sidebar.error(f"Error loading {csv_file.name}: {str(e)}")
    return projects

@st.cache_data
def load_floor_price_data(base_path='./data/by_project'):
    """Load floor_price_consolidated.csv files from project folders"""
    floor_price_data = {}
    project_path = Path(base_path)
    
    if project_path.exists():
        for project_folder in project_path.iterdir():
            if project_folder.is_dir():
                consolidated_file = project_folder / 'floor_price_consolidated.csv'
                if consolidated_file.exists():
                    try:
                        df = pd.read_csv(consolidated_file)
                        df.columns = df.columns.str.strip()
                        floor_price_data[project_folder.name] = df
                    except Exception as e:
                        st.sidebar.error(f"Error loading {consolidated_file.name}: {str(e)}")
    
    return floor_price_data

# Load all data
estates_data = load_estate_data()
projects_data = load_project_data()
floor_price_data = load_floor_price_data()

# Header
st.markdown('<div class="main-header">🏢 HDB Properties Browser</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Browse available HDB flats across estates</div>', unsafe_allow_html=True)

# Sidebar Filters
st.sidebar.header("🔍 Filters")

# Estate filter
if estates_data:
    estate_options = sorted(estates_data.keys())
    selected_estate = st.sidebar.selectbox(
        "Select Estate",
        options=estate_options,
        index=0 if estate_options else None
    )
else:
    st.error("No estate data found. Please ensure CSV files are in the 'by_estate' folder.")
    st.stop()

# Room Type filter (single select)
room_type_options = ['2-room Flexi', '3-room', '3Gen', '4-room', '5-room']
selected_room_type = st.sidebar.selectbox(
    "Room Type",
    options=room_type_options,
    index=3  # Default to 4-room
)

# Ethnicity filter
ethnicity_options = ['Chinese', 'Malay', 'Indian/ Other Races']
selected_ethnicity = st.sidebar.selectbox(
    "Ethnic Quota",
    options=ethnicity_options,
    index=0
)

st.sidebar.divider()

# Get filtered estate data
if selected_estate in estates_data:
    estate_df = estates_data[selected_estate].copy()
    
    # Filter projects that have the selected room type
    estate_df_filtered = estate_df[estate_df[selected_room_type] > 0].copy()
    
    # Calculate filtered units from project data
    def get_filtered_unit_count(project_name, room_type, ethnicity):
        """Get unit count for a project filtered by room type and ethnicity"""
        if project_name not in projects_data:
            return 0
        
        project_df = projects_data[project_name]
        filtered = project_df[
            (project_df['flat_type'] == room_type) & 
            (project_df['ethnicity'] == ethnicity)
        ]
        
        total = 0
        for floor_data in filtered['floor_data']:
            total += get_total_units_from_floor_data(floor_data)
        
        return total
    
    # Add filtered unit counts
    estate_df_filtered['Filtered_Units'] = estate_df_filtered['Project Name'].apply(
        lambda x: get_filtered_unit_count(x, selected_room_type, selected_ethnicity)
    )
    
    # Remove projects with 0 filtered units
    estate_df_filtered = estate_df_filtered[estate_df_filtered['Filtered_Units'] > 0]
    
else:
    st.error(f"Estate '{selected_estate}' data not found.")
    st.stop()

# Summary Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Estate", selected_estate.replace('_', ' ').title())

with col2:
    st.metric("Projects Available", len(estate_df_filtered))

with col3:
    total_filtered_units = estate_df_filtered['Filtered_Units'].sum()
    st.metric(f"{selected_room_type} Units", f"{int(total_filtered_units)}")

with col4:
    keys_available = len(estate_df_filtered[estate_df_filtered['Probable Completion'] == 'Keys available'])
    st.metric("Keys Available Now", keys_available)

st.divider()

# Create tabs
tab1, tab2, tab3 = st.tabs(["📊 Overview", "🗺️ Map View (WIP)", "📋 Full List"])

with tab1:
    col1, col2 = st.columns(2)
    
    with col1:
        # Remaining Lease Distribution (by units)
        st.subheader("Distribution by Remaining Lease")
        
        lease_units = estate_df_filtered.groupby('Remaining Lease')['Filtered_Units'].sum().sort_index()
        
        fig_lease = go.Figure(data=[
            go.Bar(
                x=lease_units.index,
                y=lease_units.values,
                marker_color='#1f77b4',
                text=lease_units.values,
                textposition='auto',
            )
        ])
        fig_lease.update_layout(
            xaxis_title="Remaining Lease",
            yaxis_title="Number of Units",
            height=350,
            showlegend=False
        )
        st.plotly_chart(fig_lease, use_container_width=True)
    
    with col2:
        # Completion Status Distribution (by units, bar chart with year or 'Available Now')
        st.subheader("Distribution by Completion Status")
        
        # Categorize completion dates
        def categorize_completion(completion):
            if pd.isna(completion) or completion == '':
                return 'Unknown'
            elif 'Keys available' in str(completion) or 'Completed' in str(completion):
                return 'Available Now'
            else:
                # Extract year from completion date
                try:
                    # Try to extract year from various formats
                    import re
                    year_match = re.search(r'20\d{2}', str(completion))
                    if year_match:
                        return year_match.group(0)
                    return str(completion)
                except:
                    return str(completion)
        
        estate_df_filtered['Completion_Year'] = estate_df_filtered['Probable Completion'].apply(categorize_completion)
        completion_units = estate_df_filtered.groupby('Completion_Year')['Filtered_Units'].sum().sort_index()
        
        # Sort so 'Available Now' comes first if it exists
        if 'Available Now' in completion_units.index:
            available_now = completion_units['Available Now']
            completion_units = completion_units.drop('Available Now')
            completion_units = pd.concat([pd.Series({'Available Now': available_now}), completion_units])
        fig_completion = go.Figure(data=[
            go.Bar(
                x=completion_units.index,
                y=completion_units.values,
                marker_color='#2ecc71',
                text=completion_units.values,
                textposition='auto',
            )
        ])
        fig_completion.update_layout(
            xaxis_title="Completion Status",
            yaxis_title="Number of Units",
            height=350,
            showlegend=False,
            xaxis=dict(type='category'),
        )
        st.plotly_chart(fig_completion, use_container_width=True)
    
    # Project Distribution (by units)
    st.subheader("Distribution by Project")
    
    project_units = estate_df_filtered.set_index('Project Name')['Filtered_Units'].sort_values(ascending=True)
    
    fig_project = go.Figure(data=[
        go.Bar(
            x=project_units.index,
            y=project_units.values,
            orientation='v',
            marker_color='#9b59b6',
            text=project_units.values,
            textposition='auto',
        )
    ])
    fig_project.update_layout(
        yaxis_title="Number of Units",
        xaxis_title="Project",
        # height=min(10, int(max(project_units.values))),
        showlegend=False
    )
    st.plotly_chart(fig_project, use_container_width=True)

with tab2:
    st.subheader("Project Locations Map")
    
    # Categorize completion for map coloring
    def categorize_completion_map(completion):
        if pd.isna(completion) or completion == '':
            return 'Unknown'
        elif 'Keys available' in str(completion) or 'Completed' in str(completion):
            return 'Available Now'
        else:
            # Extract year from completion date
            try:
                import re
                year_match = re.search(r'20\d{2}', str(completion))
                if year_match:
                    return year_match.group(0)
                return str(completion)
            except:
                return str(completion)
    
    estate_df_filtered['Completion_Category'] = estate_df_filtered['Probable Completion'].apply(categorize_completion_map)
    
    # Filter projects with valid coordinates
    map_df = estate_df_filtered.dropna(subset=['Latitude', 'Longitude']).copy()
    
    if len(map_df) > 0:
        # Create map with project names as labels
        fig = px.scatter_mapbox(
            map_df,
            lat='Latitude',
            lon='Longitude',
            text='Project Name',
            hover_name='Project Name',
            hover_data={
                'Remaining Lease': True,
                'Probable Completion': True,
                'Filtered_Units': True,
                'Latitude': False,
                'Longitude': False,
                'Project Name': False
            },
            color='Project Name',
            size='Filtered_Units',
            size_max=25,
            zoom=12,
            height=600,
            labels={'Filtered_Units': f'{selected_room_type} Units'},
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        
        fig.update_layout(
            mapbox_style="open-street-map",
            margin={"r": 0, "t": 0, "l": 0, "b": 0}
        )
        
        # Fix: Remove the invalid 'line' property for scattermapbox markers
        fig.update_traces(
            textposition='top center',
            textfont=dict(size=9, color='black')
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"📍 Showing {len(map_df)} projects. Marker size represents available {selected_room_type} units for {selected_ethnicity} quota.")
    else:
        st.warning("No projects with location data available for the selected filters.")

with tab3:
    st.subheader(f"Complete Project Listing - {selected_room_type}")
    
    # Search functionality
    search = st.text_input("🔍 Search projects by name", "")
    
    if search:
        display_df = estate_df_filtered[estate_df_filtered['Project Name'].str.contains(search, case=False)]
    else:
        display_df = estate_df_filtered
    
    st.markdown(f"*Showing {len(display_df)} projects*")
    
    # Sort by units descending
    display_df = display_df.sort_values('Filtered_Units', ascending=False)
    
    # Calculate total units for percentage calculation
    total_units_in_estate = display_df['Filtered_Units'].sum()
    
    # Display each project as an expandable card
    for idx, row in display_df.iterrows():
        # Calculate percentage of total units
        unit_percentage = (row['Filtered_Units'] / total_filtered_units * 100)
        
        with st.expander(f"**{row['Project Name']}** - {int(row['Filtered_Units'])} units ({unit_percentage:.1f}% of total)", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"### {row['Project Name']}")
                st.markdown(f"**📍 Town:** {row['Town']}")
                st.markdown(f"**⏰ Remaining Lease:** {row['Remaining Lease']}")
                st.markdown(f"**📅 Probable Completion:** {row['Probable Completion']}")
                
                # MRT and walking information
                if 'Nearest_MRT' in row and pd.notna(row['Nearest_MRT']):
                    st.markdown(f"**🚇 Nearest MRT:** {row['Nearest_MRT']} ({row.get('MRT_Station_Code', 'N/A')})")
                    if 'bus_duration_min' in row and pd.notna(row['bus_duration_min']):
                        st.markdown(f"**⏱️ Bus Duration:** {row['bus_duration_min']:.0f} min")
                    # if 'MRT_Distance_m' in row and pd.notna(row['MRT_Distance_m']):
                    #     st.markdown(f"**📏 MRT Distance:** {row['MRT_Distance_m']:.0f}m")
                    if 'Walk_Distance_m' in row and pd.notna(row['Walk_Distance_m']):
                        st.markdown(f"**🚶 Walking Distance:** {row['Walk_Distance_m']:.0f}m (~{row.get('Walk_Duration_min', 0):.0f} min)")
                
                # All room types available
                st.markdown("**Available Room Types:**")
                room_types_avail = []
                for room_col in ['2-room Flexi', '3-room', '3Gen', '4-room', '5-room']:
                    if room_col in row and row[room_col] > 0:
                        room_types_avail.append(f"{room_col}: {int(row[room_col])}")
                st.markdown("• " + "  \n• ".join(room_types_avail))
            
            with col2:
                st.markdown(f"### Current Filter")
                st.markdown(f"**Room Type:** {selected_room_type}")
                st.markdown(f"**Ethnicity:** {selected_ethnicity}")
                st.markdown(f"**Available Units:** {int(row['Filtered_Units'])}")
                st.markdown(f"**% of Total:** {unit_percentage:.1f}%")
                
                if 'URL' in row and pd.notna(row['URL']):
                    st.link_button("View on HDB Website", row['URL'], use_container_width=True)
            
            # Use floor_price_consolidated.csv if available
            if row['Project Name'] in floor_price_data:
                st.divider()
                st.markdown("#### Floor and Price Range Details")
                
                floor_price_df = floor_price_data[row['Project Name']]
                
                # Filter by room type and ethnicity
                filtered_floor_price = floor_price_df[
                    (floor_price_df['flat_type'] == selected_room_type) & 
                    (floor_price_df['ethnicity'] == selected_ethnicity)
                ]
                
                if not filtered_floor_price.empty:
                    for _, fp_row in filtered_floor_price.iterrows():
                        price_range = fp_row['price_range']
                        if isinstance(fp_row['price_range'], float):
                            price_range = "N/A"
                        st.markdown(f"**Blocks:** {fp_row['blocks']}")
                        st.markdown(f"**Total Units:** {fp_row['total_units']}")
                        st.markdown(f"**Price Range:** {price_range.replace('$', '\$')}")
                        
                        # Parse and display floor summary
                        floors = parse_floor_data(fp_row['floor_summary'])
                        if floors:
                            st.markdown("**Floor Distribution:**")
                            floor_table = pd.DataFrame(floors)
                            floor_table.columns = ['Floor', 'Units']
                            # st.dataframe(
                            #     floor_table,
                            #     use_container_width=True,
                            #     hide_index=True
                            # )        
                            fig_floor = go.Figure(data=[
                                go.Bar(
                                    x=floor_table['Floor'],
                                    y=floor_table['Units'],
                                    marker_color='#1f77b4',
                                    text=floor_table['Units'],
                                    textposition='auto',
                                )
                            ])
                            fig_floor.update_layout(
                                xaxis_title="Floor",
                                yaxis_title="Number of Units",
                                # height=350,
                                showlegend=False,
                                xaxis=dict(
                                    tickmode='array', # Set tick mode to 'array' to use custom values/text
                                    tickvals=floor_table['Floor'], # Specify which values should have ticks
                                    # ticktext=custom_labels # Specify the labels for those ticks
                                )
                            )
                            st.plotly_chart(fig_floor, use_container_width=True)
                else:
                    st.info(f"No floor/price data available for {selected_room_type} units with {selected_ethnicity} quota.")
            
            # Fallback to old project data if floor_price_consolidated doesn't exist
            elif row['Project Name'] in projects_data:
                st.divider()
                st.markdown("#### Detailed Unit Breakdown")
                
                project_df = projects_data[row['Project Name']]
                filtered_project = project_df[
                    (project_df['flat_type'] == selected_room_type) & 
                    (project_df['ethnicity'] == selected_ethnicity)
                ]
                
                if not filtered_project.empty:
                    # Parse and display floor information
                    floor_breakdown = []
                    for _, prow in filtered_project.iterrows():
                        floors = parse_floor_data(prow['floor_data'])
                        for floor in floors:
                            floor_breakdown.append({
                                'Block': prow['block'],
                                'Floor': floor['floor'],
                                'Units': floor['count'],
                                'Price Range': prow['price_range']
                            })
                    
                    if floor_breakdown:
                        floor_df_display = pd.DataFrame(floor_breakdown)
                        st.dataframe(
                            floor_df_display,
                            use_container_width=True,
                            hide_index=True
                        )

# Footer
st.divider()
st.markdown(f"""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p><strong>Filtered View:</strong> {selected_estate.replace('_', ' ').title()} | {selected_room_type} | {selected_ethnicity}</p>
    <p>Data from HDB. For official information, please visit the HDB website.</p>
</div>
""", unsafe_allow_html=True)