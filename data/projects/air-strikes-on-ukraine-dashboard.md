# Air Strikes on Ukraine Analysis Dashboard

## Summary

Tuomas Kuusisto's personal project analyzes reported Russian missile and UAV strike activity in Ukraine. It includes a data pipeline and an interactive Streamlit dashboard. The repository describes it as an actively developed local and deployed MVP; the user confirms that the project is his own individual work and is not finished.

## Background and timing

The project uses a Kaggle dataset titled “Massive Missile Attacks on Ukraine” by Kaggle user piterfm. The repository states that the dataset is licensed CC BY-NC-SA 4.0. No project start date is stated in the README or CV.

## Tuomas's contribution

Tuomas states that he completed this project individually. The README and portfolio describe the project's implementation, including data ingestion and transformation, analytical marts, and the dashboard. The CV also describes building and publishing an MVP dashboard and conducting exploratory and comparative analysis. These sources do not provide a separate task-by-task record of his personal contribution beyond identifying it as his individual project.

## Technologies and their uses

- Python 3.12 and pandas for data ingestion, cleaning, and transformation.
- DuckDB for local analytical storage and data marts.
- SQL for summary and daily marts and dashboard-facing views.
- Streamlit for the dashboard.
- Plotly and PyDeck for charts and maps.
- Kaggle API for source-data download.

## Technical approach

The pipeline uses bronze, silver, and gold data layers. It normalizes columns and dates, enriches weapon references, maps target areas, and creates DuckDB marts and views for dashboard queries. The dashboard covers activity trends, launched and destroyed totals by weapon, target-area summaries, approximate centroid maps, and air-defense success percentages.

The repository defines air-defense success percentage as destroyed total divided by launched total. It cautions that strike records are rows in the cleaned source dataset and should not automatically be read as deduplicated counts of real-world attacks. Map points use approximate centroids rather than exact strike locations or official boundaries; nationwide, unknown, and multi-region rows also affect mapping and regional comparisons.

## Results and current status

The README describes a local and deployed MVP on Streamlit Community Cloud and says the project remains under active development. The portfolio calls it MVP-stage. The repository lists additional improvements as future work, including data-quality checks, tests for transformation and SQL assumptions, scheduled pipeline runs, and geographic validation. Those items are plans, not completed features. The user confirms the project is unfinished.

## Sources

- [GitHub repository and README](https://github.com/tujokuus/air-strikes-on-ukraine-dashboard)
- [Portfolio page](https://tujokuus.github.io/)
- `resume.pdf`
