# CodeT5+ Fine-tuning Configuration

# Data paths
DATA_SOURCE = "E:/Intel Fest/Fine Tune/datasets/clean_code"      # Path to your clean_code dataset
PROCESSED_DATA = "./data/processed"                               # Where to save processed data
OUTPUT_DIR = "./checkpoints/codet5p-finetuned"                  # Where to save the fine-tuned model

# Model configuration
MODEL_NAME = "Salesforce/codet5p-220m"
MAX_SOURCE_LENGTH = 512     # Maximum input length
MAX_TARGET_LENGTH = 256     # Maximum output length

# Training configuration
NUM_EPOCHS = 3              # Number of training epochs
BATCH_SIZE_TRAIN = 4        # Training batch size (adjust based on GPU memory)
BATCH_SIZE_EVAL = 8         # Evaluation batch size
LEARNING_RATE = 5e-5        # Learning rate
WEIGHT_DECAY = 0.01         # Weight decay for regularization
WARMUP_STEPS = 500          # Warmup steps for learning rate scheduler

# Evaluation and logging
EVAL_STEPS = 500           # Evaluate every N steps
SAVE_STEPS = 1000          # Save checkpoint every N steps
LOGGING_STEPS = 100        # Log metrics every N steps

# Hardware configuration
USE_FP16 = True            # Use mixed precision training (recommended for RTX 3050)
SEED = 42                  # Random seed for reproducibility

# Data sampling (for testing/development)
MAX_SAMPLES = None         # Set to a number like 10000 for quick testing, None for full dataset
TEST_SIZE = 0.1           # Fraction of data to use for validation

# Task configuration
TASK_TYPE = "code_completion"  # Options: "code_completion", "code_summarization"
