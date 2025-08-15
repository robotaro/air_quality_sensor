import os
import sys
import pandas as pd
from glob import glob

def combine_and_sort_csvs(input_folder, output_file):
    # Get all CSV files in the input folder
    csv_files = glob(os.path.join(input_folder, '*.csv'))

    if not csv_files:
        print(f"No CSV files found in folder: {input_folder}")
        return

    # Read and concatenate all CSV files
    combined_df = pd.concat(
        (pd.read_csv(file) for file in csv_files),
        ignore_index=True
    )

    # Convert timestamp column to datetime and sort
    combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp'])
    combined_df = combined_df.sort_values(by='timestamp')

    # Save to output file
    combined_df.to_csv(output_file, index=False)
    print(f"Combined CSV saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python combine_and_sort_csvs.py <input_folder> <output_file>")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_file = sys.argv[2]
    combine_and_sort_csvs(input_folder, output_file)