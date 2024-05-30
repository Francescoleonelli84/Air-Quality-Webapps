from datetime import datetime, timedelta
import requests
import gradio as gr
import json
import pandas as pd
import matplotlib.pyplot as plt
import io
from PIL import Image
import numpy as np
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import seaborn as sns
from jinja2 import Template


# https://www.umweltbundesamt.de/daten/luft/luftdaten/doc
# Measured components:
# 1 -> PM10
# 3 -> O3
# 5 -> NO2
# 9 -> PM2
# (Calculation base: https://www.umweltbundesamt.de/en/calculation-base-air-quality-index)

station_data = {}
filtered_df = pd.DataFrame()

def create_graph(dataframe):
    if dataframe.empty:
        return "Dataframe is empty"

    dataframe['Date'] = pd.to_datetime(dataframe['Date'])

    # Ottieni il primo giorno degli ultimi tre mesi
    first_day_of_current_month = pd.Timestamp.now().replace(day=1)
    first_day_of_last_three_months = first_day_of_current_month - \
        pd.DateOffset(months=2)
    df_last_three_months = dataframe[dataframe['Date']
                                     >= first_day_of_last_three_months]

    # Assumi che 'Component ID' sia già nel formato corretto
    component_ids = dataframe['Component ID'].unique()
    df_filtered = df_last_three_months[df_last_three_months['Component ID'].isin(
        component_ids)]

    # Crea il grafico
    sns.set_context("notebook", font_scale=2, rc={"lines.linewidth": 3})
    plt.figure(figsize=(20, 7))
    sns.lineplot(x='Date', y='Value', hue='Component ID',
                 data=df_filtered, dashes=False)

    plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    plt.title('Trend of Components in the Last Three Months')
    plt.ylabel('Value')
    plt.xlabel('Date')

    # current_date = pd.Timestamp.now()
    # if df_filtered['Date'].max() < current_date:
    #     plt.xlim(df_filtered['Date'].min(), current_date)

    # Save the graph in a buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png',  bbox_inches='tight')
    buf.seek(0)
    plt.close()

    # Gives back the image of the graph
    image = Image.open(buf)
    return np.array(image)


def fetch_API_data(city_input): 
    # fetch the general data on stations
    url = "https://www.umweltbundesamt.de/api/air_data/v3/stations/json?lang=de&index=code"
    response = requests.get(url, headers={"accept": "application/json"})
  #  response = requests.get(url)
    if response.status_code == 200:
        json_data = json.loads(response.text)
        matches = []
        for station in json_data['data'].values():
            if station[3].lower() == city_input.lower():
                station_id = station[0]
                station_code = station[1]
                station_name = station[2]
                active_from = station[5]
                # fetches only active stations 
                active_to = station[6] if station[6] else "Active"
                if active_to == "Active":

                    matches.append({
                        'ID': station_id,
                        'Code': station_code,
                        'Station': station_name,
                        'Begin': active_from,
                        'End': active_to
                    })
                else:
                    pass
        if matches:
            df =  pd.DataFrame(matches)
            csv_filename = f"{city_input}_stations.csv"
            df.to_csv(csv_filename, index=False)
            return df
        else:
            return pd.DataFrame()
    else:
        return pd.DataFrame(), print("Request Error: ", response.status_code)


# searches the data from station code in the last three months
def fetch_station_details(station_id):
    global filtered_df
    # create new dataframe-object every time a cell has been clicked 
    filtered_df = pd.DataFrame()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    url = f"https://www.umweltbundesamt.de/api/air_data/v3/airquality/json?date_from={
        start_date.strftime('%Y-%m-%d')}&date_to={end_date.strftime('%Y-%m-%d')}&station={station_id}"
    response = requests.get(url)

    if response.status_code == 200:
        json_data = response.json()
        rows = []
        for date, data in json_data['data'][station_id].items():
            for component in data[3:]:
                rows.append({
                    'Date': date,
                    'Component ID': return_component_id(component[0]),
                    'Value': component[1],
                    'Index': component[2],
                    'Y-Value': component[3]
                })

        df = pd.DataFrame(rows)
        today_str = datetime.now().strftime('%Y-%m-%d')
        df['Date'] = pd.to_datetime(df['Date'])
        filtered_df = df[df['Date'].dt.strftime('%Y-%m-%d') == today_str]
        station_data[station_id] = filtered_df
        graph = create_graph(df)
        # checks if dataframe is empty. If not, datas are reported on respective Gradio components, if yes, everything is set to empty or None  
        if not df.empty:
            return df, graph, "", "", filtered_df
    else:
        return None, None, f"<h1> No data available for this station </h1>", "", filtered_df

#  returns for every number of component the type of component in the cell of the dataframe
def return_component_id(component):
    if component == 1:
        return str(component) + " " + "(PM10)"
    if component == 3:
        return str(component) + " " + "(O3)"
    if component == 5:
        return str(component) + " " + "(N02)"
    if component == 9:
        return str(component) + " " + "(PM2.5)"
    else:
        return component


def return_variable_and_fetch(evt: gr.SelectData):
    value = evt.value
    print(f"value of cell is: {value}")
    return value, f"<h1> You selected Id-Nr. {value} </h1>"


def update_label(station_id):
    filtered_df = station_data.get(station_id)
    current_date = datetime.now().strftime("%d-%m-%Y")
    _, _, _, _, filtered_df = fetch_station_details(station_id)
    air_quality_status = returns_average_air_quality(filtered_df)
    print(f"Filtered df is with station number:{station_id}: ", _, _, _, _, filtered_df)
    html_content = f"""
    <div style="margin: auto; width: 50%; padding: 10px; border: 1px solid gray; border-radius: 5px; box-shadow: 2px 2px 2px #888888;">
        <p style="text-align: center; font-size: 24px">For the station Nr. <b> {station_id} </b> </p>
        <p style="text-align: center; font-size: 24px">On the day {current_date}</p>
        <p style="text-align: center; font-size: 24px">The air quality status is on average: {air_quality_status}</p>
    </div>
    """
    return html_content


def returns_average_air_quality(filtered_df):
    # Checks if dataframe received from fetch_station_details() is empty
    if filtered_df.empty:
        return "<span style=color:red;>No detail on the average air status of this station is available</span></p>"

    else:

        component_statuses = []
        limits = {

            1: [(35, "Good"), (50, "Moderate")],  # Limits for PM10
            3: [(120, "Good"), (180, "Moderate")],  # Limits for O3
            5: [(40, "Good"), (100, "Moderate")],  # Limits for NO2
            9: [(20, "Good"), (25, "Moderate")]  # Limits for PM2.5
        }

        last_hour = filtered_df['Date'].max()
        print("Last hour is: ", last_hour)
        last_hour_data = filtered_df[filtered_df['Date'] == last_hour]
        print("Last hour data", last_hour_data)

        for component_id, limits in limits.items():
            component_data = last_hour_data[last_hour_data['Component ID'].str.contains(
                str(component_id))]
            print("Last hour component data", component_data)
            if not component_data.empty:
                value = component_data['Value'].iloc[0]
                for limit, status in limits:
                    if value <= limit:
                        component_statuses.append(status)
                        break
                else:
                    component_statuses.append('Poor')

        return check_average_air_quality(component_statuses)


def check_average_air_quality(component_statuses):
    # Assume that the best possible quality is "Good"
    worst_status_level = 0
    # Iterate over the individual component statuses and increments of 1 the counter for every exceeded limit
    for status in component_statuses:
        if status == 'Moderate' and worst_status_level < 1:
            worst_status_level = 1
        elif status == 'Poor':
            worst_status_level = 2
    if worst_status_level == 0:
        return "<span style=color:green;>Good</span></p>"
    elif worst_status_level == 1:
        return "<span style=color:orange;>Moderate</span></p>"
    else:
        return "<span style=color:red;>Poor</span></p>"

with gr.Blocks() as demo:
   # Section 1: Find station
    # Input station name
    input_text = gr.Textbox(lines=2, placeholder="Input the name of the city")

    # fetch data button
    fetch_API_data_button = gr.Button("Fetch")

    # First Dataframe
    station_dataframe = gr.Dataframe(headers=[
        'ID', 'Code', 'Station', 'Begin',  'End'], interactive=False, type="pandas")
    # Hidden ID-Textbox
    hidden_id_texbox = gr.Textbox(label="ID", visible=False)

    fetch_API_data_button.click(fn=fetch_API_data, inputs=input_text,
                                outputs=[station_dataframe])

    selected_id_display = gr.HTML()
    station_dataframe.select(return_variable_and_fetch, None, [
        hidden_id_texbox, selected_id_display])

    hidden_id_texbox_html = gr.HTML()

    # Section 2: find station Air Quality Data
    components_dataframe = gr.Dataframe(
        headers=['Date', 'Component ID', 'Value', 'Index', 'Y-Value'])

    output_graph = gr.Image()

    check_average_air_quality_button = gr.Button(
        "Check average air quality for today")

    jumbotron = gr.HTML()

    check_average_air_quality_button.click(
        fn=update_label, inputs=hidden_id_texbox, outputs=jumbotron)

    hidden_id_texbox.change(fetch_station_details, hidden_id_texbox,
                            [components_dataframe, output_graph, hidden_id_texbox_html, jumbotron])

#    demo.launch(share=True, debug=True)
    demo.load(None, None, None)

if __name__ == "__main__":
    demo.launch()
