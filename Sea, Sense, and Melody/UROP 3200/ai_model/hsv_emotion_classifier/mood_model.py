#!/usr/bin/env python3
"""
mood_model.py — Attentional GRU Mood Classifier for 26-D Multi-Modal Features
================================================================================

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Defines a GRU-based classifier enhanced with temporal self-attention.
    Input: (batch, 12, 26) — 12-frame window, 26 features per frame
    Output: 20-class logits

Architecture:
    - GRU (hidden=64, 1 layer, bidirectional=False)
    - Self-attention over time steps → context vector
    - Linear projection to 20 classes

Usage:
    from mood_model import AttentionalGRUMoodClassifier, load_model
    model = load_model('trained_model/gru_mood_model.pth', device)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Constants – must match emotion_profiles.py and generate_dataset.py
# ---------------------------------------------------------------------------
INPUT_DIM = 26
HIDDEN_DIM = 64
NUM_LAYERS = 1
NUM_CLASSES = 20
WINDOW_SIZE = 12


class AttentionalGRUMoodClassifier(nn.Module):
    """
    GRU + temporal self-attention classifier for multi-modal emotion sequences.

    The model processes a sequence of 26-dimensional feature vectors through
    a single-layer GRU, computes attention weights over time steps, produces
    a weighted context vector, and passes it through a linear layer to obtain
    20-class logits.
    """

    def __init__(self, input_dim=INPUT_DIM, hidden_dim=HIDDEN_DIM,
                 num_layers=NUM_LAYERS, num_classes=NUM_CLASSES):
        """
        Initialize the model layers.

        Parameters:
            input_dim (int): Number of features per time step (default 26).
            hidden_dim (int): Hidden state size of the GRU (default 64).
            num_layers (int): Number of stacked GRU layers (default 1).
            num_classes (int): Number of output emotion classes (default 20).
        """
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers,
                          batch_first=True, bidirectional=False)
        # Attention mechanism: learnable query vector
        self.attn_query = nn.Parameter(torch.randn(hidden_dim))
        self.fc = nn.Linear(hidden_dim, num_classes)

    def forward(self, x):
        """
        Forward pass of the classifier.

        Steps:
            1. Run the input sequence through the GRU.
            2. Compute attention scores via dot product between tanh(GRU outputs)
               and the learned query vector.
            3. Softmax over the time dimension to obtain attention weights.
            4. Compute weighted sum of GRU outputs (context vector).
            5. Pass context through a linear layer to get logits.

        Parameters:
            x (torch.Tensor): Input tensor of shape (batch, seq_len, input_dim).

        Returns:
            torch.Tensor: Logits tensor of shape (batch, num_classes).
        """
        # GRU outputs: (batch, seq_len, hidden_dim)
        gru_out, _ = self.gru(x)          # (B, T, H)

        # Compute attention scores
        # score = tanh(W * gru_out) · attn_query
        scores = torch.tanh(gru_out) @ self.attn_query  # (B, T)
        attn_weights = F.softmax(scores, dim=1)          # (B, T)

        # Weighted sum over time
        context = (gru_out * attn_weights.unsqueeze(-1)).sum(dim=1)  # (B, H)

        return self.fc(context)


def load_model(path, device):
    """
    Load a pretrained AttentionalGRUMoodClassifier from disk.

    The function instantiates the model, loads the state dictionary,
    moves it to the specified device, and sets it to evaluation mode.

    Parameters:
        path (str): Filesystem path to the .pth checkpoint.
        device (torch.device): Target device (CPU or CUDA).

    Returns:
        AttentionalGRUMoodClassifier: The loaded model in eval mode.
    """
    model = AttentionalGRUMoodClassifier()
    state = torch.load(path, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return model