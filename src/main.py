import os
import time
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from openpyxl.drawing.image import Image

from utils import *

load_dotenv()  # Load environment variables from .env file

DATA_FOLDER = os.getenv('DATA_FOLDER', 'data')  # Default to 'data' if not set
SAVE_FOLDER = "../data/"

class LocationAnalysis:
    """Class to perform analysis for a specific location."""
    def __init__(self, df, location):
        self.df = isolate_location(df, location)
        self.location = location
        # Deduplicate column names for cases like location == "Scotland".
        self.loc_cols = list(dict.fromkeys([
            "Cause",
            "Scotland_2019",
            f"{location}_2014",
            f"{location}_2015",
            f"{location}_2016",
            f"{location}_2017",
            f"{location}_2018",
            f"{location}_2019",
        ]))

    def analyze_gender(self, gender_df, gender="Female"):
        """Perform analysis for a specific gender."""
        gender_df = gender_df.loc[:, self.loc_cols].copy()

        # Calculate the difference between Scotland and the location for 2019
        gender_df[f"{self.location}_diff"] = gender_df["Scotland_2019"] - gender_df[f"{self.location}_2019"]

        # Sort the DataFrame by Scotland's 2019 DALY rate in descending order
        gender_df = gender_df.sort_values(by="Scotland_2019", ascending=False).reset_index(drop=True)

        # Calculate CAGR for the location 2014-19 and 2017-19
        gender_df[f"{self.location}_CAGR_2014"] = gender_df.apply(lambda row: get_cagr(row, self.location, 2014, 2019), axis=1)
        gender_df[f"{self.location}_CAGR_2017"] = gender_df.apply(lambda row: get_cagr(row, self.location, 2017, 2019), axis=1)

        self.threshold = 1 # 1% CAGR threshold for inclusion change
        gender_df[f"{self.location}_inclusion_change"] = gender_df.apply(lambda row: "Yes" if (self.threshold - row[f"{self.location}_CAGR_2014"])*(1 - row[f"{self.location}_CAGR_2017"]) < 0 else "No", axis=1)

        # Plot the CAGR changes for causes that changed inclusion
        # plot_cagr_changes(gender_df, self.location)

        # Calculate all Thiel-Sen slopes for the location and add them to the DataFrame
        for norm_mode in ["mean", "median", "interval", "base"]:
            gender_df[f"{self.location}_tsq2_{norm_mode}"] = gender_df.apply(lambda row: get_tsq(list(range(2014, 2020)), [row[f"{self.location}_{yr}"] for yr in range(2014, 2020)], q=2, norm_mode=norm_mode), axis=1)
        for norm_mode in ["mean", "median", "interval", "base"]:
            gender_df[f"{self.location}_tsq3_{norm_mode}"] = gender_df.apply(lambda row: get_tsq(list(range(2014, 2020)), [row[f"{self.location}_{yr}"] for yr in range(2014, 2020)], q=3, norm_mode=norm_mode), axis=1)
        
        # Get correlation matrices for the metrics
        cols = [f"{self.location}_CAGR_2014", f"{self.location}_CAGR_2017"] + [f"{self.location}_tsq2_{norm_mode}" for norm_mode in ["mean", "median", "interval", "base"]] + [f"{self.location}_tsq3_{norm_mode}" for norm_mode in ["mean", "median", "interval", "base"]]

        corr_pearson = gender_df[cols].corr(method="pearson")
        corr_spearman = gender_df[cols].corr(method="spearman")
        corr_kendall = gender_df[cols].corr(method="kendall")

        save_heatmap(corr_pearson, f"Pearson - {self.location}", SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_pearson.png")
        save_heatmap(corr_spearman, f"Spearman - {self.location}", SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_spearman.png")
        save_heatmap(corr_kendall, f"Kendall - {self.location}", SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_kendall.png")

        plot_sheets = {
            f'{gender}_pearson': os.path.join(SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_pearson.png"),
            f'{gender}_spearman': os.path.join(SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_spearman.png"),
            f'{gender}_kendall': os.path.join(SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_{gender}_corr_kendall.png"),
        }

        save_path = os.path.join(SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_analysis.xlsx")

        writer_kwargs = {}
        if os.path.exists(save_path):
            # 'if_sheet_exists' is only valid in append ('a') mode
            writer_kwargs = {'mode': 'a', 'engine': 'openpyxl', 'if_sheet_exists': 'replace'}
        else:
            # 'w' mode creates the file from scratch
            writer_kwargs = {'mode': 'w', 'engine': 'openpyxl'}

        with pd.ExcelWriter(save_path, **writer_kwargs) as writer:
            gender_df.to_excel(writer, sheet_name=gender, index=False)
            
            workbook = writer.book
            for sheet_name, img_path in plot_sheets.items():
                if sheet_name not in workbook.sheetnames:
                    worksheet = workbook.create_sheet(sheet_name)
                else:
                    worksheet = workbook[sheet_name]
                
                # Dimensions
                h,w = 18.92, 24.49 # cm
                
                img = Image(img_path)
                img.width = cm_to_pixels(w)
                img.height = cm_to_pixels(h)
                worksheet.add_image(img, 'B2')
        
        # Once done delete the temporary plot images
        for img_path in plot_sheets.values():
            if os.path.exists(img_path):
                os.remove(img_path)

        return gender_df


    def analyze_location(self):
        """Perform analysis for a specific location."""
        start = time.time()

        # Form pivot table
        self.df["location_yr"] = self.df["Location"] + "_" + self.df["Year"].astype(str)
        self.df["daly_int"] = (
            pd.to_numeric(
                self.df["DALY rate"].astype(str).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            )
            .round()
            .astype("Int64")
        )
        tables = {}
        for gender in self.df["Sex"].unique():
            # Filter the data for the current gender
            filtered_df = self.df[self.df["Sex"] == gender]
            
            # Pivot the data to have causes as columns and location-year combinations as rows
            pivoted_df = pd.pivot_table(
                filtered_df,
                index='Cause',
                columns='location_yr',
                values='daly_int',
                aggfunc='first' # Use 'sum' or 'mean' if you have duplicate rows for the same condition/location/year
            ).reset_index()

            # Clean up the axis label (removes the 'location_year' label floating above the columns)
            pivoted_df.columns.name = None
            
            # Save the table in our dictionary
            tables[gender] = pivoted_df
        
        for gender_df, gender in zip(tables.values(), tables.keys()):
            if gender != "Both sexes":
                tables[gender] = self.analyze_gender(gender_df, gender)
        
        # with pd.ExcelWriter(os.path.join(SAVE_FOLDER, f"{self.location.lower().replace(' ', '_')}_analysis.xlsx")) as writer:
        #     tables["Male"].to_excel(writer, sheet_name="Male", index=False)
        #     tables["Female"].to_excel(writer, sheet_name="Female", index=False)
        
        end = time.time()

        return round(end - start, 2)


if __name__ == "__main__":
    df = load_data(DATA_FOLDER, "sbod_data.csv")

    for location in tqdm(df["Location"].unique(), desc="Analyzing locations"):
        if location == "Scotland":
            continue  # Skip Scotland as it's our reference point
        location_analysis = LocationAnalysis(df, location)
        time_taken = location_analysis.analyze_location()
        tqdm.write(f"Analysis for {location} completed in {time_taken} seconds.")