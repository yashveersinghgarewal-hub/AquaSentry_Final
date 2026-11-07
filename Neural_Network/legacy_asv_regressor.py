"""
Simple feedforward neural network adapted for predicting arsenic concentration
from anodic stripping voltammetry (ASV) data.
"""

from __future__ import annotations

try:
    import numpy as np
except ImportError:
    import sys
    print("[!] Error: NumPy is required to execute the legacy ASV regressor.")
    print("    Install numpy via: pip install numpy, or run within a virtualenv with numpy.")
    sys.exit(1)

# -------------------- Configuration --------------------
INPUT_SIZE = 81  # Number of potential points in ASV scan (-1000mV to -600mV in 5mV steps)
HIDDEN_SIZE = 10_000
OUTPUT_SIZE = 1
EPOCHS = 10
BATCH_SIZE = 128
LEARNING_RATE = 0.01
NUM_SAMPLES = 100_000
SEED = 42

np.random.seed(SEED)

# -------------------- Synthetic Data Generator --------------------
def generate_arsenic_data(num_samples: int) -> tuple[np.ndarray, np.ndarray]:
    """
    Generates synthetic ASV data modeling the attached arsenic example.
    Each curve has a peak around -795 mV, with peak current proportional
    to the concentration (using the calibration JSON: slope 0.856, intercept 0.009).
    """
    potentials = np.linspace(-1000, -600, INPUT_SIZE)
    
    # Concentrations in ppm (e.g., 0.0 to 0.5)
    concentrations = np.random.uniform(0.0, 0.5, (num_samples, 1)).astype(np.float32)
    
    slope = 0.856
    intercept = 0.009
    peak_currents = slope * concentrations + intercept
    
    baseline = 0.04
    peak_V = -795.0
    width = 20.0
    
    peak_shape = np.exp(-((potentials - peak_V) ** 2) / (2 * width ** 2))
    
    x = baseline + peak_currents * peak_shape
    noise = np.random.normal(0, 0.002, x.shape)
    x += noise
    
    return x.astype(np.float32), concentrations.astype(np.float32)

# -------------------- Activation functions --------------------
def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(0, x)

def relu_derivative(x: np.ndarray) -> np.ndarray:
    return (x > 0).astype(np.float32)

# -------------------- Network initialization --------------------
def init_params() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    w1 = np.random.randn(INPUT_SIZE, HIDDEN_SIZE).astype(np.float32) * np.sqrt(2.0 / INPUT_SIZE)
    b1 = np.zeros((1, HIDDEN_SIZE), dtype=np.float32)
    w2 = np.random.randn(HIDDEN_SIZE, OUTPUT_SIZE).astype(np.float32) * np.sqrt(2.0 / HIDDEN_SIZE)
    b2 = np.zeros((1, OUTPUT_SIZE), dtype=np.float32)
    return w1, b1, w2, b2

# -------------------- Forward / backward pass --------------------
def forward(
    x: np.ndarray,
    w1: np.ndarray,
    b1: np.ndarray,
    w2: np.ndarray,
    b2: np.ndarray,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    z1 = x @ w1 + b1
    a1 = relu(z1)
    z2 = a1 @ w2 + b2
    a2 = z2  # Linear activation for regression
    cache = (z1, a1, z2, a2)
    return a2, cache

def compute_loss(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    # Mean Squared Error
    return float(np.mean((y_true - y_pred) ** 2))

def backward(
    x: np.ndarray,
    y: np.ndarray,
    cache: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    w2: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    m = x.shape[0]
    z1, a1, _, a2 = cache

    # Derivative of MSE Loss w.r.t z2 (linear output)
    d_z2 = a2 - y
    
    d_w2 = (a1.T @ d_z2) / m
    d_b2 = np.sum(d_z2, axis=0, keepdims=True) / m

    d_a1 = d_z2 @ w2.T
    d_z1 = d_a1 * relu_derivative(z1)
    d_w1 = (x.T @ d_z1) / m
    d_b1 = np.sum(d_z1, axis=0, keepdims=True) / m

    return d_w1, d_b1, d_w2, d_b2

def train() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    print("Generating synthetic arsenic ASV data...")
    x, y = generate_arsenic_data(NUM_SAMPLES)

    w1, b1, w2, b2 = init_params()

    print(f"Network architecture: {INPUT_SIZE} (Potentials) -> {HIDDEN_SIZE} -> {OUTPUT_SIZE} (Concentration)")
    print(f"Total hidden neurons: {HIDDEN_SIZE}")
    print(f"Training for {EPOCHS} epochs...\n")

    for epoch in range(1, EPOCHS + 1):
        indices = np.random.permutation(NUM_SAMPLES)
        x_shuffled = x[indices]
        y_shuffled = y[indices]

        epoch_loss = 0.0
        epoch_mae = 0.0
        num_batches = 0

        for i in range(0, NUM_SAMPLES, BATCH_SIZE):
            x_batch = x_shuffled[i:i + BATCH_SIZE]
            y_batch = y_shuffled[i:i + BATCH_SIZE]

            y_pred, cache = forward(x_batch, w1, b1, w2, b2)
            loss = compute_loss(y_batch, y_pred)
            d_w1, d_b1, d_w2, d_b2 = backward(x_batch, y_batch, cache, w2)

            w1 = w1 - LEARNING_RATE * d_w1
            b1 = b1 - LEARNING_RATE * d_b1
            w2 = w2 - LEARNING_RATE * d_w2
            b2 = b2 - LEARNING_RATE * d_b2

            epoch_loss += loss
            epoch_mae += float(np.mean(np.abs(y_pred - y_batch)))
            num_batches += 1

        epoch_loss /= num_batches
        epoch_mae /= num_batches

        print(f"Epoch {epoch:4d}/{EPOCHS} - MSE Loss: {epoch_loss:.6f} - Mean Absolute Error: {epoch_mae:.4f} ppm")

    final_mae = 0.0
    num_batches = 0
    for i in range(0, NUM_SAMPLES, BATCH_SIZE):
        x_batch = x[i:i + BATCH_SIZE]
        y_batch = y[i:i + BATCH_SIZE]
        final_pred = forward(x_batch, w1, b1, w2, b2)[0]
        final_mae += float(np.mean(np.abs(final_pred - y_batch)))
        num_batches += 1
    
    if num_batches > 0:
        final_mae /= num_batches

    print(f"\nFinal Mean Absolute Error: {final_mae:.4f} ppm")
    print("Training complete.")
    return w1, b1, w2, b2

if __name__ == "__main__":
    train()