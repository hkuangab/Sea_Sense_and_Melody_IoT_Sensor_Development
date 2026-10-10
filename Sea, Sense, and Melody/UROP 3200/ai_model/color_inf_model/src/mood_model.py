#!/usr/bin/env python3
"""
mood_model.py — GRU Mood Classifier Definition
================================================
Author: KUANG, Haozhe
Affiliation: Hong Kong University of Science and Technology (HKUST)
Email: hkuangab@connect.ust.hk
Date: October 2026

Description:
    Defines the GRU-based neural network architecture for emotion
    classification from HSV color features. Supports 16 complex
    emotional states.

Architecture:
    - Input:  (batch, seq_len=12, input_dim=17)
    - GRU:    hidden_dim=32, num_layers=1, dropout=0.3, bidirectional=False
    - FC:     hidden_dim → num_classes (16)
    - Output: logits (batch, 16)

Factory functions:
    - create_default_model(): Create model with default hyperparameters
    - load_model(path, device): Load pretrained weights
==================================================
"""

import torch
import torch.nn as nn


class GRUMoodClassifier(nn.Module):
    """
    GRU-based emotion classifier from sequential HSV color features.
    
    Takes a temporal window of color features and predicts the
    emotional state at the final timestep.
    
    Args:
        input_dim: Number of input features per timestep (default: 17)
        hidden_dim: GRU hidden state dimension (default: 32)
        num_layers: Number of stacked GRU layers (default: 1)
        dropout: Dropout probability between GRU layers (default: 0.3)
        num_classes: Number of emotion classes (default: 16)
    """
    
    def __init__(self, input_dim=17, hidden_dim=32, num_layers=1,
                 dropout=0.3, num_classes=16):
        super(GRUMoodClassifier, self).__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_classes = num_classes
        
        # GRU layer
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=False
        )
        
        # Additional dropout for single-layer case
        self.dropout = nn.Dropout(dropout)
        
        # Fully connected classifier
        self.fc = nn.Linear(hidden_dim, num_classes)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize weights using Xavier uniform initialization."""
        for name, param in self.gru.named_parameters():
            if 'weight_ih' in name:
                nn.init.xavier_uniform_(param.data)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                # Set forget gate bias to 1 (common practice for GRU/LSTM)
                n = param.size(0)
                start, end = n // 3, 2 * n // 3
                param.data[start:end].fill_(1.0)
        
        nn.init.xavier_uniform_(self.fc.weight)
        nn.init.zeros_(self.fc.bias)
    
    def forward(self, x):
        """
        Forward pass through the network.
        
        Args:
            x: Input tensor of shape (batch_size, seq_len, input_dim)
        
        Returns:
            Logits tensor of shape (batch_size, num_classes)
        """
        # GRU forward
        gru_out, hidden = self.gru(x)
        
        # Take the last timestep's hidden state
        # hidden shape: (num_layers, batch, hidden_dim)
        last_hidden = hidden[-1]  # (batch, hidden_dim)
        
        # Apply dropout
        last_hidden = self.dropout(last_hidden)
        
        # Classify
        logits = self.fc(last_hidden)  # (batch, num_classes)
        
        return logits
    
    def predict_proba(self, x):
        """
        Get softmax probabilities for each class.
        
        Args:
            x: Input tensor of shape (batch_size, seq_len, input_dim)
        
        Returns:
            Probability tensor of shape (batch_size, num_classes)
        """
        logits = self.forward(x)
        return torch.softmax(logits, dim=1)
    
    def predict(self, x):
        """
        Get hard class predictions.
        
        Args:
            x: Input tensor of shape (batch_size, seq_len, input_dim)
        
        Returns:
            Predicted class indices of shape (batch_size,)
        """
        probs = self.predict_proba(x)
        return torch.argmax(probs, dim=1)


def create_default_model(num_classes=16):
    """
    Create a GRU model with default hyperparameters optimized for
    Raspberry Pi 5 performance.
    
    Args:
        num_classes: Number of emotion classes (default: 16)
    
    Returns:
        GRUMoodClassifier instance
    """
    return GRUMoodClassifier(
        input_dim=17,
        hidden_dim=32,
        num_layers=1,
        dropout=0.3,
        num_classes=num_classes
    )


def load_model(model_path, device=None):
    """
    Load a pretrained GRU model from disk.
    
    Args:
        model_path: Path to the .pth checkpoint file
        device: Torch device (cpu/cuda). Auto-detected if None.
    
    Returns:
        GRUMoodClassifier instance with loaded weights
    """
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Load checkpoint to get num_classes
    checkpoint = torch.load(model_path, map_location=device, weights_only=True)
    
    # Infer num_classes from the fc layer weight shape
    if 'fc.weight' in checkpoint:
        num_classes = checkpoint['fc.weight'].shape[0]
    else:
        num_classes = 16  # Default fallback
    
    # Create model with correct number of classes
    model = create_default_model(num_classes=num_classes)
    model.load_state_dict(checkpoint)
    model.to(device)
    model.eval()
    
    return model


# ═══════════════════════════════════════════════════════════
# MODEL SUMMARY (for verification)
# ═══════════════════════════════════════════════════════════

def print_model_summary(model):
    """Print a summary of the model architecture and parameter count."""
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f'Model: {model.__class__.__name__}')
    print(f'  Input dim:     {model.input_dim}')
    print(f'  Hidden dim:    {model.hidden_dim}')
    print(f'  Num layers:    {model.num_layers}')
    print(f'  Num classes:   {model.num_classes}')
    print(f'  Total params:  {total_params:,}')
    print(f'  Trainable:     {trainable_params:,}')
    print(f'  Model size:    {total_params * 4 / 1024:.1f} KB (float32)')


# ═══════════════════════════════════════════════════════════
# SELF-TEST
# ═══════════════════════════════════════════════════════════

if __name__ == '__main__':
    print('Testing GRUMoodClassifier...')
    
    # Create model
    model = create_default_model(num_classes=16)
    print_model_summary(model)
    
    # Test forward pass
    batch_size = 4
    seq_len = 12
    input_dim = 17
    
    dummy_input = torch.randn(batch_size, seq_len, input_dim)
    output = model(dummy_input)
    
    print(f'\nForward pass test:')
    print(f'  Input shape:  {dummy_input.shape}')
    print(f'  Output shape: {output.shape}')
    print(f'  Output range: [{output.min().item():.3f}, {output.max().item():.3f}]')
    
    # Test predict_proba
    probs = model.predict_proba(dummy_input)
    print(f'\nProbability test:')
    print(f'  Probs shape:  {probs.shape}')
    print(f'  Row sums:     {probs.sum(dim=1)}')
    
    # Test predict
    preds = model.predict(dummy_input)
    print(f'\nPrediction test:')
    print(f'  Predictions:  {preds}')
    
    # Test save/load cycle
    print('\nSave/Load test:')
    torch.save(model.state_dict(), '/tmp/test_model.pth')
    loaded = load_model('/tmp/test_model.pth')
    loaded_output = loaded(dummy_input)
    assert torch.allclose(output, loaded_output, atol=1e-6)
    print('  ✓ Save/Load successful!')
    
    print('\nAll tests passed!')