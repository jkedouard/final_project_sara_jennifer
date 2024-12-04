from shiny import App, render, ui, reactive
from shinywidgets import render_altair, output_widget
from shinyswatch import theme
import pandas as pd
import geopandas as gpd
import altair as alt
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


full_data_df = pd.read_csv("trees_grouped.csv")
dropdown_choices = full_data_df['nta_name'].unique().tolist()

app_ui = ui.page_fluid(
    ui.page_auto(
        title="Tree Density vs. Air Quality in New York City", theme=theme.journal),
    ui.navset_pill_list(
        ui.nav_panel(
            "Tree Density by Neighborhood Tabulation Area (NTA)",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_select(
                        id="nta_choices",
                        label="Select Neighborhood:",
                        choices=dropdown_choices,
                        selected=dropdown_choices[1] if dropdown_choices else None
                    ),
                    ui.input_radio_buttons(
                        id="census_year_radio",
                        label="Select Census Year:",
                        choices={"2005": 2005, "2015": 2015},
                        selected=2005
                    ),
                    ui.output_text("tree_count_info")
                ),
                output_widget("tree_map")
            )
        ),
        ui.nav_panel(
            "Tree Density by Borough",
            ui.layout_sidebar(
                ui.sidebar(
                    ui.input_select(
                        id="borough_choices",
                        label="Select Borough:",
                        choices=["Manhattan", "Brooklyn",
                                 "Queens", "Bronx", "Staten Island"],
                        selected="Manhattan"
                    ),
                    ui.input_radio_buttons(
                        id="census_year_radio_borough",
                        label="Select Census Year:",
                        choices={"2005": 2005, "2015": 2015},
                        selected=2005
                    ),
                    ui.output_text("tree_count_info_borough")
                ),
                output_widget("tree_map_borough")
            )
        ),
    )
)


def server(input, output, session):

    @reactive.calc
    def full_data():
        data = pd.read_csv("trees_grouped.csv")
        data = data.rename(columns={"nta": "NTACode"}) 
        return data  

    @reactive.calc
    def full_data_borough():
        data = pd.read_csv("trees_grouped_borough.csv")
        data = data.rename(columns={"borough": "boro_name"})
        return data 

    @reactive.calc
    def geo_data():
        return gpd.read_file("shapefiles/nynta.shp")

    @reactive.calc
    def geo_data_borough():
        return gpd.read_file("shapefiles/geo_export_efd6f6d8-cbf0-4c24-b4ee-a228765d4622.shp")

    @reactive.calc
    def merged_data():
        data = full_data()
        geo = geo_data()
        merged = geo.merge(data, how='left', on='NTACode')  
        merged = merged.to_crs(epsg=4326)
        merged["geometry_json"] = merged["geometry"].apply(
            lambda x: x.__geo_interface__)
        return merged

    @reactive.calc
    def merged_data_borough():
        data = full_data_borough()
        geo = geo_data_borough()
        merged = geo.merge(data, how='left', on='boro_name')  
        merged = merged.to_crs(epsg=4326)
        merged["geometry_json"] = merged["geometry"].apply(
            lambda x: x.__geo_interface__)
        return merged

    @reactive.calc
    def filtered_data():
        selected_nta = input.nta_choices()
        selected_year = input.census_year_radio()

        if not selected_nta or not selected_year:
            return pd.DataFrame()

        data = merged_data()
        if data.empty:
            return pd.DataFrame()

        filtered = data[data["nta_name"] == selected_nta].copy()

        if str(selected_year) not in filtered.columns:
            return pd.DataFrame()

        filtered["tree_count"] = filtered[str(selected_year)]

        filtered["color"] = filtered["trees_diff"].apply(
            lambda x: "green" if x > 0 else "red"
        )
        return filtered

    @reactive.calc
    def filtered_data_borough():
        selected_borough = input.borough_choices()
        selected_year = input.census_year_radio_borough()

        if not selected_borough or not selected_year:
            return pd.DataFrame()

        data = merged_data_borough()
        if data.empty:
            return pd.DataFrame()

        filtered = data[data["boro_name"] == selected_borough].copy()

        if str(selected_year) not in filtered.columns:
            return pd.DataFrame()

        year_column = str(selected_year)
        filtered["tree_count"] = filtered[year_column]

        filtered["color"] = filtered["trees_diff"].apply(
            lambda x: "green" if x > 0 else "red"
        )
        return filtered

    @render_altair
    def tree_map():
        all_data = merged_data()
        highlight_data = filtered_data()

        if all_data.empty or highlight_data.empty:
            return alt.Chart(pd.DataFrame()).mark_geoshape().properties(width=800, height=600)

        base_map = alt.Chart(all_data).mark_geoshape(
            fill="white", stroke="grey", opacity=0.7
        ).encode(
            shape="geometry_json",
            tooltip=["nta_name"]
        ).properties(width=800, height=400)

        highlight_layer = alt.Chart(highlight_data).mark_geoshape(
            stroke="black", opacity=0.9
        ).encode(
            shape="geometry_json",
            color=alt.Color(
                "color:N",
                scale=None,
            ),
            tooltip=["nta_name", "trees_diff"]
        )

        chart = base_map + highlight_layer
        return chart

    @render_altair
    def tree_map_borough():
        all_data = merged_data_borough()
        highlight_data = filtered_data_borough()

        if all_data.empty or highlight_data.empty:
            return alt.Chart(pd.DataFrame()).mark_geoshape().properties(width=800, height=600)

        base_map = alt.Chart(all_data).mark_geoshape(
            fill="white", stroke="grey", opacity=0.7
        ).encode(
            shape="geometry_json",
            tooltip=["boro_name"]
        ).properties(width=800, height=400)

        highlight_layer = alt.Chart(highlight_data).mark_geoshape(
            fill="green", stroke="black", opacity=0.9
        ).encode(
            shape="geometry_json",
            tooltip=["boro_name", "tree_count"]
        )

        chart = base_map + highlight_layer
        chart = chart.configure_legend(
            title=None,
            labelFontSize=0,
            symbolSize=0
        )

        return chart

    @render.text
    def tree_count_info():
        data = filtered_data()
        if data.empty:
            return "Please select a year to view tree count."
        selected_nta = input.nta_choices()
        selected_year = input.census_year_radio()
        year_column = str(selected_year)
        if year_column not in data.columns:
            return f"No data available for the year {selected_year} in {selected_nta}."

        tree_count = data[year_column].iloc[0]
        return f"In {selected_year}, {tree_count} trees were recorded in {selected_nta}."

    @render.text
    def tree_count_info_borough():
        data = filtered_data_borough()
        if data.empty:
            return "Please select a year to view tree count."
        selected_borough = input.borough_choices()
        selected_year = input.census_year_radio_borough()
        year_column = str(selected_year)
        if year_column not in data.columns:
            return f"No data available for the year {selected_year} in {selected_borough}."

        tree_count = data[year_column].iloc[0]
        return f"In {selected_year}, {tree_count} trees were recorded in {selected_borough}."


app = App(app_ui, server)
