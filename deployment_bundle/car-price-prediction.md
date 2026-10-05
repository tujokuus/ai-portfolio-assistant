# Car Price Prediction

> **Project status:** This project is not finished and is still under active development.

This project explores European vehicle listing data and develops machine learning models
for vehicle price prediction.

## Goals

- understand data quality, distributions, and market differences
- identify the features most strongly related to vehicle price
- compare baseline regression models and tune the strongest candidates
- diagnose model errors and test focused feature engineering ideas

## Notebook Workflow

Run the notebooks in this order:

1. `notebooks/eda.ipynb` - data quality, distributions, price relationships, countries, and taxation
2. `notebooks/baseline_modeling.ipynb` - model comparison, ensemble, and light hyperparameter tuning
3. `notebooks/model_diagnostics.ipynb` - error analysis, engineered features, and permutation importance
4. `notebooks/advanced_modeling.ipynb` - data cleaning, feature selection, deeper model comparison, and the EUR 200k experiment

Each notebook is self-contained and reads `data/raw/cars.csv`.

Modeling results and experiment decisions are summarized in `notebooks/experiment_notes.ipynb`.

## Project Structure

```text
car-price-prediction/
|-- data/
|   |-- raw/
|   |-- interim/
|   `-- processed/
|-- models/
|-- notebooks/
|   |-- eda.ipynb
|   |-- baseline_modeling.ipynb
|   |-- model_diagnostics.ipynb
|   |-- advanced_modeling.ipynb
|   `-- experiment_notes.ipynb
|-- reports/
|-- src/car_price_prediction/
|-- tests/
|-- README.md
`-- requirements.txt
```

## Environment Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Select the `.venv` Python environment as the notebook kernel in VS Code.

## Modeling Note

The current validation split has been used during model exploration. Before reporting final
performance, reserve a new untouched test set. If listing dates become available, prefer a
chronological test split.
