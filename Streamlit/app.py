import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from streamlit_extras.no_default_selectbox import selectbox

df = pd.DataFrame() 

st.title('Clean Air in Germany')

# Add an expandable section with multiple subsections
with st.expander('More Information'):
    # Add an "About" subsection
    st.markdown('### About The Project')
    st.write('This project is an interactive visualization of air quality data for the three main cities in Germany. The goal of this project is to provide an accessible and informative way for people to explore air quality data.')

# ------------- Pollutants Diagram -----------------
# Create a selectbox widget to allow the user to select the city
selected_city = st.selectbox('Select City', ['Berlin', 'Hamburg', 'München'])
user_query = st.text_input("Search a station:", "").lower()

# Convert both the query and station names to lowercase for a case-insensitive search
def fetch_station_names(city):
    url = "https://www.umweltbundesamt.de/api/air_data/v3/stations/json?lang=de&index=code"
    response = requests.get(url, headers={"accept": "application/json"})
    if response.status_code == 200:
        json_data = response.json()
        stations = {station[2]: station[0] for station in json_data['data'].values(
        ) if station[3].lower() == city.lower()}
        return stations
    return {}

def fetch_pollutants(station_id):
    global df
    end_date = datetime.now()
    # retrieves the data for the last 4 years starting from today
    start_date = end_date - timedelta(days=1460)
    # Construct the URL with the specified dates for January 2023
    url = f"https://www.umweltbundesamt.de/api/air_data/v3/airquality/json?date_from={
        start_date.strftime('%Y-%m-%d')}&date_to={end_date.strftime('%Y-%m-%d')}&station={station_id}"
    response = requests.get(url)
    if response.status_code == 200:
        json_data = response.json()
        rows = []
        for date, data in json_data['data'][station_id].items():
            temp_row = {'Date': date}
            for component in data[3:]:
                component_name = component[0]
                temp_row[component_name] = component[1]
            rows.append(temp_row)
        # Convert the list of dictionaries to a DataFrame
        df = pd.DataFrame(rows)
        # Optionally, convert 'Date' column to datetime format
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date', ascending=True)
        df.columns = df.columns.astype(str)
        df = df.rename(columns={'1': 'PM10', '3': 'O3',
                       '5': 'NO2', '9': 'PM2.5'})
        return df

    else:
       # st.error('Sorry, there is no data available for this station.')
        return pd.DataFrame()

stations = fetch_station_names(selected_city)

if user_query:
# Filter stations based on search query if user_query is provided
    filtered_stations = {name: id for name,
                     id in stations.items() if user_query in name.lower()}
    # If search results are found, use them for the selectbox, otherwise show all stations
    if filtered_stations:
        station_names = list(filtered_stations.keys())
        st.success("There are stations with this name. Look in the dropdown menu ;)", icon="✅")

    else:
        station_names = list(stations.keys())
        st.error("No stations with this name")

else:
    # If user_query is empty, show all stations and do not display success message
    station_names = list(stations.keys())

selected_station = selectbox('Stations available:', station_names)
st.write("Select a station: ", selected_station)

# Check if dataframe is empty. If empty, raise an error message
if selected_station in stations:
    station_id = stations[selected_station]
    df = fetch_pollutants(station_id)
    if df.empty:
        st.error("Dataframe is empty") 
    else:
        st.dataframe(df.set_index(df.columns[0]))

# ------------- Pollutants Diagram -----------------

# Create a multiselect widget to allow the user to select the pollutants to display
pollutants = st.multiselect(
    'Select pollutants', ['PM10',  'O3', 'NO2', 'PM2.5'])

# Create a scatter plot to display the selected pollutants over time for each city
if pollutants:
    chart_data = pd.melt(df, id_vars='Date', value_vars=pollutants,
                         var_name='pollutant', value_name='level')
    print(df[['Date', 'PM10']].head())
    fig = px.scatter(chart_data, x='Date', y='level', color='pollutant')

    # Update the title of each subplots
    fig.update_layout(
        {'xaxis1': {'title': {'text': f'Air Quality of {selected_station}'}}})

    fig_2 = px.line(df, x='Date', y=pollutants, title=f'Trend of Pollutants in:  {selected_station}',
                  labels={'value': 'Level of Pollutant', 'variable': 'Pollutant'})
    
    # Add a title and customize axes if necessary
    fig_2.update_layout(xaxis_title='Date', yaxis_title='Level of Pollutant',
                      legend_title='Pollutant')
    
    st.plotly_chart(fig, use_container_width=True)

    st.plotly_chart(fig_2, width=800, height=600)

# ------------- Indicators Acceptable Levels -----------------

# Create a DataFrame with the acceptable levels of various air pollutants
data = {'Pollutant': ['PM10', 'O3',  'NO2', 'PM2.5', ],
        'Acceptable Level': [50, 180, 100, 25]}
acceptable_levels = pd.DataFrame(data)

# Set the index of the acceptable_levels DataFrame to the 'Pollutant' column
acceptable_levels = acceptable_levels.set_index('Pollutant')

# Define a CSS style for centering text in a column
css_style = """
<style>
    td:nth-child(2) {
        text-align: center;
    }
</style>
"""
# Display the acceptable levels as  a table without row numbers
st.markdown(f'## Level of Air Pollutants in: {selected_station}')

if not df.empty:
    grouped = df.groupby([df['Date'].dt.year])

    # Calculate the mean of each pollutant column
    annual_averages = grouped[['PM2.5','PM10', 'NO2','O3']].mean().round(1)

    # Reset the index to move the group labels into columns
    annual_averages = annual_averages.reset_index()

    # Rename the 'Date' column to 'Year'
    annual_averages = annual_averages.rename(columns={'Date': 'Year'})

    # Melt the annual_averages DataFrame to create a long format table
    long_table = annual_averages.melt(id_vars=['Year'], var_name='Pollutant', value_name='Value')

    # Pivot the long_table DataFrame to create a wide format table with columns for each year
    pollutant_table = long_table.pivot_table(index='Pollutant', columns='Year', values='Value')

    # Reindex the pollutant_table DataFrame to match the order of pollutants in the acceptable_levels DataFrame
    pollutant_table = pollutant_table.reindex(acceptable_levels.index)
    # Add a column for the acceptable levels
    pollutant_table.insert(0, 'Acceptable Level', acceptable_levels['Acceptable Level'])

    # Convert the DataFrame to an HTML table
    html_table2 = pollutant_table.to_html(formatters={'Acceptable Level': '{:,.0f}'.format})
    st.markdown(css_style + html_table2, unsafe_allow_html=True)
