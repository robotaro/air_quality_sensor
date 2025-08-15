import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture

# === CONFIGURATION ===
CSV_FILE = r"D:\air_quality_data_combined.csv"
NUM_GAUSSIANS = 6
ALPHA = 0.7

# === LOAD DATA ===
print(f"Loading data from: {CSV_FILE}")
df = pd.read_csv(CSV_FILE)
df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')

# === SELECT FEATURES ===
pm_cols = [col for col in df.columns if col.startswith('pm')]
particles_cols = [col for col in df.columns if col.startswith('particles_')]
features = pm_cols + particles_cols

print(f"Detected {len(df)} data points.")
print(f"Using {len(features)} features: {features}")
print(f"Fitting Gaussian Mixture Model with {NUM_GAUSSIANS} components...")

# === FIT GMM ===
X = df[features].astype(np.float64)
gmm = GaussianMixture(
    n_components=NUM_GAUSSIANS,
    covariance_type='full',
    reg_covar=1e-5,
    random_state=42
)
gmm.fit(X)

# === COMPUTE LOG-LIKELIHOODS ===
df['log_likelihood'] = gmm.score_samples(X)

# === PLOT ===
fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True)
fig.suptitle(f"GMM Anomaly Detection — {NUM_GAUSSIANS} Gaussian Components", fontsize=16)

# 1. Log-likelihood subplot
axes[0].plot(df['timestamp'], df['log_likelihood'], color='black', linewidth=0.5)
axes[0].set_title("Log-Likelihood of Each Data Point")
axes[0].set_ylabel("Log-Likelihood")
axes[0].grid(True)

# 2. PM sensor data subplot
for col in pm_cols:
    axes[1].plot(df['timestamp'], df[col], label=col, alpha=ALPHA)
axes[1].set_title("PM Sensor Data")
axes[1].set_ylabel("PM Values")
axes[1].legend(loc='upper right', fontsize='small')
axes[1].grid(True)

# 3. Particle counts subplot
for col in particles_cols:
    axes[2].plot(df['timestamp'], df[col], label=col, alpha=ALPHA)
axes[2].set_title("Particle Count Data")
axes[2].set_ylabel("Counts")
axes[2].set_xlabel("Timestamp")
axes[2].legend(loc='upper right', fontsize='small')
axes[2].grid(True)

plt.tight_layout(rect=[0, 0, 1, 0.96])  # Leave space for suptitle
plt.show()
