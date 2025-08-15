import sys
import pandas as pd
import matplotlib.pyplot as plt


def plot_pm_and_particles(csv_file):
    # Load the CSV
    df = pd.read_csv(csv_file)

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')

    # Select columns
    pm_columns = [col for col in df.columns if col.startswith('pm')]
    particles_columns = [col for col in df.columns if col.startswith('particles_')]

    # Create figure and subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 8), sharex=True)

    # Plot PM data
    for col in pm_columns:
        ax1.plot(df['timestamp'], df[col], label=col)
    ax1.set_title('PM Sensor Data')
    ax1.set_ylabel('PM Values')
    ax1.legend(loc='upper right')
    ax1.grid(True)

    # Plot Particle Count data
    for col in particles_columns:
        ax2.plot(df['timestamp'], df[col], label=col)
    ax2.set_title('Particle Counts')
    ax2.set_ylabel('Count')
    ax2.set_xlabel('Timestamp')
    ax2.legend(loc='upper right')
    ax2.grid(True)

    # Improve x-axis format
    fig.autofmt_xdate()

    # Show plot
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python plot_pm_and_particles.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]
    plot_pm_and_particles(csv_file)