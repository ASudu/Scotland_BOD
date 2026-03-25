import os
import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

def load_data(folder, filename):
    """Load the dataset from the specified file path."""
    fpath = os.path.join(folder, filename)
    df = pd.read_csv(fpath)

    for dir in ["North", "East", "West"]:
        mask = df["Location"].str.startswith(dir)
        df.loc[mask, "Location"] = f"{dir} Scotland"
    
    df.to_csv(os.path.join(folder, "sbod_data_cleaned.csv"), index=False)  # Save the cleaned data for future use

    return df

def isolate_location(df, location, only_all_ages=True):
    """Filter the dataset for a specific location."""
    # We need only DALY rate for now
    df1 = df[df["RAG"] == "DALY rate"]
    df1 = df1[df1["Location"].isin([location, "Scotland"])]
    df1 = df1[df1["Cause"] != "All causes of disease and injury"]

    cols_to_drop = ["RAG", "Value", "Small numbers"]
    df1 = df1.drop(columns=cols_to_drop)
    df1 = df1.rename(columns={"Measure": "DALY rate"})

    if only_all_ages:
        df1 = df1[df1["Age"] == "All ages"]
        df1 = df1.drop(columns=["Age"])
    return df1

def save_df(df, folder, filename):
    """Save the DataFrame to a CSV file."""
    fpath = os.path.join(folder, filename)
    df.to_csv(fpath, index=False)

def get_cagr(row, loc, base_yr, final_yr=2019):
    """
    Calculate the Compound Annual Growth Rate (CAGR) for a specific location between two years.
    CAGR is calculated using the formula:
    CAGR = ((Final Value / Initial Value)^(1 / Number of Years) - 1)*100%
    """
    base_value = row[f"{loc}_{base_yr}"]
    final_value = row[f"{loc}_{final_yr}"]
    if base_value == 0:
        return 0
    cagr = 100*((final_value / base_value) ** (1 / (final_yr - base_yr)) - 1)
    return round(cagr,2)

def get_pos(N, percentile=50):
    val = (percentile / 100) * (N - 1) # This gives us the position in a 0-indexed list
    return math.floor(val), val

def get_tsq(x, y=None, q=2, norm_mode="mean"):
    # Supports:
    # 1) get_tsq({year: value, ...}, q=2)
    # 2) get_tsq([years...], [values...], q=2)
    if y is None:
        if not isinstance(x, dict):
            raise ValueError("If 'y' is None, 'x' must be a dict of {x: y}.")
        x_arr = np.asarray(list(x.keys()), dtype=float)
        y_arr = np.asarray(list(x.values()), dtype=float)
    else:
        x_arr = np.asarray(x, dtype=float)
        y_arr = np.asarray(y, dtype=float)

    n = x_arr.size
    if n < 2:
        return 0.0

    # All pairwise slopes for i < j (vectorized)
    i, j = np.triu_indices(n, k=1)
    dx = x_arr[j] - x_arr[i]
    dy = y_arr[j] - y_arr[i]
    slopes = dy / dx  # dx != 0 for years

    # Percentile selection
    percentile = 50 if q == 2 else 75 if q == 3 else 50
    order = np.argsort(slopes)
    slopes_sorted = slopes[order]
    i_sorted = i[order]
    j_sorted = j[order]

    m = slopes_sorted.size
    ts_index, weight_val = get_pos(m, percentile)
    frac = weight_val - ts_index

    if ts_index >= m - 1:
        ts_slope = slopes_sorted[-1]
        frac = 0.0
    else:
        ts_slope = slopes_sorted[ts_index] + frac * (slopes_sorted[ts_index + 1] - slopes_sorted[ts_index])

    # Normalization constant
    if norm_mode == "mean":
        norm_const = y_arr.mean()
    elif norm_mode == "median":
        norm_const = np.median(y_arr)
    elif norm_mode == "interval":
        if frac == 0.0 or ts_index >= m - 1:
            yrs_idx = np.array([i_sorted[ts_index], j_sorted[ts_index]])
        else:
            yrs_idx = np.unique(
                np.array([
                    i_sorted[ts_index], j_sorted[ts_index],
                    i_sorted[ts_index + 1], j_sorted[ts_index + 1]
                ])
            )
        norm_const = y_arr[yrs_idx].mean()
    elif norm_mode == "base":
        if frac == 0.0 or ts_index >= m - 1:
            yrs_idx = np.array([i_sorted[ts_index], j_sorted[ts_index]])
        else:
            yrs_idx = np.unique(
                np.array([
                    i_sorted[ts_index], j_sorted[ts_index],
                    i_sorted[ts_index + 1], j_sorted[ts_index + 1]
                ])
            )
        norm_const = y_arr[yrs_idx].min()
    else:
        raise ValueError("norm_mode must be one of: 'mean', 'median', 'interval'")

    return round(100 * ts_slope / norm_const, 2) if norm_const != 0 else 0.0

def plot_cagr_changes(df, location, save_path=None):
    """Plot the CAGR changes for causes that changed inclusion status."""
    plot_df = df[df[f"{location}_inclusion_change"] == "Yes"][["Cause", f"{location}_CAGR_2014", f"{location}_CAGR_2017"]]
    plot_df = plot_df.melt(id_vars="Cause", var_name="Year", value_name="CAGR")
    plot_df["Year"] = plot_df["Year"].str.replace(f"{location}_CAGR_", "")
    
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.barplot(data=plot_df, x="CAGR", y="Cause", hue="Year", ax=ax)
    ax.set_title(f"CAGR Changes for Causes with Inclusion Status Change in {location}")
    ax.set_xlabel("CAGR (%)")
    ax.set_ylabel("Cause")
    ax.legend(title="Year")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    plt.close(fig)