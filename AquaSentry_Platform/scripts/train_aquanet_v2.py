#!/usr/bin/env python3
"""
AquaNet-V1 Optimizer & Re-Trainer.
Trains the 5-8-6-4 Multimodal Neural Network on a high-fidelity hydrogeochemical dataset
with dense boundary oversampling and asymmetric public health cost weighting.

Target:
- Total Nodes: 23
- Total Synapses: 112 (W1: 8x5, W2: 6x8, W3: 4x6)
- Target Accuracy: > 98.5% across continental stress conditions
- Zero-tolerance false negative safety guarantee
"""

import os
import sys
import math
import json
import time
import numpy as np

# Set deterministic seed
SEED = 42
np.random.seed(SEED)

CLASSES = ["Safe", "Caution", "Unsafe", "Hazardous"]
INPUT_MEAN = np.array([0.08, 7.5, 600.0, 4.0, 25.0], dtype=np.float32)
INPUT_STD = np.array([0.10, 0.7, 300.0, 3.0, 4.0], dtype=np.float32)

def generate_geochemical_dataset(n_samples: int = 120_000):
    print(f"[*] Generating {n_samples:,} high-fidelity hydrogeochemical samples...")
    
    # 4 Stratified cohorts:
    # Cohort 1: Broad continuous spectrum (30%)
    # Cohort 2: Dense WHO threshold boundary (0.010 mg/L +- 0.004) (25%)
    # Cohort 3: Dense BIS threshold boundary (0.050 mg/L +- 0.010) (25%)
    # Cohort 4: Dense Hazardous boundary (0.150 mg/L +- 0.025) (20%)
    
    n_broad = int(n_samples * 0.30)
    n_who = int(n_samples * 0.25)
    n_bis = int(n_samples * 0.25)
    n_haz = n_samples - (n_broad + n_who + n_bis)
    
    as_broad = np.random.uniform(0.001, 0.400, n_broad)
    as_who = np.random.uniform(0.006, 0.014, n_who)
    as_bis = np.random.uniform(0.040, 0.060, n_bis)
    as_haz = np.random.uniform(0.125, 0.175, n_haz)
    
    arsenic = np.concatenate([as_broad, as_who, as_bis, as_haz]).astype(np.float32)
    np.random.shuffle(arsenic)
    
    # Geochemical covariance
    # High arsenic often correlates with alkaline pH (adsorption desorption) and higher conductivity
    ph = np.clip(7.2 + (arsenic / 0.2) * 0.5 + np.random.normal(0, 0.4, n_samples), 5.5, 9.5).astype(np.float32)
    ec = np.clip(400.0 + (arsenic / 0.1) * 200.0 + np.random.normal(0, 180.0, n_samples), 80.0, 3500.0).astype(np.float32)
    turb = np.clip(np.random.exponential(3.5, n_samples), 0.1, 75.0).astype(np.float32)
    temp = np.clip(np.random.normal(25.0, 5.5, n_samples), 7.0, 42.0).astype(np.float32)
    
    X_raw = np.column_stack([arsenic, ph, ec, turb, temp])
    
    # Ground truth labels
    # 0: Safe (< 0.010), 1: Caution (0.010 - 0.050), 2: Unsafe (0.050 - 0.150), 3: Hazardous (> 0.150)
    y_indices = np.zeros(n_samples, dtype=np.int64)
    y_indices[(arsenic >= 0.010) & (arsenic <= 0.050)] = 1
    y_indices[(arsenic > 0.050) & (arsenic <= 0.150)] = 2
    y_indices[arsenic > 0.150] = 3
    
    # Normalize features using canonical moments
    X_norm = (X_raw - INPUT_MEAN) / INPUT_STD
    
    # One-hot encode targets
    Y_onehot = np.zeros((n_samples, 4), dtype=np.float32)
    Y_onehot[np.arange(n_samples), y_indices] = 1.0
    
    return X_norm, Y_onehot, y_indices, X_raw

class AquaNetTrainer:
    def __init__(self):
        # 5 -> 8 -> 6 -> 4
        # He initialization for ReLU layers
        self.W1 = (np.random.randn(8, 5) * np.sqrt(2.0 / 5)).astype(np.float32)
        self.B1 = np.zeros(8, dtype=np.float32)
        
        self.W2 = (np.random.randn(6, 8) * np.sqrt(2.0 / 8)).astype(np.float32)
        self.B2 = np.zeros(6, dtype=np.float32)
        
        # Xavier initialization for Softmax output layer
        self.W3 = (np.random.randn(4, 6) * np.sqrt(2.0 / (6 + 4))).astype(np.float32)
        self.B3 = np.zeros(4, dtype=np.float32)
        
        # Adam moments
        self.mW1, self.vW1 = np.zeros_like(self.W1), np.zeros_like(self.W1)
        self.mB1, self.vB1 = np.zeros_like(self.B1), np.zeros_like(self.B1)
        
        self.mW2, self.vW2 = np.zeros_like(self.W2), np.zeros_like(self.W2)
        self.mB2, self.vB2 = np.zeros_like(self.B2), np.zeros_like(self.B2)
        
        self.mW3, self.vW3 = np.zeros_like(self.W3), np.zeros_like(self.W3)
        self.mB3, self.vB3 = np.zeros_like(self.B3), np.zeros_like(self.B3)
        
        self.t = 0

    def relu(self, z):
        return np.maximum(0, z)

    def d_relu(self, z):
        return (z > 0).astype(np.float32)

    def softmax(self, logits):
        max_logits = np.max(logits, axis=1, keepdims=True)
        exp_logits = np.exp(logits - max_logits)
        return exp_logits / np.sum(exp_logits, axis=1, keepdims=True)

    def forward(self, X):
        # X: (N, 5)
        # Z1: (N, 8) = X @ W1.T + B1
        z1 = X @ self.W1.T + self.B1
        a1 = self.relu(z1)
        
        # Z2: (N, 6) = A1 @ W2.T + B2
        z2 = a1 @ self.W2.T + self.B2
        a2 = self.relu(z2)
        
        # Z3 / Logits: (N, 4) = A2 @ W3.T + B3
        logits = a2 @ self.W3.T + self.B3
        probs = self.softmax(logits)
        
        cache = (X, z1, a1, z2, a2, logits, probs)
        return probs, cache

    def compute_loss_and_gradients(self, Y_onehot, y_true_idx, cache, l2_reg=1e-4):
        X, z1, a1, z2, a2, logits, probs = cache
        N = X.shape[0]
        
        # Cross entropy with asymmetric penalty for dangerous under-predictions
        # If true is Unsafe (2) or Hazardous (3), but model predicts Safe (0) or Caution (1), penalize 4x
        loss_weights = np.ones((N, 4), dtype=np.float32)
        
        # Heavy penalty for under-estimating risk
        for i in range(N):
            true_c = y_true_idx[i]
            if true_c >= 2: # Unsafe or Hazardous
                loss_weights[i, :2] = 4.0 # Penalize safe/caution
            elif true_c == 1: # Caution
                loss_weights[i, 0] = 2.0 # Penalize safe
        
        eps = 1e-12
        loss = -np.mean(np.sum(Y_onehot * np.log(probs + eps), axis=1))
        # Add L2 penalty
        l2_loss = 0.5 * l2_reg * (np.sum(self.W1**2) + np.sum(self.W2**2) + np.sum(self.W3**2))
        total_loss = loss + l2_loss
        
        # Gradient w.r.t logits: (probs - Y)
        d_logits = (probs - Y_onehot) * loss_weights / N
        
        # Layer 3 gradients (Output: 4 nodes, W3: 4x6)
        # d_logits: (N, 4), a2: (N, 6)
        dW3 = d_logits.T @ a2 + l2_reg * self.W3
        dB3 = np.sum(d_logits, axis=0)
        
        # Layer 2 gradients (Hidden 2: 6 nodes, W2: 6x8)
        # d_a2: (N, 6) = d_logits @ W3
        da2 = d_logits @ self.W3
        dz2 = da2 * self.d_relu(z2)
        dW2 = dz2.T @ a1 + l2_reg * self.W2
        dB2 = np.sum(dz2, axis=0)
        
        # Layer 1 gradients (Hidden 1: 8 nodes, W1: 8x5)
        # d_a1: (N, 8) = dz2 @ W2
        da1 = dz2 @ self.W2
        dz1 = da1 * self.d_relu(z1)
        dW1 = dz1.T @ X + l2_reg * self.W1
        dB1 = np.sum(dz1, axis=0)
        
        grads = (dW1, dB1, dW2, dB2, dW3, dB3)
        return total_loss, grads

    def update_adam(self, grads, lr=0.005, beta1=0.9, beta2=0.999, eps=1e-8):
        dW1, dB1, dW2, dB2, dW3, dB3 = grads
        self.t += 1
        
        for w, dw, mw, vw in [
            (self.W1, dW1, self.mW1, self.vW1),
            (self.W2, dW2, self.mW2, self.vW2),
            (self.W3, dW3, self.mW3, self.vW3),
        ]:
            mw[:] = beta1 * mw + (1 - beta1) * dw
            vw[:] = beta2 * vw + (1 - beta2) * (dw**2)
            m_hat = mw / (1 - beta1**self.t)
            v_hat = vw / (1 - beta2**self.t)
            w -= lr * m_hat / (np.sqrt(v_hat) + eps)
            
        for b, db, mb, vb in [
            (self.B1, dB1, self.mB1, self.vB1),
            (self.B2, dB2, self.mB2, self.vB2),
            (self.B3, dB3, self.mB3, self.vB3),
        ]:
            mb[:] = beta1 * mb + (1 - beta1) * db
            vb[:] = beta2 * vb + (1 - beta2) * (db**2)
            m_hat = mb / (1 - beta1**self.t)
            v_hat = vb / (1 - beta2**self.t)
            b -= lr * m_hat / (np.sqrt(v_hat) + eps)

    def train(self, X_train, Y_train, y_train_idx, X_val, y_val_idx, epochs=150, batch_size=256, lr_init=0.008):
        n_train = X_train.shape[0]
        print(f"[*] Training AquaNet (5-8-6-4) for {epochs} epochs (batch size: {batch_size})...")
        
        best_val_acc = 0.0
        best_weights = None
        
        for epoch in range(1, epochs + 1):
            # Cosine learning rate decay
            lr = 0.0002 + 0.5 * (lr_init - 0.0002) * (1 + math.cos(math.pi * epoch / epochs))
            
            indices = np.random.permutation(n_train)
            epoch_loss = 0.0
            n_batches = 0
            
            for i in range(0, n_train, batch_size):
                b_idx = indices[i:i+batch_size]
                X_batch = X_train[b_idx]
                Y_batch = Y_train[b_idx]
                y_idx_batch = y_train_idx[b_idx]
                
                probs, cache = self.forward(X_batch)
                loss, grads = self.compute_loss_and_gradients(Y_batch, y_idx_batch, cache)
                self.update_adam(grads, lr=lr)
                
                epoch_loss += loss
                n_batches += 1
                
            epoch_loss /= n_batches
            
            # Validation every 10 epochs
            if epoch % 10 == 0 or epoch == epochs:
                val_probs, _ = self.forward(X_val)
                val_preds = np.argmax(val_probs, axis=1)
                val_acc = np.mean(val_preds == y_val_idx) * 100.0
                
                # Check toxic false negative count on validation set (As >= 50ug/L predicted as Safe)
                toxic_fn = np.sum((y_val_idx >= 2) & (val_preds == 0))
                
                print(f"    Epoch {epoch:3d}/{epochs} | Loss: {epoch_loss:.4f} | Val Acc: {val_acc:.2f}% | Toxic FNs: {toxic_fn} | lr: {lr:.5f}")
                
                if val_acc > best_val_acc and toxic_fn == 0:
                    best_val_acc = val_acc
                    best_weights = {
                        "W1": self.W1.copy(), "B1": self.B1.copy(),
                        "W2": self.W2.copy(), "B2": self.B2.copy(),
                        "W3": self.W3.copy(), "B3": self.B3.copy(),
                    }
                    
        print(f"[*] Training finished! Best Validation Accuracy: {best_val_acc:.2f}%")
        if best_weights is not None:
            self.W1, self.B1 = best_weights["W1"], best_weights["B1"]
            self.W2, self.B2 = best_weights["W2"], best_weights["B2"]
            self.W3, self.B3 = best_weights["W3"], best_weights["B3"]
        return best_val_acc

def main():
    X_norm, Y_onehot, y_indices, X_raw = generate_geochemical_dataset(120_000)
    
    # Train / Val Split (100,000 train, 20,000 val)
    X_train, Y_train, y_train_idx = X_norm[:100_000], Y_onehot[:100_000], y_indices[:100_000]
    X_val, Y_val, y_val_idx = X_norm[100_000:], Y_onehot[100_000:], y_indices[100_000:]
    
    trainer = AquaNetTrainer()
    acc = trainer.train(X_train, Y_train, y_train_idx, X_val, y_val_idx, epochs=160, batch_size=256, lr_init=0.009)
    
    # Format weights to 4 decimal places for exact injection into neural_classifier.py
    def fmt_2d(arr):
        lines = []
        for row in arr:
            formatted_row = ", ".join(f"{float(v):8.4f}" for v in row)
            lines.append(f"    [{formatted_row}],")
        return "\n".join(lines)
        
    def fmt_1d(arr):
        return ", ".join(f"{float(v):.4f}" for v in arr)
        
    print("\n" + "=" * 70)
    print("OPTIMIZED WEIGHT MATRICES (READY FOR INJECTION):")
    print("=" * 70)
    print(f"# W1 (8x5):\nW1 = [\n{fmt_2d(trainer.W1)}\n]")
    print(f"# B1 (8,):\nB1 = [{fmt_1d(trainer.B1)}]")
    print(f"# W2 (6x8):\nW2 = [\n{fmt_2d(trainer.W2)}\n]")
    print(f"# B2 (6,):\nB2 = [{fmt_1d(trainer.B2)}]")
    print(f"# W3 (4x6):\nW3 = [\n{fmt_2d(trainer.W3)}\n]")
    print(f"# B3 (4,):\nB3 = [{fmt_1d(trainer.B3)}]")
    
    # Save optimized weights to JSON file
    out_json = {
        "W1": trainer.W1.round(4).tolist(),
        "B1": trainer.B1.round(4).tolist(),
        "W2": trainer.W2.round(4).tolist(),
        "B2": trainer.B2.round(4).tolist(),
        "W3": trainer.W3.round(4).tolist(),
        "B3": trainer.B3.round(4).tolist(),
        "validation_accuracy": round(acc, 2),
    }
    with open("/tmp/optimized_aquanet_weights.json", "w") as f:
        json.dump(out_json, f, indent=2)
    print("[+] Saved /tmp/optimized_aquanet_weights.json")

if __name__ == "__main__":
    main()
