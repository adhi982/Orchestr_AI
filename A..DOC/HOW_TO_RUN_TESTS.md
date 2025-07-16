# How to Run the Test Kafka Script

To properly run the Kafka test script, you have a few options:

## Option 1: Use the sys.path modification (already implemented)
This is already implemented in the updated script. Just run:

```
python scripts/test_kafka.py
```

## Option 2: Use Python's module syntax
```
python -m scripts.test_kafka
```

## Option 3: Install the package in development mode
Run this command from the project root directory:

```
pip install -e .
```

Then you can run:
```
python scripts/test_kafka.py
```

## Troubleshooting

If you continue to have import issues:

1. Make sure you're running the command from the root directory of the project.
2. Check that __init__.py files exist in:
   - The project root directory
   - The common directory
   - The scripts directory
3. Ensure your virtual environment is activated.
4. Try installing the package in development mode as shown in Option 3.
